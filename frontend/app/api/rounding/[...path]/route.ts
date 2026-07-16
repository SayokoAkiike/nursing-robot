import { NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/lib/backend-api";

/**
 * Thin proxy for every backend/api/routes_rounding.py endpoint
 * (/rounding/start, /rounding/{id}, /rounding/{id}/detect-patient,
 * /rounding/{id}/start-interaction, /rounding/{id}/classify-need,
 * /rounding/{id}/provide-information, /rounding/{id}/escalate,
 * /rounding/{id}/require-delivery) -- one catch-all route instead of one
 * file per endpoint, since every one of them is the same shape: forward
 * method + JSON body to `${BACKEND_API_BASE_URL}/rounding/<path>` and
 * relay the response back verbatim.
 *
 * /escalate is nurse-authenticated (see routes_rounding.py's module
 * docstring), so this route attaches x-nurse-token itself -- the token
 * lives server-side only (NURSE_TOKEN env var), the same demo default the
 * rest of the repo already documents in .env.example, never shipped to
 * the browser.
 */
const NURSE_TOKEN = process.env.NURSE_TOKEN ?? "precare-dev-token-2026";

async function proxy(request: Request, path: string[]): Promise<NextResponse> {
  const url = `${getBackendBaseUrl()}/rounding/${path.join("/")}`;
  const init: RequestInit = {
    method: request.method,
    headers: {
      "Content-Type": "application/json",
      "x-nurse-token": NURSE_TOKEN,
    },
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    const bodyText = await request.text();
    init.body = bodyText || "{}";
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, init);
  } catch {
    return NextResponse.json(
      { error: "バックエンドAPIに接続できませんでした。FastAPIサーバーが起動しているか確認してください。" },
      { status: 502 },
    );
  }

  const body = await upstream.json().catch(() => ({}));
  return NextResponse.json(body, { status: upstream.status });
}

type RouteParams = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, { params }: RouteParams) {
  const { path } = await params;
  return proxy(request, path);
}

export async function POST(request: Request, { params }: RouteParams) {
  const { path } = await params;
  return proxy(request, path);
}
