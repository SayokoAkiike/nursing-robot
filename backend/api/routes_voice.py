"""Voice backend endpoint.

Wraps a single `VoiceBackend.respond()` call (audio in, transcript/reply
text/reply audio out) behind HTTP, so the Next.js frontend's Route Handler
(`frontend/app/api/voice/respond/route.ts`) can proxy a recorded patient
utterance to whichever engine (ずんだもん / Gemini Live) the UI has selected,
the same way `backend/scripts/test_zundamon_pipeline.py` already calls
`get_backend()` directly for the CLI/Streamlit demos.
"""
import base64

from fastapi import APIRouter, Form, UploadFile

from backend.services.voice_backends import get_backend

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/respond")
def respond(audio: UploadFile, backend: str = Form(...)):
    # Deliberately a sync def, not async: FastAPI runs sync path operations
    # in a worker thread, which GeminiLiveBackend.respond() needs -- it
    # calls asyncio.run() internally, which raises if invoked from a thread
    # that already has a running event loop (i.e. from an async def handler
    # here).
    audio_bytes = audio.file.read()
    voice_backend = get_backend(backend)
    result = voice_backend.respond(audio_bytes)
    return {
        "transcript": result.transcript,
        "response_text": result.response_text,
        "response_audio_base64": base64.b64encode(result.response_audio).decode("ascii"),
        "backend_name": result.backend_name,
    }
