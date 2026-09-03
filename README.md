# Sada

A web app that helps you match your Quran recitation *style* — melody, pacing, tone, and elongation timing — to a specific professional reciter's. It is a **style coach, not a correctness checker**: it never grades tajweed or articulation correctness.

See [`INITIAL_PROJECT_PLAN.md`](./INITIAL_PROJECT_PLAN.md) for the full product spec, [`CONTEXT.md`](./CONTEXT.md) for the domain glossary, and [`docs/adr/`](./docs/adr/) for key decisions.

## How it works

1. Pick a reciter and a verse range of Surah Al-Fatiha, optionally listen to the reference.
2. Record yourself reciting it in one take (3:00 cap).
3. Get an overall similarity score + encouraging label, four sub-scores (melody, pacing, tone similarity, elongation timing), per-verse scores, a reference-vs-you pitch-contour chart, and located, specific tips.

The analysis pipeline (`analysis/`) is pure Python — pitch extraction (`librosa.pyin`), median-centering for transposition invariance, DTW alignment, then four independent scorers combined by weight. It's fully unit-tested in isolation from the web layer.

## Setup (local)

Requires **Python 3.11+** and **ffmpeg** on `PATH` (browser recordings are WebM/Opus; ffmpeg converts them).
On Windows: `winget install --id Gyan.FFmpeg -e`. On macOS: `brew install ffmpeg`. On Debian/Ubuntu: `apt install ffmpeg`.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # then fill in SESSION_SECRET_KEY (and QF creds if building reference data)
```

## Build the reference data

The app needs at least one reciter's precomputed Al-Fatiha features under `data/reference/`. This is a one-time manual step (never run per-request):

```bash
# With Quran Foundation API credentials in .env (QF_CLIENT_ID / QF_CLIENT_SECRET):
python scripts/build_reference.py --reciter-name "Mishari Rashid al-`Afasy"

# No credentials yet? Use the unauthenticated public mirror (see ADR-0001):
python scripts/build_reference.py --source public-mirror --reciter-name "Mishari Rashid al-`Afasy" --reciter-id 7
```

Each bundle is cached under `data/reference/<slug>/` (`audio.wav`, `features.npz`, `timestamps.json`, `passage.json`). `data/reference/` is gitignored — it's regenerable.

## Run

```bash
uvicorn app.main:app --reload
```

- App + full flow: <http://localhost:8000/>
- API docs: <http://localhost:8000/docs>

The single FastAPI service serves both the JSON API (`/api/*`) and the static frontend (`frontend/`). Reciters are seeded into SQLite on startup from whatever bundles exist under `data/reference/`.

## CLI (no web)

```bash
python scripts/compare.py --audio my_recitation.wav --reciter mishari_rashid_al_afasy --verses 1-7
```

Prints the overall score + label, all four sub-scores, per-verse scores, and the combined tips list.

## Test

```bash
pytest -q
```

## Deploy

`imageio-ffmpeg` (in `requirements.txt`) ships a static ffmpeg binary that
`analysis/audio_io.py` finds automatically, so **no Docker and no system
ffmpeg package are needed** on either host below.

### Render (`render.yaml` blueprint)

1. Commit a reference bundle so the deploy has a reciter (it's gitignored by default):
   ```bash
   git add -f data/reference/<slug>
   git commit -m "Add reference bundle for deploy"
   ```
2. In Render: **New → Blueprint**, point it at this repo. `render.yaml` sets the
   build/start commands and generates a stable `SESSION_SECRET_KEY`.
3. Open the `*.onrender.com` URL.

The free plan has **no persistent disk**, so the SQLite DB and uploads reset on
each deploy/cold-start — fine for a demo (the record→results flow always works;
reciters re-seed from the committed bundle). For durable accounts + history,
use a paid instance with a disk (uncomment the `disk:` block in `render.yaml`,
then set `SADA_DATA_DIR` / `SADA_DATABASE_URL` into it) or attach a managed
Postgres and point `SADA_DATABASE_URL` at it.

### Railway (`nixpacks.toml` + `Procfile`)

1. Create a Railway project from this repo (Nixpacks builds it automatically).
2. Add a **Volume** mounted at `/data`.
3. Set env vars: `SESSION_SECRET_KEY` (a real secret — never commit it),
   `SADA_DATA_DIR=/data`, `SADA_DATABASE_URL=sqlite:////data/sada.db`.
4. Provide a reference bundle: commit one (as above), or run
   `scripts/build_reference.py` in a one-off shell with
   `SADA_REFERENCE_DIR=/data/reference`.

## Project layout

- `analysis/` — pure-Python analysis pipeline (pitch, tone, alignment, four scorers, `pipeline.analyze`). No web imports.
- `app/` — FastAPI layer: endpoints, SQLite persistence, self-built email+password accounts (ADR-0002).
- `frontend/` — vanilla HTML/CSS/JS single-page flow, served by `app`.
- `scripts/build_reference.py` — manual reference-data builder. `scripts/compare.py` — CLI scorer.
- `data/reference/` (bundles), `data/attempts/` (uploads) — both gitignored.
- `tests/` — unit + API tests.
