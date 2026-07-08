"""Frame sources for the perception pipeline.

Abstracts over where camera frames come from so `qr_detector` /
`run_perception` don't need to know whether they're reading a live webcam,
a recorded video file (e.g. the synthetic QR demo video planned for PR5),
or a plain directory of image frames (handy for tests and for scripted
demos without needing an encoded video file at all).
"""
from __future__ import annotations

import glob
import os
from typing import Iterator

import cv2
import numpy as np


class FrameSource:
    """Base class: iterate over BGR numpy frames."""

    def frames(self) -> Iterator[np.ndarray]:
        raise NotImplementedError

    def __iter__(self) -> Iterator[np.ndarray]:
        return self.frames()

    def close(self) -> None:
        pass


class VideoFileSource(FrameSource):
    """Reads frames from a video file (e.g. the PR5 synthetic QR demo)."""

    def __init__(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Video file not found: {path}")
        self.path = path
        self._cap = None

    def frames(self) -> Iterator[np.ndarray]:
        self._cap = cv2.VideoCapture(self.path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open video file: {self.path}")
        try:
            while True:
                ok, frame = self._cap.read()
                if not ok:
                    break
                yield frame
        finally:
            self._cap.release()
            self._cap = None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class ImageDirectorySource(FrameSource):
    """Reads a sorted sequence of image files from a directory.

    Useful for tests and for any demo material shipped as still frames
    instead of an encoded video.
    """

    def __init__(self, directory: str, pattern: str = "*.png"):
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Frame directory not found: {directory}")
        self.directory = directory
        self.pattern = pattern

    def frames(self) -> Iterator[np.ndarray]:
        paths = sorted(glob.glob(os.path.join(self.directory, self.pattern)))
        for path in paths:
            frame = cv2.imread(path)
            if frame is not None:
                yield frame


class WebcamSource(FrameSource):
    """Reads live frames from a webcam device.

    Not usable in headless environments such as GitHub Codespaces (no
    camera device attached) -- kept for completeness / local hardware use,
    mirroring the existing caveat in `vision/qr_detection/read_qr.py`.
    """

    def __init__(self, index: int = 0):
        self.index = index
        self._cap = None

    def frames(self) -> Iterator[np.ndarray]:
        self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open camera index {self.index} "
                "(expected in headless environments such as Codespaces)"
            )
        try:
            while True:
                ok, frame = self._cap.read()
                if not ok:
                    break
                yield frame
        finally:
            self._cap.release()
            self._cap = None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def open_source(spec: str) -> FrameSource:
    """Parse a --source CLI argument into a FrameSource.

    Accepted forms:
      "webcam:0"      -> WebcamSource(0)
      "/path/to/dir"  -> ImageDirectorySource(...)
      "/path/to.mp4"  -> VideoFileSource(...)
    """
    if spec.startswith("webcam:"):
        return WebcamSource(int(spec.split(":", 1)[1]))
    if os.path.isdir(spec):
        return ImageDirectorySource(spec)
    return VideoFileSource(spec)
