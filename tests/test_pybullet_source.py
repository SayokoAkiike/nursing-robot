"""Tests for perception/pybullet_source.py (Phase 4, PR17).

Always uses PyBullet's headless DIRECT mode -- never GUI -- so these run
fine in CI and Codespaces, same as every other test in this suite.
"""
import numpy as np
import pytest

from perception.camera_source import open_source
from perception.pybullet_source import DEFAULT_HEIGHT, DEFAULT_WIDTH, PyBulletSource


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        PyBulletSource(preset="no_such_preset")


def test_steps_must_be_positive():
    with pytest.raises(ValueError):
        PyBulletSource(steps=0)


def test_frames_yields_expected_count_and_shape():
    source = PyBulletSource(preset="delivery", steps=5, width=64, height=48)
    frames = list(source.frames())
    assert len(frames) == 5
    for frame in frames:
        assert frame.shape == (48, 64, 3)
        assert frame.dtype == np.uint8


def test_default_frame_size_matches_module_constants():
    source = PyBulletSource(preset="delivery", steps=2)
    frames = list(source.frames())
    assert frames[0].shape == (DEFAULT_HEIGHT, DEFAULT_WIDTH, 3)


def test_camera_moves_over_time_frames_are_not_identical():
    """The robot moves from dock to bedside across steps, so the rendered
    view should change -- a coarse proxy for "the camera really moved"
    without asserting exact pixel values (which could legitimately vary
    slightly across PyBullet builds/platforms)."""
    source = PyBulletSource(preset="delivery", steps=10, width=64, height=48)
    frames = list(source.frames())
    first, last = frames[0], frames[-1]
    assert not np.array_equal(first, last)


def test_close_is_idempotent():
    source = PyBulletSource(preset="delivery", steps=2, width=64, height=48)
    list(source.frames())
    source.close()
    source.close()  # must not raise


def test_open_source_dispatches_pybullet():
    source = open_source("pybullet:delivery")
    assert isinstance(source, PyBulletSource)
    assert source.preset == "delivery"
    source.close()
