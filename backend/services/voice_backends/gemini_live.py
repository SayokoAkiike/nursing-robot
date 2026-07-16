import asyncio
import os

from google import genai
from google.genai import types

from .audio_convert import decode_to_pcm16, pcm16_to_wav
from .base import VoiceBackend, VoiceTurnResult

_SYSTEM_PROMPT = """あなたは病院で夜間巡回をしているケアサポートロボットです。
患者さんへの応答は、丁寧語を保ちつつ、語尾を柔らかく（〜ですね、〜でしょうか、等）、
機械的にならないようにしてください。"""

# Live APIの音声対話モデル。テキストのみのgemini-3.1-flash-liteとは異なり、
# 音声入力→音声出力（Speech-to-Speech）にネイティブ対応している。
_MODEL = "gemini-3.1-flash-live-preview"

# Live APIの音声入出力は固定フォーマット（16-bit PCM, リトルエンディアン）。
# 入力は16kHz、出力は24kHzで固定。
_INPUT_SAMPLE_RATE = 16000
_OUTPUT_SAMPLE_RATE = 24000


class GeminiLiveBackend(VoiceBackend):
    def __init__(self):
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def respond(self, audio_input: bytes) -> VoiceTurnResult:
        return asyncio.run(self._respond_async(audio_input))

    async def _respond_async(self, audio_input: bytes) -> VoiceTurnResult:
        pcm_input = decode_to_pcm16(audio_input, _INPUT_SAMPLE_RATE)

        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=_SYSTEM_PROMPT,
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        transcript_parts: list[str] = []
        response_text_parts: list[str] = []
        audio_chunks: list[bytes] = []

        async with self._client.aio.live.connect(model=_MODEL, config=config) as session:
            await session.send_realtime_input(
                audio=types.Blob(
                    data=pcm_input, mime_type=f"audio/pcm;rate={_INPUT_SAMPLE_RATE}"
                )
            )
            await session.send_realtime_input(audio_stream_end=True)

            async for message in session.receive():
                content = message.server_content
                if content is None:
                    continue
                if content.input_transcription and content.input_transcription.text:
                    transcript_parts.append(content.input_transcription.text)
                if content.output_transcription and content.output_transcription.text:
                    response_text_parts.append(content.output_transcription.text)
                if content.model_turn:
                    for part in content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_chunks.append(part.inline_data.data)
                if content.turn_complete:
                    break

        response_audio = pcm16_to_wav(b"".join(audio_chunks), _OUTPUT_SAMPLE_RATE)
        return VoiceTurnResult(
            transcript="".join(transcript_parts).strip(),
            response_text="".join(response_text_parts).strip(),
            response_audio=response_audio,
            backend_name="gemini_live",
        )
