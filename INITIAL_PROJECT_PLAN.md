# PRD: Recitation Coach (working title)

**Version:** 1.0 (MVP)
**Owner:** Solo developer (student, building as a portfolio project)
**Status:** Approved for build
**Last updated:** 2026-09-02

---

## 1. Product overview

Recitation Coach is a **web app** that helps Muslims match their Quran recitation *style* to that of their favorite professional reciter. The user selects a reciter, records themselves reciting a passage, and receives a detailed comparison: an overall similarity score, per-verse scores, and specific, actionable feedback on **where** and **how** their recitation diverges from the reference (melody, pacing, tone, and elongation timing).

**This is a style coach, not a correctness checker.** Existing apps (e.g., Tarteel) verify *what* you said (word-level correctness for memorization). This app analyzes *how* you said it and how closely your delivery resembles a specific reciter's.

### Target user
A Muslim who already knows the words of the surah and wants to improve the beauty and style of their recitation by emulating a specific reciter (e.g., "I want my Al-Fatiha to sound like Maher Al Muaiqly's").

---

## 2. Scope

### In scope (v1)
- Web app only (desktop + mobile browser). No native mobile app.
- **Surah Al-Fatiha only** (7 verses).
- 2–3 preset reference reciters.
- User selects a verse range (e.g., verses 1–7, or 2–4) and records it in **one continuous take**. Hard cap: **3 minutes** of audio.
- Post-recording analysis (upload → analyze → results). **No real-time analysis in v1.**
- Four scored dimensions (see §5): melody, pacing, tone similarity, elongation timing.
- Results page with overall score, per-verse breakdown, pitch-contour overlay visualization, and a list of specific improvement tips.
- No user accounts. Attempts may be stored locally (SQLite) with an anonymous session ID for a simple "recent attempts" list.

### Explicitly OUT of scope (v1) — do not build, do not stub with fake implementations
- **Articulation-level tajweed checking** (makharij, ghunnah, qalqalah, letter-articulation correctness). This requires phoneme-level Arabic ASR and is a v2+ research item. Do NOT fake this with heuristics and present it as tajweed correctness.
- Real-time / live follow-along highlighting while reciting (v2).
- Word-correctness detection ("you said the wrong word").
- User authentication, profiles, social features.
- Surahs other than Al-Fatiha.
- Native mobile apps.

---

## 3. Tech stack (fixed — do not substitute)

| Layer | Choice | Notes |
|---|---|---|
| Backend | **Python 3.11+, FastAPI** | Async endpoints; auto docs at `/docs` |
| Audio analysis | **librosa, numpy, scipy, fastdtw** | Core algorithm lives in a pure-Python module, independent of FastAPI |
| Audio conversion | **pydub + ffmpeg** | Convert browser uploads (webm/ogg) to mono WAV |
| Frontend | **Vanilla HTML/CSS/JS** (no React, no framework) | MediaRecorder API for recording; Canvas for pitch-contour chart |
| Database | **SQLite** via `sqlite3` or SQLAlchemy | Single file DB; fine for MVP |
| Reference data | **Quran Foundation Content API** (api.quran.foundation) | Reciter audio mp3 URLs + word-level timestamps. Requires free OAuth2 client credentials (server-side only — never expose credentials to the browser) |
| Deployment | Render or Railway (single service) | FastAPI serves both the API and the static frontend |

**Important developer notes:**
- The owner is learning this stack. Prefer **simple, readable, well-commented code** over clever abstractions. Small modules, clear names.
- The audio analysis pipeline (§5) is the heart of the project. Keep it in its own module (e.g., `analysis/`) with **unit tests** using small sample audio fixtures, so it can be developed and tested independently of the web layer.
- Reference reciter audio and timestamps must be **fetched once and cached/precomputed locally** (see §6). Do not call the Quran Foundation API on every user request.
- Respect the Quran Foundation Developer Terms regarding audio storage and use. Cache only what the terms permit; link/stream reference audio from their CDN where required.

---

## 4. Core user flow

1. **Welcome page** → brief explanation → "Start practicing."
2. **Select reciter** → cards for 2–3 reciters (name, photo optional, short description).
3. **Select passage** → Surah Al-Fatiha shown with all 7 verses (Arabic text). User picks a start verse and end verse (default: 1–7).
4. **Listen (optional)** → user can play the reference reciter's audio for the selected range (streamed, with the current verse highlighted using reference timestamps).
5. **Record** → mic permission → record button with live elapsed timer and a visible 3:00 cap (auto-stop at cap). User can play back their take and re-record before submitting.
6. **Analyze** → upload; show a progress/loading state (analysis may take several seconds).
7. **Results** →
   - Overall similarity score (0–100) with a qualitative label (e.g., "Getting close").
   - Sub-scores: Melody, Pacing, Tone, Elongation (each 0–100).
   - Per-verse score chips (tap/click a verse to focus its feedback).
   - **Pitch-contour overlay chart**: reference contour vs. user contour on a shared normalized time axis (this is the visual centerpiece).
   - **Actionable tips list**, each tied to a location, e.g.:
     - "Verse 2, word 3 (الرَّحْمَـٰنِ): the reciter rises in pitch here; yours falls."
     - "Verse 4: you recited this 40% faster than the reference. Slow down."
     - "Verse 1, word 4: the reciter elongates this word ~2.1s; you held it ~0.8s. Extend the madd."
   - "Try again" button returning to the record step with the same settings.

---

## 5. Analysis pipeline (technical specification)

All analysis happens server-side after upload. Implement as pure functions in an `analysis/` module.

### 5.1 Preprocessing
1. Convert upload to **mono WAV, 22050 Hz** (pydub/ffmpeg).
2. Trim leading/trailing silence (librosa.effects.trim, sensible top_db e.g. 30).
3. Reject with a clear error if: duration < 2s, duration > 3min, or audio is essentially silent.

### 5.2 Reference data (precomputed offline, stored locally)
For each reciter × Al-Fatiha:
- Full-surah mp3 (or per-ayah files) from Quran Foundation API/CDN.
- **Word-level timestamps** `[word_index, start_ms, end_ms]` per verse from the API.
- Precompute and cache: pitch contour (§5.3), MFCC matrix (§5.6), per-word durations, per-verse durations. Store as JSON/NPZ in `data/reference/`.
- A small maintenance script (`scripts/build_reference.py`) performs this precomputation; it is run manually by the developer, not at request time.

For a user-selected verse range, slice the reference features using the verse timestamps.

### 5.3 Pitch extraction (both user and reference)
- `librosa.pyin` with range roughly C2–C6 (`fmin=65 Hz`, `fmax=1047 Hz`), standard frame/hop (e.g., hop_length=256).
- Output: f0 array + voiced flags.
- Convert f0 to **semitones**: `12 * log2(f0 / 55.0)` (reference pitch arbitrary; only relative shape matters).
- **Transposition invariance (critical):** subtract the *median* voiced semitone value from each contour before comparison. Users naturally recite in different registers; we compare melodic **shape**, not absolute pitch. Never penalize a user for having a deeper/higher voice.
- Handle unvoiced frames by masking or linear interpolation across short gaps; document the choice in code comments.

### 5.4 Alignment (DTW)
- Run DTW (fastdtw, radius tuned for performance) between the normalized user contour and the normalized reference contour for the selected range.
- Outputs: (a) alignment path mapping user time ↔ reference time; (b) normalized DTW distance.
- The alignment path is reused by every other scorer (pacing, tone, elongation, per-verse segmentation). Compute once, pass around.
- Map user audio to verses/words by pushing the reference word timestamps through the alignment path.

### 5.5 Melody score
- From normalized DTW distance → 0–100 score via a calibration function (e.g., exponential decay; constants tuned by hand against test recordings — expose them in a config file).
- Per-verse melody scores: compute DTW distance restricted to each verse's aligned segment.
- Divergence detection for tips: find contiguous regions along the alignment path where |user_semitone − ref_semitone| exceeds a threshold (e.g., >3 semitones for >0.5s); map region → verse/word via timestamps; classify direction (user higher/lower, rising where reference falls, etc.).

### 5.6 Tone similarity score
- Extract MFCCs (13 coefficients, **drop c0**) for user and reference.
- Compare frame pairs along the DTW alignment path using cosine similarity; aggregate to 0–100.
- **Framing requirement (product-level):** present this as "tone similarity," never as correctness. Different voices legitimately differ; UI copy must say something like "how closely your vocal tone resembles the reciter's" and must not tell users their voice is "wrong."

### 5.7 Pacing score
- Per-verse: user verse duration (via alignment) ÷ reference verse duration. Score decays as the ratio departs from 1.0 (also detect global tempo offset vs. per-verse anomalies — reciting uniformly slower is less of an error than rushing one verse).
- Pause analysis: compare inter-verse pause durations (silence between verse-end and next verse-start) user vs. reference; flag missing/short pauses where the reference clearly pauses (waqf behavior at verse ends).
- Tips: verses >25% faster/slower than reference (after removing global tempo offset) generate a tip.

### 5.8 Elongation (madd-proxy) score
- Identify reference words whose duration is unusually long relative to surrounding words (e.g., > 1.6× local median) — these are elongation candidates.
- Compare the user's aligned duration for those words. Ratio-based scoring; large shortfalls/overshoots generate word-specific tips ("extend this word," "you're over-holding this word").
- **Naming requirement:** in code and UI this is "elongation timing," not "tajweed score." It is a timing proxy, not a tajweed ruling.

### 5.9 Overall score
- Weighted: Melody 45%, Pacing 20%, Tone 20%, Elongation 15%. Weights live in a config file.
- Qualitative labels: e.g., 85+ "Very close", 70–84 "Getting close", 50–69 "On your way", <50 "Keep practicing". Copy must always be encouraging and respectful — this is Quran recitation practice; never mocking, never gamified in a trivializing way (no confetti, no leaderboards).

### 5.10 Failure modes (must handle gracefully)
- User recites a different passage than selected, or mostly silence → DTW distance will be extreme; detect via distance threshold and return a friendly "We couldn't match your recording to the selected verses — check that you recited verses X–Y and try again" instead of a nonsense low score.
- Very noisy audio → if voiced-frame ratio is very low, ask the user to re-record somewhere quieter.
- Browser sends unsupported codec → convert via ffmpeg; if conversion fails, return a clear error.

---

## 6. API design (FastAPI)

Base path `/api`. FastAPI also serves the static frontend from `/`.

- `GET /api/reciters` → list of reciters `[{id, name, description}]`.
- `GET /api/passages/fatiha?reciter_id=` → verses `[{verse_number, arabic_text, start_ms, end_ms}]`, reference audio stream URL, word timestamps for the reciter.
- `POST /api/attempts` (multipart form) → fields: `reciter_id`, `start_verse`, `end_verse`, `audio` (file). Runs the full pipeline. Response:

```json
{
  "attempt_id": "uuid",
  "overall_score": 78,
  "label": "Getting close",
  "sub_scores": {"melody": 81, "pacing": 74, "tone": 77, "elongation": 70},
  "per_verse": [{"verse": 1, "score": 84}, {"verse": 2, "score": 71}],
  "pitch_overlay": {
    "time_axis": [0.0, 0.05, ...],
    "reference_semitones": [...],
    "user_semitones_aligned": [...]
  },
  "tips": [
    {"verse": 2, "word_index": 3, "type": "melody", "text": "..."},
    {"verse": 4, "word_index": null, "type": "pacing", "text": "..."}
  ]
}
```

- `GET /api/attempts/{id}` → stored result (for the "recent attempts" list).
- Upload constraints enforced server-side: max 3 minutes / e.g. 15 MB; accepted types webm/ogg/wav/mp3/m4a.

## 7. Data model (SQLite)

- `reciters(id, name, slug, description, qf_recitation_id)`
- `attempts(id TEXT PK, session_id TEXT, reciter_id, start_verse, end_verse, overall_score, sub_scores_json, per_verse_json, tips_json, created_at)`
  - Raw user audio: store on disk under `data/attempts/` keyed by attempt id; add a config flag to disable retention. Do not store audio in the DB.
- Reference features cached as files in `data/reference/` (not in DB).

`session_id` = random ID in a cookie/localStorage; used only to show the user their own recent attempts. No accounts, no personal data collected. State this in a short privacy note in the footer.

---

## 8. Frontend requirements

- Single-page flow (steps shown/hidden via JS), mobile-responsive, RTL-correct rendering of Arabic text (use a proper Quran font, e.g., a KFGQPC/Uthmanic font, loaded locally).
- Recording via MediaRecorder; show elapsed time and remaining cap; auto-stop at 3:00; playback preview before submit.
- Reference playback with current-verse highlighting driven by reference timestamps.
- Results: score cards, per-verse chips, Canvas chart drawing the two pitch contours (reference vs. user, aligned time axis), tips list grouped by verse. Keep the chart simple: two lines, a legend, verse boundary markers.
- Visual design: clean, calm, respectful. No gamification aesthetics. Dark-on-light default is fine.

---

## 9. Milestones (build order)

1. **M1 — Reference data**: QF API credentials; `scripts/build_reference.py` fetches Al-Fatiha audio + word timestamps for 2 reciters and precomputes features. Verify by plotting a reference pitch contour.
2. **M2 — Analysis core (no web)**: pipeline functions + unit tests; CLI script that takes two audio files and prints scores + tips. **This milestone is the project's core; do not move on until scores behave sensibly on test recordings.**
3. **M3 — API**: FastAPI endpoints wrapping the pipeline; enforce upload limits; error handling per §5.10.
4. **M4 — Frontend**: full user flow against the API.
5. **M5 — Polish + deploy**: results visualization polish, failure-mode UX, deploy to Render/Railway, README.

---

## 10. Success criteria (MVP)

- Reciting Al-Fatiha carefully while imitating the selected reciter scores noticeably higher than reciting it flat/rushed (sanity check with the developer's own recordings).
- Recording a wrong/garbage input produces the friendly mismatch error, not a score.
- End-to-end (record → results) completes in under ~15s for a full-surah take on the free hosting tier.
- A stranger can open the deployed URL and complete the full flow with no instructions.

---

## 11. Notes for the AI coding assistant

- Do not add frameworks, ORMs, task queues, Docker, or auth unless asked. Keep it simple.
- Do not fabricate tajweed/articulation analysis. If a feature request seems to require phoneme-level ASR, stop and flag it instead of stubbing it.
- Comment the analysis code generously — the owner must be able to explain every step of §5 in an interview.
- Prefer standard, well-documented library calls over custom DSP where possible.
- All scoring constants (thresholds, weights, calibration) belong in one config module for easy tuning.