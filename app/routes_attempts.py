"""Attempt submission + retrieval (PRD §6/§7).

`POST /api/attempts` runs the full analysis pipeline; `GET` endpoints read
stored results scoped to the caller's identity (logged-in user, else guest
session -- docs/adr/0002).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from analysis import pipeline

from . import settings
from .db import get_db
from .models import Attempt, Reciter
from .reference import get_bundle
from .schemas import AttemptOut, AttemptSummaryOut, PerVerseOut, PitchOverlayOut, TipOut
from .security import current_user_id, get_or_create_session_id

router = APIRouter(prefix="/api", tags=["attempts"])

FATIHA_VERSE_COUNT = 7
RECENT_ATTEMPTS_LIMIT = 50


def _validate_verse_range(start_verse: int, end_verse: int) -> None:
    if not (1 <= start_verse <= end_verse <= FATIHA_VERSE_COUNT):
        raise HTTPException(
            status_code=422,
            detail=f"Verse range must be within 1-{FATIHA_VERSE_COUNT}, start before end.",
        )


def _save_upload(audio: UploadFile, data: bytes) -> Path:
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in settings.ACCEPTED_AUDIO_EXTENSIONS:
        suffix = ".webm"  # MediaRecorder's default; the pipeline sniffs content anyway
    settings.ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.ATTEMPTS_DIR / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    return path


def _check_upload_type(audio: UploadFile) -> None:
    content_type = (audio.content_type or "").split(";")[0].strip().lower()
    suffix = Path(audio.filename or "").suffix.lower()
    if content_type in settings.ACCEPTED_AUDIO_CONTENT_TYPES:
        return
    if suffix in settings.ACCEPTED_AUDIO_EXTENSIONS:
        return
    raise HTTPException(
        status_code=415,
        detail="Unsupported audio format. Record in the browser, or upload webm, ogg, wav, mp3, or m4a.",
    )


@router.post("/attempts", response_model=AttemptOut, status_code=201)
async def create_attempt(
    request: Request,
    reciter_id: int = Form(...),
    start_verse: int = Form(...),
    end_verse: int = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AttemptOut:
    session_id = get_or_create_session_id(request)
    user_id = current_user_id(request)

    reciter = db.get(Reciter, reciter_id)
    if reciter is None:
        raise HTTPException(status_code=404, detail="Unknown reciter.")
    _validate_verse_range(start_verse, end_verse)
    _check_upload_type(audio)

    data = await audio.read()
    if len(data) == 0:
        raise HTTPException(status_code=422, detail="The uploaded audio file is empty.")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file is larger than the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    audio_path = _save_upload(audio, data)
    try:
        bundle = get_bundle(reciter.slug)
        result = pipeline.analyze(audio_path, bundle, start_verse, end_verse)
    except pipeline.AnalysisError as exc:
        # PRD §5.10: friendly, actionable message -- not a 500.
        audio_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        audio_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503, detail="This reciter's reference data isn't available right now."
        ) from exc

    attempt = Attempt(
        id=str(uuid.uuid4()),
        session_id=session_id,
        user_id=user_id,
        reciter_id=reciter.id,
        start_verse=start_verse,
        end_verse=end_verse,
        overall_score=result.overall_score,
        label=result.label,
        sub_scores_json=json.dumps(result.sub_scores),
        per_verse_json=json.dumps(result.per_verse),
        tips_json=json.dumps([asdict(t) for t in result.tips]),
        pitch_overlay_json=json.dumps(asdict(result.pitch_overlay)),
        audio_path=str(audio_path) if settings.RETAIN_AUDIO else None,
    )
    if not settings.RETAIN_AUDIO:
        audio_path.unlink(missing_ok=True)

    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_out(attempt)


@router.get("/attempts", response_model=list[AttemptSummaryOut])
def list_attempts(request: Request, db: Session = Depends(get_db)) -> list[AttemptSummaryOut]:
    session_id = get_or_create_session_id(request)
    user_id = current_user_id(request)

    query = db.query(Attempt)
    if user_id is not None:
        query = query.filter(Attempt.user_id == user_id)
    else:
        query = query.filter(Attempt.session_id == session_id, Attempt.user_id.is_(None))
    rows = query.order_by(Attempt.created_at.desc()).limit(RECENT_ATTEMPTS_LIMIT).all()

    return [
        AttemptSummaryOut(
            attempt_id=a.id,
            reciter_id=a.reciter_id,
            reciter_slug=a.reciter.slug,
            start_verse=a.start_verse,
            end_verse=a.end_verse,
            overall_score=a.overall_score,
            label=a.label,
            created_at=a.created_at.isoformat(),
        )
        for a in rows
    ]


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: str, request: Request, db: Session = Depends(get_db)) -> AttemptOut:
    session_id = get_or_create_session_id(request)
    user_id = current_user_id(request)

    attempt = db.get(Attempt, attempt_id)
    if attempt is None or not _caller_owns(attempt, user_id, session_id):
        # Same response whether it doesn't exist or isn't yours.
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return _attempt_out(attempt)


def _caller_owns(attempt: Attempt, user_id: int | None, session_id: str) -> bool:
    if attempt.user_id is not None:
        return attempt.user_id == user_id
    return attempt.session_id == session_id


def _attempt_out(attempt: Attempt) -> AttemptOut:
    return AttemptOut(
        attempt_id=attempt.id,
        reciter_id=attempt.reciter_id,
        start_verse=attempt.start_verse,
        end_verse=attempt.end_verse,
        overall_score=attempt.overall_score,
        label=attempt.label,
        sub_scores=json.loads(attempt.sub_scores_json),
        per_verse=[PerVerseOut(**e) for e in json.loads(attempt.per_verse_json)],
        pitch_overlay=PitchOverlayOut(**json.loads(attempt.pitch_overlay_json)),
        tips=[TipOut(**t) for t in json.loads(attempt.tips_json)],
        created_at=attempt.created_at.isoformat(),
    )
