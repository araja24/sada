"""Runtime configuration, all from environment variables (with dev-friendly
defaults) so the same code runs locally and on Render/Railway.

Scoring constants live in `analysis/config.py`; this module is only about
where files and the database are, and the session secret.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Where mutable data lives. Overridable as a whole (SADA_DATA_DIR) or piece
# by piece -- tests point these at a tmp dir.
DATA_DIR = Path(os.environ.get("SADA_DATA_DIR", REPO_ROOT / "data"))
REFERENCE_DIR = Path(os.environ.get("SADA_REFERENCE_DIR", DATA_DIR / "reference"))
ATTEMPTS_DIR = Path(os.environ.get("SADA_ATTEMPTS_DIR", DATA_DIR / "attempts"))

DATABASE_URL = os.environ.get("SADA_DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'sada.db').as_posix()}"

# Signs the session cookie (docs/adr/0002). Required in production; the
# insecure default only exists so `uvicorn app.main:app` runs out of the box
# for local dev.
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "dev-insecure-secret-do-not-use-in-prod")
SESSION_COOKIE_NAME = "sada_session"
# 30 days; a guest's "recent attempts" identity shouldn't evaporate mid-week.
SESSION_MAX_AGE_S = 30 * 24 * 3600

# PRD §7: "add a config flag to disable [audio] retention."
RETAIN_AUDIO = os.environ.get("SADA_RETAIN_AUDIO", "1").lower() not in {"0", "false", "no"}

# Upload constraints (PRD §5.10 / §6): max ~15 MB, and only browser-plausible
# audio container types.
MAX_UPLOAD_BYTES = int(os.environ.get("SADA_MAX_UPLOAD_BYTES", 15 * 1024 * 1024))
ACCEPTED_AUDIO_CONTENT_TYPES = {
    "audio/webm",
    "audio/ogg",
    "video/webm",  # some browsers label MediaRecorder webm audio as video/webm
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",  # mp3
    "audio/mp3",
    "audio/mp4",  # m4a
    "audio/x-m4a",
    "audio/aac",
}
ACCEPTED_AUDIO_EXTENSIONS = {".webm", ".ogg", ".wav", ".mp3", ".m4a", ".aac"}

FRONTEND_DIR = Path(os.environ.get("SADA_FRONTEND_DIR", REPO_ROOT / "frontend" / "dist"))
