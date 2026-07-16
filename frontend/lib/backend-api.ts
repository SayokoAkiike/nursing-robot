/**
 * Server-only helper: every Route Handler under app/api/ that proxies to
 * the FastAPI backend (backend/main.py) reads the base URL from here,
 * instead of each one hardcoding/re-reading the env var, so there is one
 * place to change if the backend ever moves (e.g. a deployed URL instead
 * of the local dev server).
 */
export function getBackendBaseUrl(): string {
  return process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000";
}
