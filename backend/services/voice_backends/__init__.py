from functools import lru_cache

from backend.core.errors import NotFoundError

from .base import VoiceBackend, VoiceTurnResult as VoiceTurnResult
from .zundamon_pipeline import ZundamonPipelineBackend
from .gemini_live import GeminiLiveBackend

_BACKENDS = {
    "ずんだもん": ZundamonPipelineBackend,
    "Gemini Live": GeminiLiveBackend,
}


@lru_cache
def get_backend(name: str) -> VoiceBackend:
    """Cached per name -- both backends load real models/clients in
    __init__ (Whisper, VOICEVOX/Gemini clients), which would otherwise
    reload on every single HTTP request through routes_voice.py."""
    if name not in _BACKENDS:
        raise NotFoundError(f"Unknown backend: {name}")
    return _BACKENDS[name]()
