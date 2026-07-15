import { NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/lib/backend-api";

/**
 * Proxies one recorded utterance to the FastAPI backend's
 * POST /voice/respond (backend/api/routes_voice.py), which runs it through
 * whichever VoiceBackend (ずんだもん / Gemini Live) the UI selected and
 * returns the transcript, reply text, and reply audio in one round trip.
 *
 * A Route Handler (rather than calling the backend directly from the
 * browser) keeps BACKEND_API_BASE_URL server-side only and sidesteps CORS
 * entirely -- the browser only ever talks to this same-origin route.
 */
export async function POST(request: Request) {
  const formData = await request.formData();
  const audio = formData.get("audio");
  const backend = formData.get("backend");

  if (!(audio instanceof Blob) || typeof backend !== "string" || !backend) {
    return NextResponse.json(
      { error: "audio (file) and backend (name) are required" },
      { status: 400 },
    );
  }

  const upstreamForm = new FormData();
  upstreamForm.append("audio", audio, "recording.webm");
  upstreamForm.append("backend", backend);

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(`${getBackendBaseUrl()}/voice/respond`, {
      method: "POST",
      body: upstreamForm,
    });
  } catch {
    return NextResponse.json(
      { error: "バックエンドAPIに接続できませんでした。FastAPIサーバーが起動しているか確認してください。" },
      { status: 502 },
    );
  }

  const body = await upstreamResponse.json();
  return NextResponse.json(body, { status: upstreamResponse.status });
}
