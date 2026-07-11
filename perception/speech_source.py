"""Audio input sources for the rounding workflow's speech recognition
(PR29), mirroring `perception/camera_source.py`'s role for QR detection:
a small abstraction so `speech_recognizer.py` doesn't care whether the
audio came from an existing WAV file or a live microphone.

Neither class here ever writes audio into `care_requests`,
`patient_interactions`, or any other DB table -- only the *text* that
`speech_recognizer.transcribe_file()` returns gets persisted downstream
(same `patient_interactions.patient_response` column simulated/manual
input already writes to). `WavFileSpeechSource` never writes audio at
all (it only reads a file the caller already has); `MicrophoneSpeechSource`
writes one ephemeral temp file per recording, which the caller is
expected to delete immediately after transcription (see
`backend/scripts/run_simulated_rounding.py`'s `--microphone` handling).
"""
from __future__ import annotations

import tempfile
import wave
from pathlib import Path


class WavFileSpeechSource:
    """An already-existing WAV file on disk. Never writes anything --
    just validates the path exists so callers get a clear error before
    handing it to faster-whisper."""

    def __init__(self, path: "str | Path"):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Audio file not found: {self.path}")

    def get_path(self) -> Path:
        return self.path


class MicrophoneSpeechSource:
    """Records `duration_seconds` from the local microphone.

    Local-only: importing `sounddevice` is deferred to __init__ (not
    module level), so merely importing this module never fails in a
    headless/Codespaces environment -- only *constructing* this class
    does, with a clear error pointing at `WavFileSpeechSource` instead.
    This is the same reasoning `ui/patient_request_app`'s eventual
    webcam-only features would need; the QR side already documents the
    identical limitation for `WebcamSource` in the README.
    """

    def __init__(self, duration_seconds: float = 5.0, sample_rate: int = 16000):
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                "Microphone input requires the 'sounddevice' package and a "
                "local audio input device. This is not available in "
                "Codespaces or other headless/CI environments -- use "
                "WavFileSpeechSource with a pre-recorded file instead."
            ) from exc
        self._sd = sd
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate

    def record_to_temp_file(self) -> Path:
        """Records once, writes exactly one ephemeral WAV file, and
        returns its path. The caller (not this class) is responsible for
        deleting it once transcription is done -- kept explicit rather
        than auto-deleting here so a caller that wants to keep the file
        for debugging can still choose to."""
        frames = self._sd.rec(
            int(self.duration_seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
        )
        self._sd.wait()

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(frames.tobytes())
        return Path(tmp.name)
