"""MediaPipe Pose Landmarker wrapper (PR30).

Unlike `perception/speech_recognizer.py` (faster-whisper), the Pose
Landmarker task does NOT auto-download its model weights -- MediaPipe's
Tasks API requires an explicit local `.task` model file path. See
`backend/scripts/download_pose_model.py` for the one-time setup step
this requires (mirrors faster-whisper's one-time download, just not
automatic).

Consumes frames from the existing `perception/camera_source.py`
`FrameSource` classes (`VideoFileSource`, `WebcamSource`,
`ImageDirectorySource`) unchanged -- pose detection needs the exact same
"stream of BGR numpy frames" input QR detection does, so there is no new
frame-source abstraction in this PR, only a new consumer of the existing
one.

Converts MediaPipe's landmark objects into
`backend.services.bed_exit_service.Landmark` (plain x/y/visibility
tuples) so that module stays free of any mediapipe import -- this is the
only file in the codebase that imports mediapipe directly.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.services.bed_exit_service import Landmark

DEFAULT_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)


class PoseDetector:
    """Thin wrapper around `mediapipe.tasks.python.vision.PoseLandmarker`,
    IMAGE running mode (one still frame in, landmarks out -- the caller,
    e.g. `backend/scripts/run_pose_demo.py`, is the one iterating over a
    `FrameSource`'s frames and calling `detect()` once per frame).

    Lazily creates the underlying `PoseLandmarker` on first `detect()`
    call, same reasoning `perception/speech_recognizer.py`'s
    `SpeechRecognizer` lazy-loads its model -- constructing a
    `PoseDetector` must stay cheap.
    """

    def __init__(self, model_path: "str | Path"):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Pose model not found: {self.model_path}. Run "
                "`python -m backend.scripts.download_pose_model` first "
                "(one-time download, requires network access)."
            )
        self._landmarker = None

    def _get_landmarker(self):
        if self._landmarker is None:
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python import vision

            options = vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(self.model_path)),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=1,
            )
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
        return self._landmarker

    def detect(self, frame_bgr: np.ndarray) -> "list[Landmark] | None":
        """`frame_bgr`: one BGR frame, same shape `FrameSource.frames()`
        yields. Returns the 33 landmarks for the first detected person
        (this wrapper is num_poses=1), or None if nobody was detected in
        this frame at all."""
        import mediapipe as mp

        landmarker = self._get_landmarker()
        rgb = frame_bgr[:, :, ::-1]  # BGR (OpenCV/FrameSource convention) -> RGB (mediapipe)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = landmarker.detect(mp_image)

        if not result.pose_landmarks:
            return None
        return [
            Landmark(x=lm.x, y=lm.y, visibility=getattr(lm, "visibility", 1.0))
            for lm in result.pose_landmarks[0]
        ]
