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
    consecutive counter -- this is the whole point of debouncing."""
    frame_dir = _make_frame_dir(tmp_path, n_frames=5)
    sequence = [
        _fall_risk_landmarks(),
        _in_bed_landmarks(),  # resets the counter
        _fall_risk_landmarks(),
        _in_bed_landmarks(),  # resets again
        _fall_risk_landmarks(),
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
