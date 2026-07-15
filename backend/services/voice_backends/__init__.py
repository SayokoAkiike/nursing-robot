from .base import VoiceBackend, VoiceTurnResult as VoiceTurnResult
from .zundamon_pipeline import ZundamonPipelineBackend
from .gemini_live import GeminiLiveBackend

_BACKENDS = {
    "ずんだもん": ZundamonPipelineBackend,
    "Gemini Live": GeminiLiveBackend,
}


def get_backend(name: str) -> VoiceBackend:
    if name not in _BACKENDS:
        raise ValueError(f"Unknown backend: {name}")
    return _BACKENDS[name]()
