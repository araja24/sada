# Sada

A web app that helps you match your Quran recitation *style* — melody, pacing, tone, and elongation timing — to a specific reciter's. See [`INITIAL_PROJECT_PLAN.md`](./INITIAL_PROJECT_PLAN.md) for the full product spec, and [`CONTEXT.md`](./CONTEXT.md) for the project's domain glossary and key decisions.

This is a **style coach, not a correctness checker** — it never grades tajweed/articulation correctness.

## Status

Early build. Currently on **Milestone 1 (reference data)**: fetching Maher Al Muaiqly's Al-Fatiha recitation + word timestamps from the Quran Foundation API and precomputing reference audio features.

## Setup

1. **Python 3.11+** and **ffmpeg** (on PATH) are required. On Windows: `winget install --id Gyan.FFmpeg -e`.
2. Create and activate a virtualenv, then install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your [Quran Foundation API](https://api-docs.quran.foundation/) OAuth2 client credentials.

## Building the reference data

Milestone 1: fetch Maher Al Muaiqly's Al-Fatiha audio + word timestamps and precompute reference features (pitch contour, MFCCs, per-word/per-verse durations). Requires `QF_CLIENT_ID`/`QF_CLIENT_SECRET` in `.env`:

```bash
python scripts/build_reference.py
# Also save a pitch-contour plot for one verse, as a sanity check:
python scripts/build_reference.py --plot-verse 1
```

This caches everything under `data/reference/<reciter_slug>/` (`audio.wav`, `features.npz`, `timestamps.json`, `passage.json`, and optionally `plots/verse_N_pitch.png`). It hits the live API and is meant to be run manually, not automatically or per-request.

**No Quran Foundation credentials yet?** The same v4 API is served unauthenticated at `api.quran.com`, which is enough to build a real reference cache and work on everything downstream. See [ADR-0001](./docs/adr/0001-reference-data-source.md):

```bash
python scripts/build_reference.py --source public-mirror \
    --reciter-name "Mahmoud Khalil Al-Husary" --reciter-id 6
```

## Project layout

- `analysis/` — pure-Python audio analysis pipeline (pitch, tone, alignment, scoring). No FastAPI imports here; unit-testable in isolation.
- `scripts/build_reference.py` — one-time/manual script that fetches reciter audio + timestamps and precomputes reference features into `data/reference/`.
- `data/reference/` — precomputed reference features (regenerable, gitignored).
- `data/attempts/` — user-submitted recordings (private, gitignored).
- `tests/` — unit tests for `analysis/`.
