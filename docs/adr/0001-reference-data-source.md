# ADR-0001: Reference data source, and an unauthenticated development fallback

**Status:** Accepted
**Date:** 2026-09-03

## Context

`INITIAL_PROJECT_PLAN.md` §3 fixes the reference-data source: the **Quran Foundation Content API** (`api.quran.foundation`), authenticated with OAuth2 client credentials. That is the source `scripts/build_reference.py` uses to fetch a reciter's Al-Fatiha audio, word-level timestamps, and verse text.

Two practical problems come with it:

1. Quran Foundation credentials are issued per-app and **start in pre-live**; production access needs separate approval. Until a developer has working credentials, nothing downstream of Milestone 1 can be built or tested, because every later milestone reads the cached reference features.
2. The same v4 content API is also served **unauthenticated** at `api.quran.com` (the Quran.com API that the Quran Foundation API productionizes). Identical endpoint paths under a different prefix, identical payload shapes.

## Decision

Keep the Quran Foundation API as the **default and only production source**. Add `--source public-mirror` to `scripts/build_reference.py` as an explicitly-labelled **development** source that reads the same v4 endpoints from `api.quran.com` without credentials.

Both sources are implemented as thin transports behind one shared class (`_ContentApiV4Client` in `analysis/qf_client.py`), so all response interpretation is shared and neither path can silently drift from the other.

## Consequences

- A developer can build a real reference cache and work on Milestones 2-5 before their Quran Foundation credentials are approved. No fabricated/synthetic reference data is needed to exercise the pipeline, which matters because fake reference features would produce meaningless scores.
- The `source` is recorded in each reference bundle's `timestamps.json`, so it's always visible which source a given cache came from.
- The mirror is a development convenience, not a supported production path: it has no SLA for this project's use, serves word-level `segments` for only a subset of reciters, and its `/resources/chapter_reciters` endpoint is frequently unavailable (hence the documented fallback to `/resources/recitations` and the `--reciter-id` escape hatch).
- **Maher Al Muaiqly specifically is not available on the mirror** — it carries word-level timestamps for roughly a dozen reciters and he is not among them. Building the v1 reference bundle for him (per `CONTEXT.md`) therefore still requires Quran Foundation credentials. Development and testing use a reciter that does have segment data.
- Quran Foundation's Developer Terms still govern the production path (PRD §3: cache only what the terms permit, stream reference audio from their CDN where required).
- **Confirmed (2026-09-03), with working prelive credentials:** prelive's `/resources/chapter_reciters` only lists a small demo set — Mahmoud Khaleel/Khalil Al-Husary (ids 6, 12) and Mishari Rashid al-`Afasy (ids 7, 173) — and Maher Al Muaiqly is not among them either. So the mirror's Maher gap isn't mirror-specific: **prelive access doesn't include him at all**, and building his real bundle needs Quran Foundation **production** access, which per their docs requires separate approval beyond just having a working app.
- **Update (2026-09-03): v1's preset reciter is now Mishari Rashid al-`Afasy, not Maher.** Rather than block v1 on production approval, `CONTEXT.md`'s reciter definition and the PRD were updated to make Al-Afasy (chapter-reciter id 7) the actual v1 preset -- he's available on both prelive and the public mirror, so this ADR's whole rationale (build now, without waiting on approval) applies to him directly rather than as a stand-in. The reference bundle in `data/reference/` is built via `--source qf` (not the mirror) since prelive credentials now work. Maher remains a plausible v2+ addition if/when production access is granted.
