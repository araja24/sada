"""Elongation (madd-proxy) timing score.

PRD §5.8: identify reference words whose duration is unusually long
relative to nearby words -- a graphemic timing proxy for madd, never a
tajweed ruling -- then score the user's aligned duration for exactly
those words via a ratio, with word-specific tips for large
shortfalls/overshoots.

**Naming requirement (product-level, not a naming nit):** this is
"elongation timing," never "tajweed score." See PRD §5.8 and CONTEXT.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import config
from .align import AlignmentResult, path_indices_by_span
from .melody import VoicedSeries
from .qf_client import VerseTimestamp, WordTimestamp


@dataclass
class ElongationCandidate:
    """One reference word flagged as an elongation candidate, plus how the
    user's aligned duration for it compares.

    `user_duration_s`/`ratio`/`score` are `None` when no aligned frame
    landed on this word at all (e.g. the user's audio ended early) -- there
    is nothing to measure, which is different from measuring a bad ratio.
    """

    verse_number: int
    word_index: int
    ref_duration_s: float
    user_duration_s: float | None = None
    ratio: float | None = None
    score: float | None = None


@dataclass
class ElongationTip:
    verse_number: int
    word_index: int
    kind: str  # "shortfall" (held too short) or "overshoot" (held too long)
    percent_off: float


@dataclass
class ElongationScoreResult:
    overall_score: float
    candidates: list[ElongationCandidate]
    tips: list[ElongationTip] = field(default_factory=list)


def calibrate_elongation_score(ratio: float) -> float:
    """Map a duration ratio (user/reference, for one elongation-candidate
    word) to 0-100. Symmetric exponential decay in log-space -- same shape
    as `analysis.pacing.calibrate_pacing_score` (ratio 1.0 -> 100,
    over-holding and under-holding by the same factor score equally) but
    with its own hand-tuned constant, since a single word's timing
    tolerance need not match a whole verse's.
    """
    if ratio <= 0:
        raise ValueError("ratio must be > 0 (it's a duration ratio).")
    score = 100.0 * math.exp(-config.ELONGATION_DECAY_RATE * abs(math.log(ratio)))
    return max(0.0, min(100.0, score))


def find_elongation_candidates(
    ref_verses: list[VerseTimestamp],
    window_radius: int = config.ELONGATION_WINDOW_RADIUS,
    ratio_threshold: float = config.ELONGATION_LOCAL_MEDIAN_RATIO,
) -> list[tuple[VerseTimestamp, WordTimestamp]]:
    """Reference words whose duration exceeds `ratio_threshold` times the
    local median duration of nearby words (PRD §5.8).

    "Nearby" is a window across the whole passage's word sequence in
    order, not reset at verse boundaries -- Al-Fatiha's verses are short
    enough that a per-verse window would often have too few words for a
    meaningful median. Returns (verse, word) pairs in passage order.
    """
    flat: list[tuple[VerseTimestamp, WordTimestamp]] = [
        (verse, word) for verse in ref_verses for word in verse.words
    ]
    durations_ms = [word.duration_ms for _verse, word in flat]

    candidates: list[tuple[VerseTimestamp, WordTimestamp]] = []
    n = len(flat)
    for i, (verse, word) in enumerate(flat):
        window = durations_ms[max(0, i - window_radius) : min(n, i + window_radius + 1)]
        local_median_ms = float(np.median(window))
        if local_median_ms > 0 and word.duration_ms > ratio_threshold * local_median_ms:
            candidates.append((verse, word))
    return candidates


def score_elongation(
    alignment: AlignmentResult,
    user_series: VoicedSeries,
    ref_series: VoicedSeries,
    ref_verses: list[VerseTimestamp],
) -> ElongationScoreResult:
    """Score every elongation-candidate word in `ref_verses` and collect tips.

    Like pacing, this has no independent way to measure the user's
    duration for a given word -- it reads the aligned *user* time span for
    that word's ref-time range off the shared alignment path (PRD §5.4).
    """
    raw_candidates = find_elongation_candidates(ref_verses)
    spans = [
        ((verse.verse_number, word.word_index), word.start_ms, word.end_ms)
        for verse, word in raw_candidates
    ]
    indices_by_word = path_indices_by_span(alignment.path, ref_series.times, spans)

    candidates: list[ElongationCandidate] = []
    tips: list[ElongationTip] = []
    scores: list[float] = []
    for verse, word in raw_candidates:
        indices = indices_by_word[(verse.verse_number, word.word_index)]
        ref_duration_s = word.duration_ms / 1000.0

        if not indices:
            candidates.append(
                ElongationCandidate(
                    verse_number=verse.verse_number,
                    word_index=word.word_index,
                    ref_duration_s=ref_duration_s,
                )
            )
            continue

        user_times = [user_series.times[alignment.path[i][0]] for i in indices]
        user_duration_s = max(user_times) - min(user_times)
        ratio = user_duration_s / ref_duration_s if ref_duration_s > 0 else None
        score = calibrate_elongation_score(ratio) if ratio and ratio > 0 else None

        candidates.append(
            ElongationCandidate(
                verse_number=verse.verse_number,
                word_index=word.word_index,
                ref_duration_s=ref_duration_s,
                user_duration_s=user_duration_s,
                ratio=ratio,
                score=score,
            )
        )
        if score is not None:
            scores.append(score)

        if ratio is not None:
            percent_off = (ratio - 1.0) * 100.0
            if abs(percent_off) > config.ELONGATION_TIP_PERCENT_THRESHOLD:
                tips.append(
                    ElongationTip(
                        verse_number=verse.verse_number,
                        word_index=word.word_index,
                        kind="shortfall" if percent_off < 0 else "overshoot",
                        percent_off=percent_off,
                    )
                )

    # No elongation candidates in the scored range -> nothing to judge,
    # not a penalty; same convention as pacing/melody's "no issues found."
    overall_score = float(np.mean(scores)) if scores else 100.0
    return ElongationScoreResult(overall_score=overall_score, candidates=candidates, tips=tips)
