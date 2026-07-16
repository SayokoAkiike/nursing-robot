"""Small audio container/PCM helpers shared by the voice backends.

Kept separate from any one backend because both `gemini_live.py` (needs raw
16-bit PCM in/out for the Live API) and, potentially, future backends need
the same conversions -- `zundamon_pipeline.py` doesn't need this today since
Whisper and VOICEVOX both consume/produce WAV directly.
"""
import io
import wave

import av


def decode_to_pcm16(audio_bytes: bytes, sample_rate: int) -> bytes:
    """Decode an arbitrary audio container (WAV, WebM/Opus, etc. -- whatever
    the browser's MediaRecorder or a WAV file hands us) into raw, mono,
    16-bit little-endian PCM at `sample_rate` Hz, as required by the Gemini
    Live API's realtime audio input.
    """
    resampler = av.audio.resampler.AudioResampler(
        format="s16", layout="mono", rate=sample_rate
    )
    pcm_chunks = []
    with av.open(io.BytesIO(audio_bytes), mode="r") as container:
        for frame in container.decode(audio=0):
            for resampled in resampler.resample(frame):
                pcm_chunks.append(resampled.to_ndarray().tobytes())
    return b"".join(pcm_chunks)


def pcm16_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    """Wrap raw mono 16-bit PCM (as returned by the Live API) in a WAV
    container, so callers can treat every backend's `response_audio` the
    same way regardless of what produced it."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()
