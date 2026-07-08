"""Tests for vision/qr_detection/demo/generate_synthetic_video.py."""
import json
import os

import cv2

from vision.qr_detection.demo.generate_synthetic_video import generate_video
from vision.qr_detection.demo.synthetic_frames import SceneConfig


def test_generate_video_writes_playable_video_and_metadata(tmp_path):
    config = SceneConfig(seconds_per_code=0.5, fps=8, frame_size=160)
    output = str(tmp_path / "demo.mp4")

    metadata_path = generate_video(config, output)

    assert os.path.exists(output)
    assert os.path.getsize(output) > 0
    assert metadata_path == str(tmp_path / "demo.json")
    assert os.path.exists(metadata_path)

    cap = cv2.VideoCapture(output)
    assert cap.isOpened()
    count = 0
    while True:
        ok, _frame = cap.read()
        if not ok:
            break
        count += 1
    cap.release()
    assert count == config.total_frames

    metadata = json.loads(open(metadata_path, encoding="utf-8").read())
    assert len(metadata["frames"]) == config.total_frames
    assert metadata["frames"][0]["phase"] == "patient"
    assert metadata["frames"][-1]["phase"] == "kit"


def test_generate_video_creates_output_directory(tmp_path):
    config = SceneConfig(seconds_per_code=0.3, fps=5, frame_size=120)
    output = str(tmp_path / "nested" / "dir" / "demo.mp4")

    generate_video(config, output)

    assert os.path.exists(output)


def test_generate_video_custom_metadata_path(tmp_path):
    config = SceneConfig(seconds_per_code=0.3, fps=5, frame_size=120)
    output = str(tmp_path / "demo.mp4")
    metadata_output = str(tmp_path / "custom_meta.json")

    returned_path = generate_video(config, output, metadata_path=metadata_output)

    assert returned_path == metadata_output
    assert os.path.exists(metadata_output)
