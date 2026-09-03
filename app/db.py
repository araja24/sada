"""SQLAlchemy engine/session wiring for the single SQLite file (PRD §7).

Deliberately thin: `Base` + a `get_db` FastAPI dependency. Models live in
`app/models.py`; schema is created with `Base.metadata.create_all` on
startup (no migration tool -- v1 has one schema).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import settings

# check_same_thread=False: FastAPI may touch a session from a threadpool
# worker. Fine for SQLite here -- one process, low concurrency.
_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    # Import models for their side effect of registering on Base.metadata.
    from . import models  # noqa: F401

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
