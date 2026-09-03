"""Unit tests for analysis.pacing -- per-verse duration ratios (with global
tempo offset removed), pause analysis, and tip generation.

Alignment is deliberately computed on a plain `np.arange(n)` "feature"
sequence for both series (a guaranteed 1:1 diagonal path -- see
test_align.py), decoupled from the `VoicedSeries.times` each test sets up
independently. This gives full, predictable control over exactly which
user time each verse's boundary maps to, rather than fighting DTW's
value-based matching when the thing under test is duration math, not
alignment itself.
"""

from __future__ import annotations

import numpy as np
import pytest

from analysis import align, pacing
from analysis.melody import VoicedSeries
from analysis.qf_client import VerseTimestamp


def _verses(*spans_ms: tuple[int, int]) -> list[VerseTimestamp]:
    return [
        VerseTimestamp(
            verse_key=f"1:{i + 1}", timestamp_from_ms=start, timestamp_to_ms=end, words=[]
        )
        for i, (start, end) in enumerate(spans_ms)
    ]


def _series(times: list[float]) -> VoicedSeries:
    times = np.array(times)
    return VoicedSeries(times=times, semitones=np.zeros(len(times)), frame_indices=np.arange(len(times)))


def _diagonal_alignment(n: int) -> align.AlignmentResult:
    """A guaranteed 1:1 path: user frame i <-> ref frame i, for every i."""
    return align.align_sequences(np.arange(n, dtype=float), np.arange(n, dtype=float))


# --- calibrate_pacing_score --------------------------------------------------


def test_calibrate_pacing_score_ratio_of_one_is_100():
    assert pacing.calibrate_pacing_score(1.0) == pytest.approx(100.0)


def test_calibrate_pacing_score_symmetric_for_faster_and_slower():
    # Twice as fast (ratio 0.5) and twice as slow (ratio 2.0) are equally
    # far from the ideal ratio of 1.0 in log-space -- same score.
    faster = pacing.calibrate_pacing_score(0.5)
    slower = pacing.calibrate_pacing_score(2.0)
    assert faster == pytest.approx(slower)


def test_calibrate_pacing_score_decreases_away_from_one():
    scores = [pacing.calibrate_pacing_score(r) for r in (1.0, 1.2, 1.5, 3.0)]
    assert scores == sorted(scores, reverse=True)


def test_calibrate_pacing_score_rejects_non_positive_ratio():
    with pytest.raises(ValueError):
        pacing.calibrate_pacing_score(0.0)
    with pytest.raises(ValueError):
        pacing.calibrate_pacing_score(-1.0)


# --- score_pacing: per-verse durations + global-offset removal -------------


def test_score_pacing_matching_tempo_scores_100_everywhere():
    # 8 frames: verse 1 = ref frames 0-3 (times 0, 0.3, 0.6, 0.9s -> [0,900]ms),
    # verse 2 = ref frames 4-7 (times 1.0, 1.3, 1.6, 1.9s -> [1000,1900]ms).
    # User recites at exactly the same pace.
    ref_verses = _verses((0, 900), (1000, 1900))
    times = [0.0, 0.3, 0.6, 0.9, 1.0, 1.3, 1.6, 1.9]
    alignment = _diagonal_alignment(8)

    result = pacing.score_pacing(alignment, _series(times), _series(times), ref_verses)

    assert result.per_verse_scores[1] == pytest.approx(100.0, abs=1e-6)
    assert result.per_verse_scores[2] == pytest.approx(100.0, abs=1e-6)
    assert result.global_tempo_ratio == pytest.approx(1.0, abs=1e-6)


def test_score_pacing_uniform_slowdown_still_scores_verses_highly():
    # User takes exactly 1.5x as long on *every* verse (a uniform tempo
    # offset, not a per-verse anomaly) -- PRD: this should be scored gently
    # per-verse once the global offset is removed.
    ref_verses = _verses((0, 900), (1000, 1900))
    ref_times = [0.0, 0.3, 0.6, 0.9, 1.0, 1.3, 1.6, 1.9]
    user_times = [t * 1.5 for t in ref_times]
    alignment = _diagonal_alignment(8)

    result = pacing.score_pacing(alignment, _series(user_times), _series(ref_times), ref_verses)

    assert result.global_tempo_ratio == pytest.approx(1.5, abs=1e-6)
    assert result.per_verse_scores[1] == pytest.approx(100.0, abs=1e-6)
    assert result.per_verse_scores[2] == pytest.approx(100.0, abs=1e-6)


def test_score_pacing_single_verse_anomaly_scores_lower_than_others():
    # Verses 1-2 at normal pace, verse 3 rushed by the user specifically
    # (not a global offset) -- should score noticeably lower than the other
    # two, and should generate a "too_fast" tip.
    ref_verses = _verses((0, 900), (1000, 1900), (2000, 2900))
    ref_times = [0.0, 0.3, 0.6, 0.9, 1.0, 1.3, 1.6, 1.9, 2.0, 2.3, 2.6, 2.9]
    # Verses 1-2 identical to reference; verse 3 compressed to a third of
    # its reference duration (0.9s -> 0.3s).
    user_times = [0.0, 0.3, 0.6, 0.9, 1.0, 1.3, 1.6, 1.9, 2.0, 2.1, 2.2, 2.3]
    alignment = _diagonal_alignment(12)

    result = pacing.score_pacing(alignment, _series(user_times), _series(ref_times), ref_verses)

    assert result.per_verse_scores[3] < result.per_verse_scores[1]
    assert result.per_verse_scores[3] < result.per_verse_scores[2]
    tempo_tips = [t for t in result.tips if t.kind in ("too_fast", "too_slow")]
    assert any(t.verse_number == 3 and t.kind == "too_fast" for t in tempo_tips)


# --- pause analysis -----------------------------------------------------------


def test_score_pacing_flags_missing_pause():
    # Reference pauses 400ms between verse 1 (ends 1000ms) and verse 2
    # (starts 1400ms); the user's aligned times show almost no gap there.
    ref_verses = _verses((0, 1000), (1400, 2400))
    ref_times = [0.0, 0.5, 1.0, 1.4, 1.9, 2.4]
    user_times = [0.0, 0.5, 1.0, 1.01, 1.51, 2.01]  # ~10ms gap, not 400ms
    alignment = _diagonal_alignment(6)

    result = pacing.score_pacing(alignment, _series(user_times), _series(ref_times), ref_verses)

    pause_tips = [t for t in result.tips if t.kind == "missing_pause"]
    assert len(pause_tips) == 1
    assert pause_tips[0].verse_number == 1
    assert pause_tips[0].ref_pause_s == pytest.approx(0.4, abs=1e-6)
    assert pause_tips[0].user_pause_s == pytest.approx(0.01, abs=1e-6)


def test_score_pacing_does_not_flag_pause_user_actually_took():
    ref_verses = _verses((0, 1000), (1400, 2400))
    times = [0.0, 0.5, 1.0, 1.4, 1.9, 2.4]  # user matches the reference's pause exactly
    alignment = _diagonal_alignment(6)

    result = pacing.score_pacing(alignment, _series(times), _series(times), ref_verses)

    assert [t for t in result.tips if t.kind == "missing_pause"] == []


def test_score_pacing_ignores_reference_pauses_too_short_to_matter():
    # Reference pause is only 50ms (below PACING_MIN_REFERENCE_PAUSE_S) --
    # not a "clear" waqf, so no flag even though the user has ~no pause there.
    ref_verses = _verses((0, 1000), (1050, 2050))
    ref_times = [0.0, 0.5, 1.0, 1.05, 1.55, 2.05]
    user_times = [0.0, 0.5, 1.0, 1.0, 1.5, 2.0]
    alignment = _diagonal_alignment(6)

    result = pacing.score_pacing(alignment, _series(user_times), _series(ref_times), ref_verses)

    assert [t for t in result.tips if t.kind == "missing_pause"] == []
