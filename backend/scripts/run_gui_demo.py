"""Local-only GUI visualization of PreCareBot's Phase 4 PyBullet delivery scene.

Requires a real display (a window manager / X server) -- **does not run in
CI or GitHub Codespaces**, which have neither. This is the visual
counterpart to `backend/services/robot_service.py`'s tail CLI demo: same
"explicit local run only, never imported by anything tested" positioning,
just for the Phase 4 simulation scene instead of the state machine.

Deliberately does NOT reuse `perception.pybullet_source.PyBulletSource`
directly -- that class always connects with `p.DIRECT` on purpose (see its
own docstring), and changing that would risk the one thing this whole
Phase 4 track has tried hardest to avoid: touching a class that CI/
Codespaces tests already exercise headlessly. Instead, this module
duplicates the small amount of scene-setup code (floor, bed placeholder,
robot body, dock->bedside interpolation) using the exact same
`SCENE_PRESETS` positions imported from `pybullet_source.py`, so what you
see in the window matches what the headless path is actually simulating,
just rendered live with `p.GUI` instead of captured into numpy frames.

QR overlay compositing (see `pybullet_source.py`'s PR18 docstring) is a 2D
post-render technique applied to captured numpy frames -- it has no
equivalent for a live GUI window, so this demo does not attempt to show
the QR codes. It exists purely so you can *watch* the robot move; for a
full functional walkthrough that actually exercises QR verification and
the safety-gated state machine, use `run_simulated_delivery.py` instead.

Usage (local machine only):
    python -m backend.scripts.run_gui_demo
    python -m backend.scripts.run_gui_demo --steps 200 --speed 2.0
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from perception.pybullet_source import SCENE_PRESETS


def run_demo(preset: str = "delivery", steps: int = 120, speed: float = 1.0) -> None:
    if preset not in SCENE_PRESETS:
        raise ValueError(f"Unknown PyBullet scene preset: {preset!r}")
    if steps < 1:
        raise ValueError("steps must be >= 1")
    if speed <= 0:
        raise ValueError("speed must be > 0")
    dock, bedside = SCENE_PRESETS[preset]

    import pybullet as p
    import pybullet_data

    client_id = p.connect(p.GUI)
    try:
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=client_id)
        p.setGravity(0, 0, -9.8, physicsClientId=client_id)
        p.loadURDF("plane.urdf", physicsClientId=client_id)

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
            basePosition=[bedside[0], bedside[1] + 1.0, bed_half_extents[2]],
            physicsClientId=client_id,
        )

        robot_id = p.loadURDF("r2d2.urdf", basePosition=list(dock), physicsClientId=client_id)

        dock_arr = np.array(dock, dtype=float)
        bedside_arr = np.array(bedside, dtype=float)

        print(f"=== PreCareBot Phase 4 GUIデモ (preset={preset!r}, steps={steps}, speed={speed}x) ===")
        print("PyBulletウィンドウでロボットの動きを確認してください。ウィンドウを閉じるかCtrl+Cで終了します。")

        for step in range(steps):
            t = step / max(steps - 1, 1)
            position = dock_arr + (bedside_arr - dock_arr) * t
            p.resetBasePositionAndOrientation(
                robot_id, position.tolist(), [0, 0, 0, 1], physicsClientId=client_id
            )
            p.stepSimulation(physicsClientId=client_id)

            target = position + np.array([0.0, 0.5, 0.2])
            p.resetDebugVisualizerCamera(
                cameraDistance=2.2,
                cameraYaw=0,
                cameraPitch=-20,
                cameraTargetPosition=target.tolist(),
                physicsClientId=client_id,
            )
            time.sleep(max(0.0, (1.0 / 60.0) / speed))

        print("=== 配送完了（ベッドサイド到着） ===")
        time.sleep(1.5)
    finally:
        p.disconnect(physicsClientId=client_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default="delivery", choices=sorted(SCENE_PRESETS))
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--speed", type=float, default=1.0, help="1.0 = 等速, 2.0 = 2倍速")
    args = parser.parse_args()
    run_demo(preset=args.preset, steps=args.steps, speed=args.speed)


if __name__ == "__main__":
    main()
