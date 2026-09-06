"""API + persistence + auth tests (PRD §6/§7, docs/adr/0002).

Uses FastAPI's TestClient against a per-test SQLite file and a synthetic
reference bundle on disk -- no live network, no real Quran Foundation data.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis.pitch import extract_pitch_contour
from analysis.tone import extract_mfcc
from app import settings as app_settings
from app.db import Base, get_db
from app.main import app as fastapi_app
from app.reference import clear_bundle_cache, seed_reciters

SR = 22050
FREQS = [220.0, 247.0, 277.0]
SEG_S = 1.5


def _sine(freq, dur, sr=SR):
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    return (0.8 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _passage_audio():
    return np.concatenate([_sine(f, SEG_S) for f in FREQS])


def _write_bundle(reciter_dir):
    reciter_dir.mkdir(parents=True)
    y = _passage_audio()
    contour = extract_pitch_contour(y, SR)
    np.savez(
        reciter_dir / "features.npz",
        sample_rate=SR,
        pitch_times=contour.times,
        f0_hz=contour.f0_hz,
        voiced_flag=contour.voiced_flag,
        semitones=contour.semitones,
        semitones_centered=contour.semitones_centered,
        median_semitone=contour.median_semitone,
        mfcc=extract_mfcc(y, SR),
    )
    seg_ms = int(SEG_S * 1000)
    verses = []
    for i in range(len(FREQS)):
        start = i * seg_ms
        verses.append({
            "verse_key": f"1:{i + 1}",
            "verse_number": i + 1,
            "timestamp_from_ms": start,
            "timestamp_to_ms": start + seg_ms,
            "words": [
                {"word_index": w + 1, "start_ms": start + w * seg_ms // 3,
                 "end_ms": start + (w + 1) * seg_ms // 3}
                for w in range(3)
            ],
        })
    (reciter_dir / "timestamps.json").write_text(
        json.dumps({"reciter_name": "Test Reciter", "reciter_id": 7, "verses": verses}),
        encoding="utf-8",
    )
    (reciter_dir / "passage.json").write_text(
        json.dumps({"verses": [
            {"verse_key": f"1:{i + 1}", "verse_number": i + 1,
             "text_uthmani": f"verse {i + 1} text", "words": ["a", "b", "c"]}
            for i in range(len(FREQS))
        ]}, ensure_ascii=False),
        encoding="utf-8",
    )
    sf.write(str(reciter_dir / "audio.wav"), y, SR)


def _wav_bytes(y):
    buf = io.BytesIO()
    sf.write(buf, y, SR, format="WAV")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    ref_dir = tmp_path / "reference"
    _write_bundle(ref_dir / "test-reciter")
    monkeypatch.setattr(app_settings, "REFERENCE_DIR", ref_dir)
    monkeypatch.setattr(app_settings, "ATTEMPTS_DIR", tmp_path / "attempts")
    monkeypatch.setattr(app_settings, "RETAIN_AUDIO", True)
    clear_bundle_cache()

    engine = create_engine(
        f"sqlite:///{(tmp_path / 't.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    seed_db = TestingSession()
    seed_reciters(seed_db)
    seed_db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    # No `with` -> lifespan doesn't run, so the real default engine is never touched.
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
    clear_bundle_cache()


@pytest.fixture
def reciter_id(client):
    return client.get("/api/reciters").json()[0]["id"]


# --- reciters / passages -------------------------------------------


def test_list_reciters(client):
    resp = client.get("/api/reciters")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["slug"] == "test-reciter"
    assert set(body[0]) == {"id", "slug", "name", "description"}


def test_passage_has_verses_text_and_audio_url(client, reciter_id):
    resp = client.get(f"/api/passages/fatiha?reciter_id={reciter_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reference_audio_url"] == "/api/reciters/test-reciter/audio"
    assert [v["verse_number"] for v in body["verses"]] == [1, 2, 3]
    assert body["verses"][0]["arabic_text"] == "verse 1 text"
    assert body["verses"][0]["words"][0]["start_ms"] == 0


def test_passage_unknown_reciter_404(client):
    assert client.get("/api/passages/fatiha?reciter_id=999").status_code == 404


def test_reference_audio_streams(client):
    resp = client.get("/api/reciters/test-reciter/audio")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"


# --- attempts ------------------------------------------------------


def _submit(client, reciter_id, audio=None, **overrides):
    audio = audio if audio is not None else _passage_audio()
    data = {"reciter_id": reciter_id, "start_verse": 1, "end_verse": 3, **overrides}
    return client.post(
        "/api/attempts",
        data=data,
        files={"audio": ("take.wav", _wav_bytes(audio), "audio/wav")},
    )


def test_create_attempt_returns_prd_shape(client, reciter_id):
    resp = _submit(client, reciter_id)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert set(body) >= {
        "attempt_id", "overall_score", "label", "sub_scores", "per_verse",
        "pitch_overlay", "tips",
    }
    assert set(body["sub_scores"]) == {"melody", "pacing", "tone", "elongation"}
    assert body["overall_score"] >= 80
    assert len(body["pitch_overlay"]["time_axis"]) == 200


def test_get_attempt_round_trips(client, reciter_id):
    attempt_id = _submit(client, reciter_id).json()["attempt_id"]
    resp = client.get(f"/api/attempts/{attempt_id}")
    assert resp.status_code == 200
    assert resp.json()["attempt_id"] == attempt_id


def test_get_unknown_attempt_404(client):
    assert client.get("/api/attempts/does-not-exist").status_code == 404


def test_attempt_rejects_bad_verse_range(client, reciter_id):
    assert _submit(client, reciter_id, start_verse=5, end_verse=2).status_code == 422


def test_attempt_rejects_unknown_reciter(client):
    assert _submit(client, 999).status_code == 404


def test_attempt_rejects_oversized_upload(client, reciter_id, monkeypatch):
    monkeypatch.setattr(app_settings, "MAX_UPLOAD_BYTES", 10)
    assert _submit(client, reciter_id).status_code == 413


def test_attempt_rejects_unsupported_type(client, reciter_id):
    resp = client.post(
        "/api/attempts",
        data={"reciter_id": reciter_id, "start_verse": 1, "end_verse": 3},
        files={"audio": ("take.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415


def test_attempt_mismatch_returns_friendly_422(client, reciter_id):
    # Silence -> the pipeline's SilentAudioError -> 422 with a message.
    resp = _submit(client, reciter_id, audio=np.zeros(SR * 3, dtype=np.float32))
    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_list_attempts_scoped_to_guest_session(client, reciter_id):
    _submit(client, reciter_id)
    rows = client.get("/api/attempts").json()
    assert len(rows) == 1
    assert rows[0]["reciter_slug"] == "test-reciter"


# --- auth (docs/adr/0002) -----------------------------------------


def test_signup_login_logout_me(client):
    assert client.get("/api/auth/me").json() is None

    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "hunter2pw"})
    assert r.status_code == 201
    assert r.json()["email"] == "a@b.com"
    assert "password" not in r.text and "hash" not in r.text.lower()

    assert client.get("/api/auth/me").json()["email"] == "a@b.com"

    assert client.post("/api/auth/logout").json() == {"ok": True}
    assert client.get("/api/auth/me").json() is None

    assert client.post("/api/auth/login", json={"email": "a@b.com", "password": "hunter2pw"}).status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "a@b.com"


def test_signup_rejects_duplicate_email(client):
    client.post("/api/auth/signup", json={"email": "dup@b.com", "password": "hunter2pw"})
    client.post("/api/auth/logout")
    r = client.post("/api/auth/signup", json={"email": "dup@b.com", "password": "otherpw12"})
    assert r.status_code == 409


def test_login_rejects_wrong_password(client):
    client.post("/api/auth/signup", json={"email": "c@b.com", "password": "hunter2pw"})
    client.post("/api/auth/logout")
    r = client.post("/api/auth/login", json={"email": "c@b.com", "password": "wrongpass1"})
    assert r.status_code == 401


def test_guest_claim_reattaches_prior_attempts(client, reciter_id):
    # Guest submits an attempt, then signs up -> the attempt is now theirs.
    _submit(client, reciter_id)
    assert len(client.get("/api/attempts").json()) == 1

    client.post("/api/auth/signup", json={"email": "claim@b.com", "password": "hunter2pw"})
    rows = client.get("/api/attempts").json()
    assert len(rows) == 1  # same attempt, now under the account

    # A brand-new guest session (no cookie) sees nothing.
    fresh = TestClient(fastapi_app)
    assert fresh.get("/api/attempts").json() == []


def test_logout_keeps_guest_session_identity(client, reciter_id):
    # Guest attempt -> signup (claims it) -> logout -> still the same guest
    # session, so the claimed-then-released history is gone for the guest but
    # the session_id is stable (a fresh guest attempt lands under it).
    _submit(client, reciter_id)
    client.post("/api/auth/signup", json={"email": "logout@b.com", "password": "hunter2pw"})
    assert len(client.get("/api/attempts").json()) == 1  # as the user
    client.post("/api/auth/logout")
    # Back to guest: the earlier attempt now belongs to the account, not the
    # guest session, so the guest sees none of it.
    assert client.get("/api/attempts").json() == []
    _submit(client, reciter_id)
    assert len(client.get("/api/attempts").json()) == 1  # new guest attempt


def test_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_static_frontend_is_served(client):
    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]


def test_spa_deep_link_falls_back_to_index(client):
    """react-router owns /results/:id; the server must return the shell, not 404."""
    resp = client.get("/results/abc123")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_unknown_api_path_404s_as_json_not_spa(client):
    """The catch-all must never swallow /api/*, or client errors become HTML."""
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "application/json" in resp.headers["content-type"]


def test_docs_not_shadowed_by_spa(client):
    assert "text/html" in client.get("/docs").headers["content-type"]
    assert client.get("/openapi.json").json()["info"]["title"] == "Sada"


def test_favicon_is_served(client):
    resp = client.get("/favicon.svg")
    assert resp.status_code == 200


def test_spa_fallback_rejects_path_traversal(client):
    resp = client.get("/../../app/settings.py")
    assert resp.status_code in (200, 404)
    assert "SESSION_SECRET_KEY" not in resp.text
