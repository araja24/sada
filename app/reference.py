"""Reference-bundle glue between the cached M1 files and the API.

The heavy lifting (loading features, slicing verse ranges, scoring) is in
`analysis.pipeline`. This module only:

- discovers which reciter bundles exist on disk and seeds the `reciters`
  table from them,
- caches the loaded `ReferenceBundle` per slug (features.npz is a few MB;
  loading it per request would be wasteful -- PRD §3),
- assembles the `/api/passages/fatiha` payload by merging the cached
  Arabic text (passage.json) with the cached timing (timestamps.json).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from analysis import pipeline

from . import settings
from .models import Reciter


def _bundle_dirs() -> list[Path]:
    if not settings.REFERENCE_DIR.is_dir():
        return []
    return sorted(
        p for p in settings.REFERENCE_DIR.iterdir()
        if (p / "timestamps.json").exists() and (p / "features.npz").exists()
    )


def seed_reciters(db: Session) -> None:
    """Upsert a `reciters` row for every bundle under data/reference/.

    Runs on startup. Idempotent: matches on slug, updates name/description
    if the bundle changed, leaves the row's id stable so existing attempts
    keep pointing at it.
    """
    for bundle_dir in _bundle_dirs():
        meta = json.loads((bundle_dir / "timestamps.json").read_text(encoding="utf-8"))
        slug = bundle_dir.name
        name = meta.get("reciter_name", slug.replace("_", " ").title())
        description = meta.get("description") or f"Reference recitation of Surah Al-Fatiha by {name}."

        row = db.query(Reciter).filter_by(slug=slug).one_or_none()
        if row is None:
            db.add(Reciter(
                slug=slug, name=name, description=description,
                qf_recitation_id=meta.get("reciter_id"),
            ))
        else:
            row.name = name
            row.description = description
            row.qf_recitation_id = meta.get("reciter_id")
    db.commit()


@lru_cache(maxsize=8)
def get_bundle(slug: str) -> pipeline.ReferenceBundle:
    """Load (and cache) the analysis `ReferenceBundle` for a reciter slug."""
    return pipeline.load_reference_bundle(settings.REFERENCE_DIR / slug)


def clear_bundle_cache() -> None:
    get_bundle.cache_clear()


def passage_payload(slug: str, audio_url: str) -> dict:
    """Build the /api/passages/fatiha body for one reciter (PRD §6).

    `audio_url` is this API's own streaming endpoint for the reciter's
    reference audio, not the upstream CDN URL.
    """
    bundle_dir = settings.REFERENCE_DIR / slug
    timing = json.loads((bundle_dir / "timestamps.json").read_text(encoding="utf-8"))

    text_by_number: dict[int, dict] = {}
    passage_path = bundle_dir / "passage.json"
    if passage_path.exists():
        for v in json.loads(passage_path.read_text(encoding="utf-8")).get("verses", []):
            text_by_number[v["verse_number"]] = v

    verses = []
    for v in timing["verses"]:
        n = v["verse_number"]
        text_entry = text_by_number.get(n, {})
        verses.append({
            "verse_number": n,
            "verse_key": v.get("verse_key", f"1:{n}"),
            "arabic_text": text_entry.get("text_uthmani", ""),
            "words": [
                {
                    "word_index": w["word_index"],
                    "arabic_text": _word_text(text_entry, w["word_index"]),
                    "start_ms": w["start_ms"],
                    "end_ms": w["end_ms"],
                }
                for w in v["words"]
            ],
            "start_ms": v["timestamp_from_ms"],
            "end_ms": v["timestamp_to_ms"],
        })

    return {
        "reciter_slug": slug,
        "surah": "al-fatiha",
        "reference_audio_url": audio_url,
        "verses": verses,
    }


def _word_text(verse_text_entry: dict, word_index: int) -> str:
    words = verse_text_entry.get("words", [])
    # word_index is 1-based (matches the audio segments); passage.json words
    # are a plain list in order.
    if 1 <= word_index <= len(words):
        return words[word_index - 1]
    return ""


def audio_path_for(slug: str) -> Path:
    return settings.REFERENCE_DIR / slug / "audio.wav"
