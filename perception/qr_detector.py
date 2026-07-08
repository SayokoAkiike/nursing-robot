"""Multi-frame QR confirmation.

`vision/qr_detection/read_qr.py` decodes a single still frame. In a real
bedside-delivery scenario a single frame is not trustworthy evidence:
motion blur, glare, or a QR code only partially in view can produce a
false read (or, worse, a *wrong* read that happens to decode cleanly).
This module requires the same value to be read on `confirm_frames`
consecutive frames before treating it as confirmed, and separately tracks
how often a candidate reading was interrupted before reaching that
threshold (`unstable_detection_count`) -- a metric the PR6 evaluation
benchmark is expected to consume directly.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class DetectorResult:
    newly_confirmed: list[str]
    seen_this_frame: list[str]


class StableQRDetector:
    def __init__(self, confirm_frames: int = 3):
        if confirm_frames < 1:
            raise ValueError("confirm_frames must be >= 1")
        self.confirm_frames = confirm_frames
        self._cv2_detector = cv2.QRCodeDetector()
        self._streaks: dict[str, int] = {}
        self._confirmed: set[str] = set()
        self.unstable_detection_count = 0
        self.frames_processed = 0

    def _decode_frame(self, frame: np.ndarray) -> list[str]:
        """Decode zero or more QR codes present in a single frame."""
        try:
            ok, decoded_info, _points, _straight = self._cv2_detector.detectAndDecodeMulti(frame)
        except cv2.error:
            ok, decoded_info = False, ()
        if ok and decoded_info:
            values = [v for v in decoded_info if v]
            if values:
                return values
        # Fall back to the single-QR path: detectAndDecodeMulti can fail to
        # report anything on some OpenCV builds when exactly one QR code is
        # present in the frame.
        data, _points, _ = self._cv2_detector.detectAndDecode(frame)
        return [data] if data else []

    def process_frame(self, frame: np.ndarray) -> DetectorResult:
        self.frames_processed += 1
        seen = set(self._decode_frame(frame))

        for value in list(self._streaks):
            if value not in seen:
                if 0 < self._streaks[value] < self.confirm_frames:
                    self.unstable_detection_count += 1
                del self._streaks[value]

        for value in seen:
            self._streaks[value] = self._streaks.get(value, 0) + 1

        newly_confirmed = []
        for value, count in self._streaks.items():
            if count >= self.confirm_frames and value not in self._confirmed:
                self._confirmed.add(value)
                newly_confirmed.append(value)

        return DetectorResult(newly_confirmed=newly_confirmed, seen_this_frame=sorted(seen))

    @property
    def confirmed_values(self) -> set[str]:
        return set(self._confirmed)
