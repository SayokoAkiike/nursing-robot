from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VoiceTurnResult:
    transcript: str
    response_text: str
    response_audio: bytes
    backend_name: str


class VoiceBackend(ABC):
    @abstractmethod
    def respond(self, audio_input: bytes) -> VoiceTurnResult:
        ...