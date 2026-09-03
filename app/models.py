"""ORM models -- the SQLite schema from PRD §7 plus the `users` table and
`attempts.user_id` column from docs/adr/0002-user-accounts.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Reciter(Base):
    __tablename__ = "reciters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # Which Quran Foundation chapter-reciter this bundle came from (PRD §7);
    # nullable because a bundle can be built from the public mirror by id.
    qf_recitation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Nullable-shaped so an eventual OAuth-only account fits without a schema
    # change (docs/adr/0002). bcrypt hash; never logged or returned.
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    reciter_id: Mapped[int] = mapped_column(ForeignKey("reciters.id"))
    start_verse: Mapped[int] = mapped_column(Integer)
    end_verse: Mapped[int] = mapped_column(Integer)

    overall_score: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(50))
    sub_scores_json: Mapped[str] = mapped_column(Text)
    per_verse_json: Mapped[str] = mapped_column(Text)
    tips_json: Mapped[str] = mapped_column(Text)
    pitch_overlay_json: Mapped[str] = mapped_column(Text)

    # Path to the retained raw upload on disk, or NULL when retention is off
    # (PRD §7: audio never goes in the DB).
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, index=True)

    reciter: Mapped[Reciter] = relationship(lazy="joined")
