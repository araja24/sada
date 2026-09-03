"""Pacing scoring: per-verse tempo ratio (with global offset removed) and
inter-verse pause (waqf) analysis.

PRD §5.7. Reuses melody's alignment path (PRD §5.4: "the alignment path is
reused by every other scorer") to find, for each reference verse, the span
of *user* time that aligns to it -- there's no independent way to detect
verse boundaries in the user's own audio, so the alignment is the only
source of "where did the user's verse 3 start and end."
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import config
from .align import AlignmentResult, path_indices_by_verse
from .melody import VoicedSeries
from .qf_client import VerseTimestamp


@dataclass
class PacingTip:
    """One pacing issue worth surfacing to the user.

    `kind` is `"too_fast"`/`"too_slow"` (a verse's own tempo, relative to
    the passage's average pace, per `percent_off`) or `"missing_pause"` (a
    reference pause the user didn't take, per `ref_pause_s`/`user_pause_s`).
    Only the fields relevant to `kind` are populated.
    """

    verse_number: int
    kind: str
    percent_off: float | None = None
    ref_pause_s: float | None = None
    user_pause_s: float | None = None


@dataclass
class PacingScoreResult:
    overall_score: float
    global_tempo_ratio: float  # user/reference duration ratio across the whole scored range
    per_verse_scores: dict[int, float]
    tips: list[PacingTip] = field(default_factory=list)


def calibrate_pacing_score(ratio: float) -> float:
    """Map a duration ratio (user/reference, or a residual thereof) to 0-100.

    Symmetric exponential decay in log-space: ratio 1.0 (identical pace)
    scores 100, and ratio 2.0 (twice as slow) scores the same as ratio 0.5
    (twice as fast) -- speeding up and slowing down by the same factor are
    equally far from the ideal. `config.PACING_DECAY_RATE` is a hand-tuned
    starting point, meant to be recalibrated against real test recordings.
    """
    if ratio <= 0:
        raise ValueError("ratio must be > 0 (it's a duration ratio).")
    score = 100.0 * math.exp(-config.PACING_DECAY_RATE * abs(math.log(ratio)))
    return max(0.0, min(100.0, score))


def _verse_user_span_s(
    path: list[tuple[int, int]], indices: list[int], user_series: VoicedSeries
) -> tuple[float, float] | None:
    """(start, end) of the user time span aligned to this verse's path positions."""
    if not indices:
        return None
    user_times = [user_series.times[path[i][0]] for i in indices]
    return min(user_times), max(user_times)


def score_pacing(
    alignment: AlignmentResult,
    user_series: VoicedSeries,
    ref_series: VoicedSeries,
    ref_verses: list[VerseTimestamp],
) -> PacingScoreResult:
    """Per-verse pacing scores (global tempo offset removed) + pause tips.

    `ref_verses` is required (unlike melody/tone's optional verse list):
    pacing has no meaning without at least two verses to compare a tempo
    or a pause against.
    """
    if len(ref_verses) < 1:
        raise ValueError("score_pacing needs at least one reference verse.")

    indices_by_verse = path_indices_by_verse(alignment.path, ref_series.times, ref_verses)

    user_spans: dict[int, tuple[float, float]] = {}
    ref_durations_s: dict[int, float] = {}
    for verse in ref_verses:
        span = _verse_user_span_s(alignment.path, indices_by_verse[verse.verse_number], user_series)
        if span is None:
            continue  # no aligned frames landed in this verse; skip it, not a 0
        user_spans[verse.verse_number] = span
        ref_durations_s[verse.verse_number] = verse.duration_ms / 1000.0

    total_user_s = sum(end - start for start, end in user_spans.values())
    total_ref_s = sum(ref_durations_s.values())
    if total_ref_s <= 0 or total_user_s <= 0:
        raise ValueError("Could not measure any verse duration from the alignment path.")
    global_tempo_ratio = total_user_s / total_ref_s

    per_verse_scores: dict[int, float] = {}
    tips: list[PacingTip] = []
    for verse_number, (start, end) in user_spans.items():
        user_duration_s = end - start
        ref_duration_s = ref_durations_s[verse_number]
        raw_ratio = user_duration_s / ref_duration_s
        residual_ratio = raw_ratio / global_tempo_ratio
        per_verse_scores[verse_number] = calibrate_pacing_score(residual_ratio)

        percent_off = (residual_ratio - 1.0) * 100.0
        if abs(percent_off) > config.PACING_TIP_THRESHOLD_PERCENT:
            tips.append(
                PacingTip(
                    verse_number=verse_number,
                    kind="too_fast" if percent_off < 0 else "too_slow",
                    percent_off=percent_off,
                )
            )

    tips.extend(_pause_tips(ref_verses, user_spans))

    overall_score = float(np.mean(list(per_verse_scores.values()))) if per_verse_scores else 0.0
    return PacingScoreResult(
        overall_score=overall_score,
        global_tempo_ratio=global_tempo_ratio,
        per_verse_scores=per_verse_scores,
        tips=tips,
    )


def _pause_tips(
    ref_verses: list[VerseTimestamp], user_spans: dict[int, tuple[float, float]]
) -> list[PacingTip]:
    """Flag reference pauses (waqf) the user didn't take, between consecutive verses."""
    tips: list[PacingTip] = []
    for current, following in zip(ref_verses, ref_verses[1:]):
        ref_pause_s = (following.timestamp_from_ms - current.timestamp_to_ms) / 1000.0
        if ref_pause_s < config.PACING_MIN_REFERENCE_PAUSE_S:
            continue  # not a clear pause in the reference; nothing to compare against
        if current.verse_number not in user_spans or following.verse_number not in user_spans:
            continue  # can't measure a pause we have no aligned span on either side of
        user_pause_s = user_spans[following.verse_number][0] - user_spans[current.verse_number][1]
        if user_pause_s < ref_pause_s * config.PACING_SHORT_PAUSE_RATIO:
            tips.append(
                PacingTip(
                    verse_number=current.verse_number,
                    kind="missing_pause",
                    ref_pause_s=ref_pause_s,
                    user_pause_s=max(0.0, user_pause_s),
                )
            )
    return tips
