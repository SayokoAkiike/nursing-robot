"""Tests for perception/camera_source.py."""
import cv2
import numpy as np
import pytest

from perception.camera_source import ImageDirectorySource, VideoFileSource, WebcamSource, open_source


def _write_frame(path, value):
    frame = np.full((20, 20, 3), value, dtype=np.uint8)
    cv2.imwrite(str(path), frame)


def test_image_directory_source_reads_frames_in_sorted_order(tmp_path):
    _write_frame(tmp_path / "0002.png", 200)
    _write_frame(tmp_path / "0001.png", 100)
    _write_frame(tmp_path / "0000.png", 0)

    source = ImageDirectorySource(str(tmp_path))
    frames = list(source.frames())

    assert len(frames) == 3
    # sorted by filename -> 0000, 0001, 0002 -> pixel values 0, 100, 200
    assert [int(f[0, 0, 0]) for f in frames] == [0, 100, 200]


def test_image_directory_source_missing_dir_raises():
    with pytest.raises(FileNotFoundError):
        ImageDirectorySource("/no/such/directory")


def test_video_file_source_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        VideoFileSource("/no/such/video.mp4")


def test_open_source_dispatches_webcam():
    source = open_source("webcam:2")
    assert isinstance(source, WebcamSource)
    assert source.index == 2


def test_open_source_dispatches_directory(tmp_path):
    source = open_source(str(tmp_path))
    assert isinstance(source, ImageDirectorySource)


def test_open_source_dispatches_video_file_path():
    with pytest.raises(FileNotFoundError):
        open_source("/no/such/video.mp4")
