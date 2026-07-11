"""Tests for perception/pose_detector.py.

Same approach as tests/test_speech_recognizer.py: mediapipe's
PoseLandmarker is mocked so these tests exercise PoseDetector's own
logic (missing-model-file handling, lazy loading, landmark conversion)
without needing the real model file downloaded.
"""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from perception.pose_detector import PoseDetector


def _fake_frame() -> np.ndarray:
    return np.zeros((480, 640, 3), dtype=np.uint8)


def test_missing_model_file_raises_with_clear_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="download_pose_model"):
        PoseDetector(tmp_path / "does-not-exist.task")


def test_model_not_loaded_until_first_detect(tmp_path):
    model_path = tmp_path / "fake.task"
    model_path.write_bytes(b"not a real model")

    detector = PoseDetector(model_path)
    assert detector._landmarker is None


def _fake_landmark(x, y, visibility=1.0):
    lm = MagicMock()
    lm.x = x
    lm.y = y
    lm.visibility = visibility
    return lm


@patch("mediapipe.tasks.python.vision.PoseLandmarker")
@patch("mediapipe.Image")
def test_detect_returns_none_when_no_pose_landmarks(mock_image, mock_landmarker_cls, tmp_path):
    model_path = tmp_path / "fake.task"
    model_path.write_bytes(b"not a real model")

    mock_landmarker = MagicMock()
    mock_result = MagicMock()
    mock_result.pose_landmarks = []
    mock_landmarker.detect.return_value = mock_result
    mock_landmarker_cls.create_from_options.return_value = mock_landmarker

    detector = PoseDetector(model_path)
    assert detector.detect(_fake_frame()) is None


@patch("mediapipe.tasks.python.vision.PoseLandmarker")
@patch("mediapipe.Image")
def test_detect_converts_landmarks_to_plain_dataclass(mock_image, mock_landmarker_cls, tmp_path):
    model_path = tmp_path / "fake.task"
    model_path.write_bytes(b"not a real model")

    mock_landmarker = MagicMock()
    mock_result = MagicMock()
    fake_person = [_fake_landmark(0.1 * i, 0.2 * i, 0.9) for i in range(33)]
    mock_result.pose_landmarks = [fake_person]
    mock_landmarker.detect.return_value = mock_result
    mock_landmarker_cls.create_from_options.return_value = mock_landmarker

    detector = PoseDetector(model_path)
    landmarks = detector.detect(_fake_frame())

    assert landmarks is not None
    assert len(landmarks) == 33
    assert landmarks[24].x == pytest.approx(2.4)
    assert landmarks[24].visibility == pytest.approx(0.9)


@patch("mediapipe.tasks.python.vision.PoseLandmarker")
@patch("mediapipe.Image")
def test_detect_reuses_loaded_landmarker_across_calls(mock_image, mock_landmarker_cls, tmp_path):
    model_path = tmp_path / "fake.task"
    model_path.write_bytes(b"not a real model")

    mock_landmarker = MagicMock()
    mock_result = MagicMock()
    mock_result.pose_landmarks = []
    mock_landmarker.detect.return_value = mock_result
    mock_landmarker_cls.create_from_options.return_value = mock_landmarker

    detector = PoseDetector(model_path)
    detector.detect(_fake_frame())
    detector.detect(_fake_frame())

    mock_landmarker_cls.create_from_options.assert_called_once()
