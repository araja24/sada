"""Password hashing and session-cookie helpers (docs/adr/0002).

The session cookie (Starlette `SessionMiddleware`) holds a small JSON dict:
    {"sid": "<uuid4>", "uid": <user id or absent>}
`sid` is set once per browser and never changes (not even on logout);
`uid` is present only while logged in.
"""

from __future__ import annotations

import uuid

import bcrypt
from starlette.requests import Request

_SID = "sid"
_UID = "uid"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def get_or_create_session_id(request: Request) -> str:
    """Every visitor gets a stable `sid` on first contact (docs/adr/0002)."""
    sid = request.session.get(_SID)
    if not sid:
        sid = str(uuid.uuid4())
        request.session[_SID] = sid
    return sid


def current_user_id(request: Request) -> int | None:
    uid = request.session.get(_UID)
    return int(uid) if uid is not None else None


def log_in(request: Request, user_id: int) -> None:
    request.session[_UID] = int(user_id)


def log_out(request: Request) -> None:
    """Drop `uid` but keep `sid` -- reverts to the same guest identity."""
    request.session.pop(_UID, None)
