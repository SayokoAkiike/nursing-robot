"""Tests for perception/qr_detector.py's multi-frame confirmation logic."""
import io

import cv2
import numpy as np
import qrcode
from PIL import Image

from perception.qr_detector import StableQRDetector


def _qr_frame(data: str, box_size: int = 6) -> np.ndarray:
    """Renders `data` as a QR code and returns it as a BGR numpy frame."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    arr = np.array(Image.open(buf))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _blank_frame(size: int = 200) -> np.ndarray:
    return np.full((size, size, 3), 255, dtype=np.uint8)


def test_does_not_confirm_before_threshold():
    detector = StableQRDetector(confirm_frames=3)
    frame = _qr_frame("PATIENT_A_ROOM_203")

    r1 = detector.process_frame(frame)
    r2 = detector.process_frame(frame)
    assert r1.newly_confirmed == []
    assert r2.newly_confirmed == []
    assert detector.confirmed_values == set()


def test_confirms_after_threshold_consecutive_frames():
    detector = StableQRDetector(confirm_frames=3)
    frame = _qr_frame("PATIENT_A_ROOM_203")

    detector.process_frame(frame)
    detector.process_frame(frame)
    r3 = detector.process_frame(frame)

    assert r3.newly_confirmed == ["PATIENT_A_ROOM_203"]
    assert detector.confirmed_values == {"PATIENT_A_ROOM_203"}


def test_confirmed_value_only_reported_once():
    detector = StableQRDetector(confirm_frames=2)
    frame = _qr_frame("KIT_WATER")

    detector.process_frame(frame)
    r2 = detector.process_frame(frame)
    r3 = detector.process_frame(frame)

    assert r2.newly_confirmed == ["KIT_WATER"]
    assert r3.newly_confirmed == []


def test_interrupted_streak_counts_as_unstable_and_resets():
    detector = StableQRDetector(confirm_frames=3)
    frame = _qr_frame("KIT_TOILETING_A")
    blank = _blank_frame()

    detector.process_frame(frame)
    detector.process_frame(frame)  # streak = 2, below threshold
    detector.process_frame(blank)  # interrupted -> unstable, streak reset

    assert detector.unstable_detection_count == 1
    assert detector.confirmed_values == set()

    # Reading resumes and must accumulate a fresh streak from zero.
    detector.process_frame(frame)
    detector.process_frame(frame)
    r = detector.process_frame(frame)
    assert r.newly_confirmed == ["KIT_TOILETING_A"]


def test_blank_frames_do_not_confirm_or_count_as_unstable():
    detector = StableQRDetector(confirm_frames=2)
    blank = _blank_frame()

    detector.process_frame(blank)
    detector.process_frame(blank)

    assert detector.confirmed_values == set()
    assert detector.unstable_detection_count == 0


def test_confirm_frames_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        StableQRDetector(confirm_frames=0)
