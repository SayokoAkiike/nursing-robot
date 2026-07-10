from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import (
    routes_analytics,
    routes_domain,
    routes_escalations,
    routes_logs,
    routes_requests,
    routes_rounding,
    routes_tasks,
    routes_verification,
)
from backend.core.config import get_settings
from backend.core.errors import DomainError
from backend.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on boot if they don't exist yet.

    A convenience for SQLite/local dev; in a real PostgreSQL deployment,
    prefer running `alembic upgrade head` explicitly as part of the deploy
    step instead of relying on this.
    """
    init_db()
    yield


app = FastAPI(title="PreCare Dock API", version="0.5.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "x-nurse-token"],
)


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError):
    """Single place mapping domain errors to HTTP responses.

    Route handlers no longer catch ValueError / pattern-match error strings
    to decide a status code -- each service raises the typed error
    (NotFoundError, ConflictError, ForbiddenError, or plain DomainError) that
    already carries the right `status_code`.
    """
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


app.include_router(routes_requests.router)
app.include_router(routes_tasks.router)
app.include_router(routes_verification.router)
app.include_router(routes_logs.router)
app.include_router(routes_analytics.router)
app.include_router(routes_rounding.router)
app.include_router(routes_escalations.router)
app.include_router(routes_domain.router)

