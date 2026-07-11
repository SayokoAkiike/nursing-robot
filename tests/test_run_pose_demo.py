"""Integration tests for backend/scripts/run_pose_demo.py.

Mocks `PoseDetector.detect()` to return a scripted sequence of landmark
results (in-bed, then confirm_frames-worth of fall_risk) rather than
running real MediaPipe against real video -- same reasoning
test_pose_detector.py mocks the underlying PoseLandmarker: this file
tests run_pose_demo's own orchestration logic (the debounce counter, the
HTTP report call), not pose-estimation accuracy.

Uses a tiny directory of blank PNG frames as the `--source` (mirrors how
perception's own test suite feeds `ImageDirectorySource` for QR
detection) so `open_source()` needs no mocking of its own -- only
`PoseDetector.detect()` is mocked.
"""
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.scripts.run_pose_demo import run
from backend.services.bed_exit_service import BedRegion, Landmark

BED = BedRegion(x_min=0.2, y_min=0.5, x_max=0.8, y_max=1.0)


def _client():
    from backend.main import app

    return TestClient(app)


def _make_frame_dir(tmp_path, n_frames=10):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    for i in range(n_frames):
        cv2.imwrite(str(frame_dir / f"frame_{i:03d}.png"), blank)
    return frame_dir


def _in_bed_landmarks() -> list[Landmark]:
    landmarks = [Landmark(0.5, 0.5, 1.0) for _ in range(33)]
    landmarks[23] = Landmark(0.45, 0.7, 1.0)
    landmarks[24] = Landmark(0.55, 0.7, 1.0)
    return landmarks


def _fall_risk_landmarks() -> list[Landmark]:
    landmarks = [Landmark(0.5, 0.5, 1.0) for _ in range(33)]
    landmarks[23] = Landmark(0.05, 0.1, 1.0)
    landmarks[24] = Landmark(0.1, 0.1, 1.0)
    return landmarks


def test_confirmed_fall_risk_reports_escalation(tmp_path, robot_storage):
    frame_dir = _make_frame_dir(tmp_path, n_frames=10)
    # 2 in-bed frames, then 5 consecutive fall_risk frames (>= confirm_frames=3).
    sequence = [_in_bed_landmarks(), _in_bed_landmarks()] + [_fall_risk_landmarks()] * 5

    with patch("backend.scripts.run_pose_demo.PoseDetector") as mock_detector_cls:
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.side_effect = sequence

        result = run(
            source_spec=str(frame_dir),
            bed_region=BED,
            room="203",
            patient_id="PATIENT_A_ROOM_203",
            confirm_frames=3,
            client=_client(),
        )

    assert result is not None
    assert result["status"] == "PENDING"
    assert result["source"] == "vision_pose"
    assert result["room"] == "203"


def test_intermittent_fall_risk_does_not_reach_confirm_threshold(tmp_path, robot_storage):
    """A single noisy frame between in-bed frames must reset the
    consecutive counter -- this is the whole point of debouncing.

    Uses a fall_risk position offset only on the x-axis (just outside
    BED's x_min) at the same y as the in-bed position -- keeps vertical
    velocity near zero between alternating frames, so this test
    exercises the confirm_frames debounce specifically, independent of
    PR33's MotionTracker (which would otherwise also flag the same
    large, fast alternation as genuine sudden motion -- correctly, but
    that's a different behavior than this test means to cover)."""
    frame_dir = _make_frame_dir(tmp_path, n_frames=5)

    def _mild_fall_risk_landmarks() -> list[Landmark]:
        landmarks = [Landmark(0.5, 0.5, 1.0) for _ in range(33)]
        landmarks[23] = Landmark(0.05, 0.7, 1.0)
        landmarks[24] = Landmark(0.1, 0.7, 1.0)
        return landmarks

    sequence = [
        _mild_fall_risk_landmarks(),
        _in_bed_landmarks(),  # resets the counter
        _mild_fall_risk_landmarks(),
        _in_bed_landmarks(),  # resets again
        _mild_fall_risk_landmarks(),
    ]

    with patch("backend.scripts.run_pose_demo.PoseDetector") as mock_detector_cls:
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.side_effect = sequence

        result = run(
            source_spec=str(frame_dir),
            bed_region=BED,
            room="203",
            patient_id="PATIENT_A_ROOM_203",
            confirm_frames=3,
            client=_client(),
        )

    assert result is None


def test_all_in_bed_never_reports(tmp_path, robot_storage):
    frame_dir = _make_frame_dir(tmp_path, n_frames=5)

    with patch("backend.scripts.run_pose_demo.PoseDetector") as mock_detector_cls:
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.return_value = _in_bed_landmarks()

        result = run(
            source_spec=str(frame_dir),
            bed_region=BED,
            room="203",
            patient_id="PATIENT_A_ROOM_203",
            confirm_frames=3,
            client=_client(),
        )

    assert result is None


# ---- PR33 (C): MotionTracker integration -------------------------------------


def test_sudden_vertical_motion_upgrades_static_in_bed_to_fall_risk(tmp_path, robot_storage):
    """A rapid downward jump between frames -- even while the *first*
    post-jump frame's static hip position is still technically inside
    the bed region's box -- must be confirmed as fall_risk once combined
    with the motion signal. Realistic follow-through: after the fall the
    person ends up on the floor, outside the bed region entirely, which
    the static check alone picks up for the remaining confirm_frames --
    this mirrors how a real fall actually looks (a brief fast motion,
    then a settled off-bed position), rather than staying suspended
    exactly at the bed's boundary."""
    frame_dir = _make_frame_dir(tmp_path, n_frames=5)

    def _landmarks_at(x: float, y: float) -> list[Landmark]:
        landmarks = [Landmark(0.5, 0.5, 1.0) for _ in range(33)]
        landmarks[23] = Landmark(x - 0.05, y, 1.0)
        landmarks[24] = Landmark(x + 0.05, y, 1.0)
        return landmarks

    # Frame 1: settled in bed. Frame 2: fast jump, but still just inside
    # BED's box (y=0.95 < y_max=1.0) -- only the motion signal should
    # catch this one. Frames 3-4: now off the bed entirely (y=1.05) --
    # the static check alone confirms from here.
    sequence = [
        _landmarks_at(0.5, 0.55),
        _landmarks_at(0.5, 0.95),
        _landmarks_at(0.5, 1.05),
        _landmarks_at(0.5, 1.05),
    ]

    with patch("backend.scripts.run_pose_demo.PoseDetector") as mock_detector_cls:
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.side_effect = sequence

        result = run(
            source_spec=str(frame_dir),
            bed_region=BED,
            room="203",
            patient_id="PATIENT_A_ROOM_203",
            confirm_frames=3,
            client=_client(),
        )

    assert result is not None
    assert result["status"] == "PENDING"


def test_gap_in_tracking_resets_motion_history(tmp_path, robot_storage):
    """No person detected for a frame must reset the motion trace --
    otherwise a person leaving and a *different*, unrelated re-entry
    could be misread as one continuous fast motion between the last
    seen position and the new one."""
    frame_dir = _make_frame_dir(tmp_path, n_frames=5)

    def _no_person() -> None:
        return None

    def _in_bed_at(y: float) -> list[Landmark]:
        landmarks = [Landmark(0.5, 0.5, 1.0) for _ in range(33)]
        landmarks[23] = Landmark(0.45, y, 1.0)
        landmarks[24] = Landmark(0.55, y, 1.0)
        return landmarks

    # A big vertical gap, but with a "nobody detected" frame in between --
    # should NOT be read as continuous motion.
    sequence = [_in_bed_at(0.55), _no_person(), _in_bed_at(0.95), _in_bed_at(0.95), _in_bed_at(0.95)]

    with patch("backend.scripts.run_pose_demo.PoseDetector") as mock_detector_cls:
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.side_effect = sequence

        result = run(
            source_spec=str(frame_dir),
            bed_region=BED,
            room="203",
            patient_id="PATIENT_A_ROOM_203",
            confirm_frames=3,
            client=_client(),
        )

    # Both are within BED's y-range, so no static fall_risk either --
    # confirms the motion reset actually took effect (result should be
    # None, not an escalation from a phantom velocity spike).
    assert result is None
