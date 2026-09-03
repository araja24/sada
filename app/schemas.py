"""Pydantic response/request models -- the exact JSON shapes from PRD §6."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Deliberately lax -- just enough to reject obvious non-addresses without
# pulling in the `email-validator` dependency (the stack is kept minimal;
# real deliverability isn't checked since v1 has no email verification).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReciterOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str


class WordOut(BaseModel):
    word_index: int
    arabic_text: str
    start_ms: int
    end_ms: int


class PassageVerseOut(BaseModel):
    verse_number: int
    verse_key: str
    arabic_text: str
    words: list[WordOut]
    start_ms: int
    end_ms: int


class PassageOut(BaseModel):
    reciter_slug: str
    surah: str
    reference_audio_url: str
    verses: list[PassageVerseOut]


class PitchOverlayOut(BaseModel):
    time_axis: list[float]
    reference_semitones: list[float]
    user_semitones_aligned: list[float]


class TipOut(BaseModel):
    verse: int
    word_index: int | None
    type: str
    text: str


class PerVerseOut(BaseModel):
    verse: int
    score: int


class AttemptOut(BaseModel):
    attempt_id: str
    reciter_id: int
    start_verse: int
    end_verse: int
    overall_score: int
    label: str
    sub_scores: dict[str, int]
    per_verse: list[PerVerseOut]
    pitch_overlay: PitchOverlayOut
    tips: list[TipOut]
    created_at: str


class AttemptSummaryOut(BaseModel):
    attempt_id: str
    reciter_id: int
    reciter_slug: str
    start_verse: int
    end_verse: int
    overall_score: int
    label: str
    created_at: str


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v


class UserOut(BaseModel):
    id: int
    email: str


class ErrorOut(BaseModel):
    detail: str
