"""Offline speech-to-text for the rounding workflow (PR29), via
faster-whisper (CTranslate2-based, runs on CPU, no network call at
inference time beyond the one-time model weight download from Hugging
Face on first use).

This is deliberately offline/self-hosted rather than a cloud STT API: a
real deployment must never send actual patient audio to a third-party
service, and even for this prototype's synthetic demo audio, "no
external dependency at inference time, no API key, works the same for
anyone who clones the repo" matters more than the accuracy edge a hosted
API might have. See the project's own privacy-by-design pattern in
`backend/services/rounding_service.py`'s module docstring and README's
Current Limitations for the same reasoning applied elsewhere.

Never persists audio: `SpeechRecognizer.transcribe_file()` only reads an
existing file and returns text -- it does not write, copy, or cache the
audio itself anywhere. Only the returned text is meant to flow into
`patient_interactions.patient_response`, exactly like the "simulated" /
"manual" input modes already do.

PR32 (D): two accuracy improvements over PR29's original "small" model,
no-VAD baseline --

  - DEFAULT_MODEL_SIZE bumped to "medium". Still runs CPU/int8 (no GPU
    assumed), noticeably slower to load/transcribe than "small" but a
    real accuracy step up for Japanese; still configurable per-instance
    for anyone who wants to trade back down for speed.
  - vad_filter=True by default: faster-whisper bundles Silero VAD
    (no extra dependency -- it ships inside the faster-whisper package
    itself), which strips leading/trailing/internal silence before
    transcription. This matters specifically for this project's use
    case: a live rounding conversation's recording will have real
    silence around the actual answer (the patient pausing before/after
    speaking), and transcribing silence both wastes CPU time and is a
    source of hallucinated text in Whisper-family models.
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_MODEL_SIZE = "medium"
DEFAULT_LANGUAGE = "ja"
DEFAULT_VAD_FILTER = True


class SpeechRecognizer:
    """Thin wrapper around `faster_whisper.WhisperModel`.

    The model is loaded lazily on first `transcribe_file()` call, not in
    `__init__` -- constructing a `SpeechRecognizer` (e.g. to pass one
    around before deciding whether it'll actually be used) must stay
    cheap; only actually transcribing should pay the multi-hundred-MB
    model load cost.
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        language: str = DEFAULT_LANGUAGE,
        vad_filter: bool = DEFAULT_VAD_FILTER,
    ):
        self.model_size = model_size
        self.language = language
        self.vad_filter = vad_filter
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe_file(self, audio_path: "str | Path") -> str:
        """Transcribes an existing audio file and returns the
        recognized text (stripped, segments joined with no separator --
        faster-whisper's segments already include their own leading
        space where appropriate). Returns "" for silence/no speech
        detected rather than raising, matching
        `need_classification_service.classify()`'s own "never raises on
        an unrecognized/empty response, falls through to 'unknown'"
        contract -- a rounding session shouldn't error out just because
        nothing was said (and with vad_filter=True, "nothing was said"
        is exactly what an all-silence recording now correctly resolves
        to, rather than a hallucinated phrase)."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        model = self._get_model()
        segments, _info = model.transcribe(
            str(path), language=self.language, vad_filter=self.vad_filter
        )
        return "".join(segment.text for segment in segments).strip()
