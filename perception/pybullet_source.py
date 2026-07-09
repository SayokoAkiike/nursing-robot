"""PyBullet-backed frame source for the perception pipeline (Phase 4, PR17).

This is the simulation counterpart to WebcamSource/VideoFileSource/
ImageDirectorySource in `camera_source.py` -- it implements the exact same
FrameSource interface (`.frames()` yielding BGR numpy arrays, `.close()`),
so nothing downstream (`perception/qr_detector.py`, `perception/
run_perception.py`) needs to know or care that the frames came from a
physics simulation instead of a real camera.

Scope of this first PR: a headless (p.DIRECT -- no display, safe in CI and
Codespaces) scene with a floor, a bed placeholder, and a robot body
(pybullet_data's bundled r2d2.urdf, standing in for PreCareBot's own body
since no custom URDF exists yet) that moves in a straight line from a
"dock" position to a "bedside" position. The robot's position is set
directly per step (`resetBasePositionAndOrientation`) rather than driven
by wheel/joint control -- this keeps the motion perfectly deterministic
and keeps this PR's risk surface small. `p.stepSimulation()` still runs
each step so the world is a real physics world (collision geometry loaded,
gravity active) that later work can build real locomotion into without
changing this module's public interface.

QR-coded props (patient badge / kit) are added in a follow-up PR -- this
PR only proves frames can be rendered and consumed through the existing
FrameSource contract. GUI/visual mode (p.GUI) is out of scope here too --
see the standalone local-only demo entrypoint planned for a later PR;
Codespaces has no display, so this module only ever uses p.DIRECT.
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

DEFAULT_STEPS = 30
DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240


class PyBulletSource(FrameSource):
    """Renders frames from a headless PyBullet scene as the robot moves
    from a dock position to a bedside position.

    `preset` selects a (dock, bedside) pair from SCENE_PRESETS. Always
    connects with p.DIRECT (no GUI, no display needed).
    """

    def __init__(
        self,
        preset: str = "delivery",
        steps: int = DEFAULT_STEPS,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ):
        if preset not in SCENE_PRESETS:
            raise ValueError(f"Unknown PyBullet scene preset: {preset!r}")
        if steps < 1:
            raise ValueError("steps must be >= 1")
        self.preset = preset
        self.steps = steps
        self.width = width
        self.height = height
        self._dock, self._bedside = SCENE_PRESETS[preset]
        self._client_id: "int | None" = None

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

    def frames(self) -> Iterator[np.ndarray]:
        import pybullet as p

        client_id, robot_id = self._connect()
        self._client_id = client_id
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
