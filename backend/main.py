from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
 
from backend.api import routes_logs, routes_requests, routes_tasks, routes_verification
from backend.core.config import get_settings
from backend.core.errors import DomainError
 
app = FastAPI(title="PreCare Dock API", version="0.4.0")
 
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
 
