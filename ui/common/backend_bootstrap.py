"""Starts the real FastAPI backend (backend.main:app) in a background
thread, so a single Streamlit Community Cloud deployment can serve the
patient tablet UI, the nurse dashboard, and a rounding-classification demo
page as one process -- Streamlit Cloud hosts exactly one entry point per
deployment, and this project's UI code already talks to the backend over
HTTP (ui/common/api_client.py), so the least invasive way to reuse that
code unmodified is to actually run a real (if in-process) HTTP server
alongside the Streamlit app, rather than rewriting api_client.py to call
service-layer functions directly.

`st.cache_resource` is the deliberate choice here over a plain module-level
flag: Streamlit Cloud can serve multiple concurrent visitors from the same
running container, and `st.cache_resource` is Streamlit's own supported
mechanism for "compute this once, share the result across every session" --
exactly the semantics needed for "start the backend exactly once per
process, no matter how many people are viewing the demo or which page they
land on first". Every entry point (streamlit_app.py and every file under
pages/) calls start_backend() at import time so the backend is guaranteed
running regardless of which page a visitor opens first.
"""
from __future__ import annotations

import os
import threading
import time

import httpx
import streamlit as st

DEMO_BACKEND_PORT = 8000
DEMO_BACKEND_URL = f"http://127.0.0.1:{DEMO_BACKEND_PORT}"

# Holds the running uvicorn.Server instance + its thread, set only by
# start_backend() below. Test-only: tests/test_demo_deployment.py uses
# stop_backend_for_tests() to actually tear this down at the end of that
# file, rather than leaving a real server thread (and the DB/settings
# state it captured at startup) alive for the rest of a 400+ test pytest
# session. The real Streamlit Cloud deployment never calls
# stop_backend_for_tests() -- there, the process's entire lifetime is the
# deployment's lifetime, so "runs forever" is exactly the intended
# behavior; only a test suite that keeps running long after this module's
# own tests finish needs the cleanup path.
_server_holder: dict = {}


@st.cache_resource(show_spinner=False)
def start_backend() -> bool:
    # Demo-only defaults: this deployment is a public, no-real-data sandbox
    # (see docs/DEMO.md), so using the same fixed dev tokens the whole repo
    # already documents in .env.example is fine -- there is nothing sensitive
    # behind them here (unlike a real deployment, where secrets like these
    # would come from Streamlit Cloud's own secrets manager instead).
    os.environ.setdefault("NURSE_TOKEN", "precare-dev-token-2026")
    os.environ.setdefault("ROBOT_TOKEN", "precare-dev-robot-token-2026")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/precare_demo.db")
    os.environ.setdefault("API_BASE_URL", DEMO_BACKEND_URL)

    # Idempotency guard beyond st.cache_resource itself: Streamlit's
    # `AppTest` harness (used by tests/test_demo_deployment.py) doesn't
    # reliably share one cache_resource instance across separate
    # `AppTest.from_file()` calls the way a real running app shares it
    # across browser sessions -- checking liveness first, and only
    # spawning a thread if nothing is actually listening yet, makes this
    # function safe to call from multiple independent contexts without
    # ever attempting a second bind on an already-used port (which would
    # fail loudly in the new thread and, worse, could re-run init_db()
    # against whatever DATABASE_URL happens to be set at that later,
    # unpredictable moment).
    try:
        httpx.get(f"{DEMO_BACKEND_URL}/state", timeout=1.0)
        return True
    except Exception:
        pass

    import uvicorn

    config = uvicorn.Config(
        "backend.main:app",
        host="127.0.0.1",
        port=DEMO_BACKEND_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True, name="precare-demo-backend")
    thread.start()
    _server_holder["server"] = server
    _server_holder["thread"] = thread

    # Block briefly until the backend actually answers, so the very first
    # page a visitor lands on doesn't show a transient "Backend not
    # reachable" error while uvicorn is still binding the port.
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{DEMO_BACKEND_URL}/state", timeout=1.0)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def stop_backend_for_tests() -> None:
    """Test-only cleanup -- see _server_holder's docstring above. Also
    clears start_backend()'s st.cache_resource entry, so a later test (if
    any) that calls start_backend() again gets a genuinely fresh
    attempt rather than a cached "True" pointing at a server that no
    longer exists."""
    server = _server_holder.pop("server", None)
    thread = _server_holder.pop("thread", None)
    if server is not None:
        server.should_exit = True
    if thread is not None:
        thread.join(timeout=5)
    start_backend.clear()
