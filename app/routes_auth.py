"""Auth endpoints (docs/adr/0002-user-accounts.md).

Self-built email+password: bcrypt hashes in the `users` table, session
state in the signed cookie. No email verification, password reset, or
session revocation in v1 (see the ADR's consequences).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from .db import get_db
from .models import Attempt, User
from .schemas import Credentials, UserOut
from .security import current_user_id, get_or_create_session_id, hash_password, log_in, log_out, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def claim_guest_attempts(db: Session, session_id: str, user_id: int) -> int:
    """Attach this browser's guest attempts to the account (docs/adr/0002).

    One query, run on every successful signup/login: any attempt made under
    the current `session_id` that isn't already owned becomes the user's.
    Returns the number of rows reattached.
    """
    result = db.execute(
        update(Attempt)
        .where(Attempt.session_id == session_id, Attempt.user_id.is_(None))
        .values(user_id=user_id)
    )
    db.commit()
    return result.rowcount or 0


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(creds: Credentials, request: Request, db: Session = Depends(get_db)) -> UserOut:
    session_id = get_or_create_session_id(request)
    if db.query(User).filter_by(email=creds.email).one_or_none() is not None:
        raise HTTPException(status_code=409, detail="That email is already registered.")

    user = User(email=creds.email, password_hash=hash_password(creds.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    claim_guest_attempts(db, session_id, user.id)
    log_in(request, user.id)
    return UserOut(id=user.id, email=user.email)


@router.post("/login", response_model=UserOut)
def login(creds: Credentials, request: Request, db: Session = Depends(get_db)) -> UserOut:
    session_id = get_or_create_session_id(request)
    user = db.query(User).filter_by(email=creds.email).one_or_none()
    # Same message + a hash check even when the user is missing, so response
    # timing/text doesn't reveal which emails are registered.
    if user is None or not verify_password(creds.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")

    claim_guest_attempts(db, session_id, user.id)
    log_in(request, user.id)
    return UserOut(id=user.id, email=user.email)


@router.post("/logout")
def logout(request: Request) -> dict:
    log_out(request)
    return {"ok": True}


@router.get("/me", response_model=UserOut | None)
def me(request: Request, db: Session = Depends(get_db)) -> UserOut | None:
    user_id = current_user_id(request)
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None:  # stale cookie -- account gone
        log_out(request)
        return None
    return UserOut(id=user.id, email=user.email)
