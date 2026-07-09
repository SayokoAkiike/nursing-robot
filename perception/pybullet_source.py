"""PyBullet-backed frame source for the perception pipeline (Phase 4, PR17/PR18).

This is the simulation counterpart to WebcamSource/VideoFileSource/
ImageDirectorySource in `camera_source.py` -- it implements the exact same
FrameSource interface (`.frames()` yielding BGR numpy arrays, `.close()`),
so nothing downstream (`perception/qr_detector.py`, `perception/
run_perception.py`) needs to know or care that the frames came from a
physics simulation instead of a real camera.

Scene geometry (PR17): a headless (p.DIRECT -- no display, safe in CI and
Codespaces) scene with a floor, a bed placeholder, and a robot body
(pybullet_data's bundled r2d2.urdf, standing in for PreCareBot's own body
since no custom URDF exists yet) that moves in a straight line from a
"dock" position to a "bedside" position. The robot's position is set
directly per step (`resetBasePositionAndOrientation`) rather than driven
by wheel/joint control -- this keeps the motion perfectly deterministic
and keeps this module's risk surface small. `p.stepSimulation()` still
runs each step so the world is a real physics world (collision geometry
loaded, gravity active) that later work can build real locomotion into
without changing this module's public interface.

QR overlay (PR18): rather than texture-mapping QR codes onto 3D props
(which would depend on PyBullet's UV-mapping/lighting behavior for a
flat-plane box -- not something verifiable without a live test run),
QR codes are composited directly onto each rendered frame as a 2D overlay
using the same `qrcode` library already used by
`tests/test_run_perception.py`'s synthetic frames. This makes QR
decodability independent of the 3D renderer entirely. Unlike an earlier
version of this module, the QR image is *not* resized after generation --
`box_size` is chosen up front so qrcode renders close to the target pixel
size natively. Downscaling a QR's fine module pattern with cv2.resize
(especially cv2.INTER_NEAREST) reliably destroys the finder patterns the
detector needs; generating at (approximately) the right size avoids that
failure mode entirely instead of trying to compensate for it.

GUI/visual mode (p.GUI) is out of scope here -- see the standalone
local-only demo entrypoint planned for a later PR; Codespaces has no
display, so this module only ever uses p.DIRECT.
"""
from __future__ import annotations

from typing import Iterator

import cv2
import numpy as np

from perception.camera_source import FrameSource

# name -> (dock_position, bedside_position), both (x, y, z) in meters.
# Kept intentionally small/simple: a straight corridor-to-bedside path.
SCENE_PRESETS = {
    "delivery": ((0.0, 0.0, 0.1), (2.0, 1.5, 0.1)),
}

# name -> (base scene preset, {overlay_role: qr_data}). Reuses the same
# scene geometry as the base preset; only adds QR overlays on top.
QR_OVERLAY_PRESETS = {
    "delivery_with_qr": (
        "delivery",
        {"patient_id": "PATIENT_A_ROOM_203", "kit_id": "KIT_TOILETING_A"},
    ),
}

DEFAULT_STEPS = 30
DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240

# version=1 QR + border=4 => 21 + 2*4 = 29 modules per side.
_QR_MODULES_PER_SIDE = 21 + 2 * 4


class PyBulletSource(FrameSource):
    """Renders frames from a headless PyBullet scene as the robot moves
    from a dock position to a bedside position, optionally with QR-coded
    overlays composited onto every frame (see QR_OVERLAY_PRESETS).

    Always connects with p.DIRECT (no GUI, no display needed).
    """

    def __init__(
        self,
        preset: str = "delivery",
        steps: int = DEFAULT_STEPS,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ):
        if preset in QR_OVERLAY_PRESETS:
            base_preset, overlay = QR_OVERLAY_PRESETS[preset]
            self.qr_overlay: "dict[str, str] | None" = overlay
            preset = base_preset
        elif preset in SCENE_PRESETS:
            self.qr_overlay = None
        else:
            raise ValueError(f"Unknown PyBullet scene preset: {preset!r}")
        if steps < 1:
            raise ValueError("steps must be >= 1")
        self.preset = preset
        self.steps = steps
        self.width = width
        self.height = height
        self._dock, self._bedside = SCENE_PRESETS[preset]
        self._client_id: "int | None" = None
        self._overlay_images: "dict[str, np.ndarray]" = {}

    def _connect(self):
        import pybullet as p
        import pybullet_data

        client_id = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=client_id)
        p.setGravity(0, 0, -9.8, physicsClientId=client_id)
        p.loadURDF("plane.urdf", physicsClientId=client_id)

        # Bed placeholder: a static box near the bedside position.
        bed_half_extents = [0.5, 0.9, 0.25]
        bed_collision = p.createCollisionShape(
            p.GEOM_BOX, halfExtents=bed_half_extents, physicsClientId=client_id
        )
        bed_visual = p.createVisualShape(
            p.GEOM_BOX, halfExtents=bed_half_extents, rgbaColor=[1, 1, 1, 1], physicsClientId=client_id
        )
        p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=bed_collision,
            baseVisualShapeIndex=bed_visual,
            basePosition=[self._bedside[0], self._bedside[1] + 1.0, bed_half_extents[2]],
            physicsClientId=client_id,
        )

        robot_id = p.loadURDF("r2d2.urdf", basePosition=list(self._dock), physicsClientId=client_id)
        return client_id, robot_id

    def _overlay_box_size(self) -> int:
        """Pixels per QR module, chosen so the rendered QR is roughly a
        third of the shorter frame dimension without needing any resize
        afterwards."""
        target_size = max(60, min(self.height, self.width) // 3)
        return max(3, target_size // _QR_MODULES_PER_SIDE)

    def _prepare_qr_overlays(self) -> None:
        if not self.qr_overlay:
            return
        import qrcode

        box_size = self._overlay_box_size()
        for role, value in self.qr_overlay.items():
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=box_size,
                border=4,
            )
            qr.add_data(value)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            self._overlay_images[role] = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def _apply_qr_overlays(self, frame: np.ndarray) -> np.ndarray:
        if not self._overlay_images:
            return frame
        h, w = frame.shape[:2]
        for role, qr_img in self._overlay_images.items():
            qh, qw = qr_img.shape[:2]
            qh, qw = min(qh, h), min(qw, w)
            clipped = qr_img[:qh, :qw]
            if role == "kit_id":
                x, y = max(w - qw - 10, 0), 10
            else:
                x, y = 10, 10
            frame[y : y + qh, x : x + qw] = clipped
        return frame

    def frames(self) -> Iterator[np.ndarray]:
        import pybullet as p

        client_id, robot_id = self._connect()
        self._client_id = client_id
        self._prepare_qr_overlays()
        try:
            dock = np.array(self._dock, dtype=float)
            bedside = np.array(self._bedside, dtype=float)
            for step in range(self.steps):
                t = step / max(self.steps - 1, 1)
                position = dock + (bedside - dock) * t
                p.resetBasePositionAndOrientation(
                    robot_id, position.tolist(), [0, 0, 0, 1], physicsClientId=client_id
                )
                p.stepSimulation(physicsClientId=client_id)

                eye = position + np.array([0.0, -1.5, 1.2])
                target = position + np.array([0.0, 0.5, 0.2])
                view_matrix = p.computeViewMatrix(eye.tolist(), target.tolist(), [0, 0, 1])
                projection_matrix = p.computeProjectionMatrixFOV(
                    fov=60, aspect=self.width / self.height, nearVal=0.1, farVal=10.0
                )
                _, _, rgba, _, _ = p.getCameraImage(
                    self.width,
                    self.height,
                    viewMatrix=view_matrix,
                    projectionMatrix=projection_matrix,
                    renderer=p.ER_TINY_RENDERER,
                    physicsClientId=client_id,
                )
                rgba_array = np.reshape(np.array(rgba, dtype=np.uint8), (self.height, self.width, 4))
                bgr = cv2.cvtColor(rgba_array, cv2.COLOR_RGBA2BGR)
                bgr = self._apply_qr_overlays(bgr)
                yield bgr
        finally:
            self.close()

    def close(self) -> None:
        if self._client_id is not None:
            import pybullet as p

            try:
                p.disconnect(physicsClientId=self._client_id)
            except Exception:
                pass
            self._client_id = None
