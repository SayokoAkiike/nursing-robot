import os
import google.generativeai as genai

from .base import VoiceBackend, VoiceTurnResult

_SYSTEM_PROMPT = """あなたは病院で夜間巡回をしているケアサポートロボットです。
患者さんへの応答は、丁寧語を保ちつつ、語尾を柔らかく（〜ですね、〜でしょうか、等）、
機械的にならないようにしてください。"""


class GeminiLiveBackend(VoiceBackend):
    def __init__(self):
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self._model = genai.GenerativeModel(
            "gemini-3.1-flash-lite", system_instruction=_SYSTEM_PROMPT
        )

    def respond(self, audio_input: bytes) -> VoiceTurnResult:
        # まずは音声入力→テキスト応答の簡易版として実装（音声出力は後続で追加）
        audio_part = {"mime_type": "audio/wav", "data": audio_input}
        result = self._model.generate_content(
            [audio_part, "この発話に日本語で応答してください。"]
        )
        response_text = result.text.strip()
        return VoiceTurnResult(
            transcript="(Geminiが音声を直接解釈)",
            response_text=response_text,
            response_audio=b"",
            backend_name="gemini_live",
        )
