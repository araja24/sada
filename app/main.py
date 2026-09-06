"""FastAPI application factory.

Single service (PRD §3): this app serves the JSON API under /api, the
interactive docs at /docs, and -- once the frontend exists (issues #8-#10)
-- the static site at /.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import settings
from .db import SessionLocal, create_all
from .reference import seed_reciters
from .routes_attempts import router as attempts_router
from .routes_auth import router as auth_router
from .routes_reciters import router as reciters_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    db = SessionLocal()
    try:
        seed_reciters(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sada",
        description="Match your Quran recitation style to a professional reciter's.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Signed, HttpOnly session cookie (docs/adr/0002). `https_only` off in
    # dev so localhost works; the deploy sets it via env.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET_KEY,
        session_cookie=settings.SESSION_COOKIE_NAME,
        max_age=settings.SESSION_MAX_AGE_S,
        same_site="lax",
        https_only=settings.SESSION_SECRET_KEY != "dev-insecure-secret-do-not-use-in-prod",
    )

    app.include_router(reciters_router)
    app.include_router(attempts_router)
    app.include_router(auth_router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built Vite SPA.

    StaticFiles(html=True) 404s on client-side routes like /results/abc123,
    so the hashed assets get a real mount and everything else falls through
    to index.html. Registered last so it never shadows /api/* or /docs.
    """
    index = settings.FRONTEND_DIR / "index.html"
    if not index.exists():
        return
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets = settings.FRONTEND_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    root = settings.FRONTEND_DIR.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # An unknown /api/* path must 404 as JSON, not as the SPA shell.
        if full_path.startswith("api/") or full_path in {"docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (settings.FRONTEND_DIR / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
