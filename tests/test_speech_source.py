"""Tests for perception/speech_source.py.

WavFileSpeechSource tests use a tiny synthetic WAV built with the stdlib
`wave` module (a few hundred ms of silence) -- no real speech content or
external TTS tool needed to test file-handling logic, same principle as
`perception/pybullet_source.py`'s tests not needing a real physical robot.
"""
import wave
from pathlib import Path

import pytest

from perception.speech_source import MicrophoneSpeechSource, WavFileSpeechSource


def _write_silent_wav(path: Path, duration_seconds: float = 0.2, sample_rate: int = 16000) -> None:
    n_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


def test_wav_file_speech_source_reads_existing_file(tmp_path):
    wav_path = tmp_path / "test.wav"
    _write_silent_wav(wav_path)

    source = WavFileSpeechSource(wav_path)
    assert source.get_path() == wav_path


def test_wav_file_speech_source_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        WavFileSpeechSource(tmp_path / "does-not-exist.wav")


def test_wav_file_speech_source_accepts_string_path(tmp_path):
    wav_path = tmp_path / "test.wav"
    _write_silent_wav(wav_path)

    source = WavFileSpeechSource(str(wav_path))
    assert source.get_path() == wav_path


def test_microphone_speech_source_raises_clear_error_without_sounddevice(monkeypatch):
    """sounddevice isn't in requirements.txt by default (optional,
    local-only -- see requirements.txt's PR29 comment), so importing it
    should fail in this test environment same as it would in Codespaces/
    CI, and MicrophoneSpeechSource must turn that into a clear
    RuntimeError rather than a raw ImportError/ModuleNotFoundError."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sounddevice":
            raise ModuleNotFoundError("No module named 'sounddevice'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="sounddevice"):
        MicrophoneSpeechSource()
