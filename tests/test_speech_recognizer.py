"""Tests for perception/speech_recognizer.py.

The faster-whisper model itself isn't mocked-around in a way that avoids
using the real library -- `WhisperModel` is mocked via monkeypatching
`faster_whisper.WhisperModel` so these tests exercise SpeechRecognizer's
own logic (lazy loading, segment joining, missing-file handling) without
needing to download real model weights or process real audio. A separate,
real (non-mocked) integration test lives in test_run_simulated_rounding.py
using perception/audio_demo/toileting_ja.wav, gated by requiring the demo
file to be present.
"""
from unittest.mock import MagicMock, patch

import pytest

from perception.speech_recognizer import SpeechRecognizer


def _fake_segment(text: str) -> MagicMock:
    seg = MagicMock()
    seg.text = text
    return seg


def test_transcribe_file_missing_file_raises(tmp_path):
    recognizer = SpeechRecognizer()
    with pytest.raises(FileNotFoundError):
        recognizer.transcribe_file(tmp_path / "does-not-exist.wav")


def test_model_not_loaded_until_first_transcribe(tmp_path):
    """Constructing a SpeechRecognizer must be cheap -- the (slow,
    multi-hundred-MB) WhisperModel should not be instantiated until the
    first transcribe_file() call."""
    recognizer = SpeechRecognizer()
    assert recognizer._model is None


@patch("faster_whisper.WhisperModel")
def test_transcribe_file_joins_segments_and_strips(mock_whisper_model_cls, tmp_path):
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"RIFF....WAVEfmt ")  # content irrelevant, model is mocked

    mock_model = MagicMock()
    mock_model.transcribe.return_value = (
        [_fake_segment("トイレに"), _fake_segment("行きたいです")],
        MagicMock(),
    )
    mock_whisper_model_cls.return_value = mock_model

    recognizer = SpeechRecognizer()
    text = recognizer.transcribe_file(wav_path)

    assert text == "トイレに行きたいです"
    mock_model.transcribe.assert_called_once()
    _args, kwargs = mock_model.transcribe.call_args
    assert kwargs.get("language") == "ja"
    assert kwargs.get("vad_filter") is True  # PR32: on by default


@patch("faster_whisper.WhisperModel")
def test_transcribe_file_reuses_loaded_model_across_calls(mock_whisper_model_cls, tmp_path):
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"RIFF....WAVEfmt ")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([_fake_segment("hi")], MagicMock())
    mock_whisper_model_cls.return_value = mock_model

    recognizer = SpeechRecognizer()
    recognizer.transcribe_file(wav_path)
    recognizer.transcribe_file(wav_path)

    mock_whisper_model_cls.assert_called_once()


@patch("faster_whisper.WhisperModel")
def test_transcribe_file_empty_segments_returns_empty_string(mock_whisper_model_cls, tmp_path):
    wav_path = tmp_path / "silence.wav"
    wav_path.write_bytes(b"RIFF....WAVEfmt ")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())
    mock_whisper_model_cls.return_value = mock_model

    recognizer = SpeechRecognizer()
    assert recognizer.transcribe_file(wav_path) == ""


def test_custom_model_size_and_language_passed_through():
    recognizer = SpeechRecognizer(model_size="tiny", language="en")
    assert recognizer.model_size == "tiny"
    assert recognizer.language == "en"


# ---- PR32 (D): model size default + VAD filtering --------------------------


def test_default_model_size_is_medium():
    """PR32 bumped the default from PR29's "small" to "medium" -- a real
    accuracy step up for Japanese, still CPU/int8."""
    recognizer = SpeechRecognizer()
    assert recognizer.model_size == "medium"


def test_vad_filter_enabled_by_default():
    recognizer = SpeechRecognizer()
    assert recognizer.vad_filter is True


@patch("faster_whisper.WhisperModel")
def test_vad_filter_can_be_disabled(mock_whisper_model_cls, tmp_path):
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"RIFF....WAVEfmt ")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([_fake_segment("hi")], MagicMock())
    mock_whisper_model_cls.return_value = mock_model

    recognizer = SpeechRecognizer(vad_filter=False)
    recognizer.transcribe_file(wav_path)

    _args, kwargs = mock_model.transcribe.call_args
    assert kwargs.get("vad_filter") is False
