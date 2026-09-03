"""Reciter list, passage text/timing, and reference-audio streaming (PRD §6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .db import get_db
from .models import Reciter
from .reference import audio_path_for, passage_payload
from .schemas import PassageOut, ReciterOut

router = APIRouter(prefix="/api", tags=["reciters"])


@router.get("/reciters", response_model=list[ReciterOut])
def list_reciters(db: Session = Depends(get_db)) -> list[ReciterOut]:
    rows = db.query(Reciter).order_by(Reciter.name).all()
    return [
        ReciterOut(id=r.id, slug=r.slug, name=r.name, description=r.description) for r in rows
    ]


@router.get("/passages/fatiha", response_model=PassageOut)
def get_fatiha(reciter_id: int, db: Session = Depends(get_db)) -> PassageOut:
    reciter = db.get(Reciter, reciter_id)
    if reciter is None:
        raise HTTPException(status_code=404, detail="Unknown reciter.")
    audio_url = f"/api/reciters/{reciter.slug}/audio"
    return PassageOut(**passage_payload(reciter.slug, audio_url))


@router.get("/reciters/{slug}/audio", name="reciter_audio")
def reciter_audio(slug: str, db: Session = Depends(get_db)) -> FileResponse:
    reciter = db.query(Reciter).filter_by(slug=slug).one_or_none()
    if reciter is None:
        raise HTTPException(status_code=404, detail="Unknown reciter.")
    path = audio_path_for(slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No reference audio cached for this reciter.")
    # FileResponse handles Range requests, so the browser <audio> element can
    # seek within the reference recitation.
    return FileResponse(path, media_type="audio/wav", filename=f"{slug}-al-fatiha.wav")
