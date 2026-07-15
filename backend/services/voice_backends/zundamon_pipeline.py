import io
import os
import requests
from faster_whisper import WhisperModel
import google.generativeai as genai

from .base import VoiceBackend, VoiceTurnResult

_SYSTEM_PROMPT = """あなたは病院で夜間巡回をしているケアサポートロボットです。
患者さんへの応答は、丁寧語を保ちつつ、語尾を柔らかく（〜ですね、〜でしょうか、等）、
機械的にならないようにしてください。発話が曖昧な場合は、責めるような聞き方をせず、
親しみやすく聞き返してください。応答は1〜2文程度に簡潔にまとめ、一度に複数の質問を
重ねないようにしてください。明るく、丁寧だけどカジュアルに話しましょう。"""

VOICEVOX_BASE_URL = os.environ.get("VOICEVOX_BASE_URL", "http://localhost:50021")
ZUNDAMON_SPEAKER_ID = 3


class ZundamonPipelineBackend(VoiceBackend):
    def __init__(self):
        self._whisper = WhisperModel("base", device="cpu", compute_type="int8")
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self._llm = genai.GenerativeModel(
            "gemini-3.1-flash-lite", system_instruction=_SYSTEM_PROMPT
        )

    def _transcribe(self, audio_input: bytes) -> str:
        segments, _ = self._whisper.transcribe(io.BytesIO(audio_input), language="ja")
        return "".join(seg.text for seg in segments).strip()

    def _generate_response(self, transcript: str) -> str:
        result = self._llm.generate_content(transcript)
        return result.text.strip()

    def _synthesize(self, text: str) -> bytes:
        query = requests.post(
            f"{VOICEVOX_BASE_URL}/audio_query",
            params={"text": text, "speaker": ZUNDAMON_SPEAKER_ID},
        ).json()
        audio = requests.post(
            f"{VOICEVOX_BASE_URL}/synthesis",
            params={"speaker": ZUNDAMON_SPEAKER_ID},
            json=query,
        )
        return audio.content

    def respond(self, audio_input: bytes) -> VoiceTurnResult:
        transcript = self._transcribe(audio_input)
        response_text = self._generate_response(transcript)
        response_audio = self._synthesize(response_text)
        return VoiceTurnResult(
            transcript=transcript,
            response_text=response_text,
            response_audio=response_audio,
            backend_name="zundamon_pipeline",
        )