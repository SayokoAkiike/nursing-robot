"""SQLAlchemy engine/session management.

Defaults to a local SQLite file (`data/precare.db`) so `pytest` and a plain
`uvicorn backend.main:app` work with zero setup. Set `DATABASE_URL` (see
`.env.example`) to point at the PostgreSQL instance started by
`docker-compose up` instead -- nothing else in the codebase needs to change,
because `backend/db/repositories.py` only ever talks to the ORM models, not
to a specific database.

Tests never touch the module-level engine directly: `tests/conftest.py`'s
`robot_storage` fixture calls `configure_engine()` with a fresh temporary
SQLite file per test -- the same isolation pattern PR1 used for the JSON
storage fixture, just one layer lower.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import get_settings

_engine = None
_SessionLocal = None


def _default_url() -> str:
    settings = get_settings()
    return settings.database_url or "sqlite:///./data/precare.db"


def configure_engine(url: str | None = None):
    """(Re)configure the module-level engine/sessionmaker.

    Called lazily with no arguments on first use (resolving DATABASE_URL /
    the SQLite fallback), and called explicitly by tests to swap in an
    isolated SQLite file.
    """
    global _engine, _SessionLocal
    resolved = url or _default_url()
    connect_args = {"check_same_thread": False} if resolved.startswith("sqlite") else {}
    _engine = create_engine(resolved, future=True, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_engine():
    if _engine is None:
        configure_engine()
    return _engine


def get_session():
    if _SessionLocal is None:
        configure_engine()
    return _SessionLocal()


def init_db() -> None:
    """Create tables if they don't exist yet.

    In production prefer `alembic upgrade head` (see `alembic/`); this is
    mainly a zero-config convenience for SQLite and for tests.
    """
    from backend.db.models import Base

    Base.metadata.create_all(bind=get_engine())

