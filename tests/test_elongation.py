"""Unit tests for analysis.elongation -- elongation-candidate detection
(local-median-relative word duration) and ratio-based scoring/tips.

Alignment is computed on a plain `np.arange(n)` "feature" sequence
(guaranteed 1:1 diagonal path -- see test_align.py / test_pacing.py),
decoupled from the `VoicedSeries.times` each test sets up independently,
for full control over exactly which user time each word maps to.
"""

from __future__ import annotations

import numpy as np
import pytest

from analysis import align, elongation
from analysis.melody import VoicedSeries
from analysis.qf_client import VerseTimestamp, WordTimestamp


def _word(index: int, start_ms: int, end_ms: int) -> WordTimestamp:
    return WordTimestamp(word_index=index, start_ms=start_ms, end_ms=end_ms)


def _series(times: list[float]) -> VoicedSeries:
    arr = np.array(times)
    return VoicedSeries(times=arr, semitones=np.zeros(len(arr)), frame_indices=np.arange(len(arr)))


def _diagonal_alignment(n: int) -> align.AlignmentResult:
    return align.align_sequences(np.arange(n, dtype=float), np.arange(n, dtype=float))


# --- calibrate_elongation_score ---------------------------------------------


def test_calibrate_elongation_score_ratio_of_one_is_100():
    assert elongation.calibrate_elongation_score(1.0) == pytest.approx(100.0)


def test_calibrate_elongation_score_symmetric():
    shorter = elongation.calibrate_elongation_score(0.5)
    longer = elongation.calibrate_elongation_score(2.0)
    assert shorter == pytest.approx(longer)


def test_calibrate_elongation_score_rejects_non_positive_ratio():
    with pytest.raises(ValueError):
        elongation.calibrate_elongation_score(0.0)


# --- find_elongation_candidates ---------------------------------------------


def test_find_elongation_candidates_flags_word_far_above_local_median():
    # Words at 300ms each except one held for 900ms (3x the 300ms median).
    words = [_word(i, i * 300, i * 300 + 300) for i in range(1, 4)] + [
        _word(4, 900, 1800)
    ] + [_word(i, 1800 + (i - 5) * 300, 1800 + (i - 5) * 300 + 300) for i in range(5, 8)]
    verse = VerseTimestamp(verse_key="1:1", timestamp_from_ms=0, timestamp_to_ms=2700, words=words)

    candidates = elongation.find_elongation_candidates([verse])

    assert [w.word_index for _v, w in candidates] == [4]


def test_find_elongation_candidates_ignores_words_within_threshold():
    # All words within 1.6x of each other -- no elongation candidates.
    words = [_word(i, i * 300, i * 300 + 300 + i * 20) for i in range(1, 6)]
    verse = VerseTimestamp(verse_key="1:1", timestamp_from_ms=0, timestamp_to_ms=2000, words=words)

    assert elongation.find_elongation_candidates([verse]) == []


def test_find_elongation_candidates_spans_verse_boundaries():
    # The long word sits right after a verse boundary; the window used to
    # judge it should still include neighboring words from the *previous*
    # verse (Al-Fatiha's verses are short -- a per-verse-only window would
    # often be too small to give a meaningful median).
    verse1 = VerseTimestamp(
        verse_key="1:1",
        timestamp_from_ms=0,
        timestamp_to_ms=900,
        words=[_word(i, i * 300, i * 300 + 300) for i in range(1, 4)],
    )
    verse2 = VerseTimestamp(
        verse_key="1:2",
        timestamp_from_ms=900,
        timestamp_to_ms=1800,
        words=[_word(1, 900, 1800)],  # 900ms, 3x the 300ms neighbors
    )

    candidates = elongation.find_elongation_candidates([verse1, verse2], window_radius=3)

    assert (verse2, verse2.words[0]) in candidates


# --- score_elongation ---------------------------------------------------------


def _verse_with_one_long_word() -> VerseTimestamp:
    # word 4 is 900ms, 3x its 300ms neighbors -> elongation candidate.
    words = [_word(i, i * 300, i * 300 + 300) for i in range(1, 4)] + [
        _word(4, 900, 1800)
    ] + [_word(i, 1800 + (i - 5) * 300, 1800 + (i - 5) * 300 + 300) for i in range(5, 8)]
    return VerseTimestamp(verse_key="1:1", timestamp_from_ms=0, timestamp_to_ms=2700, words=words)


def test_score_elongation_matching_duration_scores_100():
    verse = _verse_with_one_long_word()
    # 10 frames, 100ms apart, spanning the whole verse (0..900ms candidate
    # word range covered by frames 9 and 18 in seconds -> use finer steps).
    times = [i * 0.1 for i in range(28)]  # 0..2.7s, matches verse span
    alignment = _diagonal_alignment(28)

    result = elongation.score_elongation(alignment, _series(times), _series(times), [verse])

    assert len(result.candidates) == 1
    assert result.candidates[0].word_index == 4
    assert result.overall_score == pytest.approx(100.0, abs=1e-6)
    assert result.tips == []


def test_score_elongation_shortfall_scores_lower_and_generates_tip():
    verse = _verse_with_one_long_word()
    ref_times = [i * 0.1 for i in range(28)]
    # User's aligned frames for the candidate word (ref 0.9s-1.8s, indices
    # 9-18) are compressed into a much shorter user-time span.
    user_times = ref_times.copy()
    compressed = np.linspace(0.9, 1.1, 10)  # was 0.9s long, now ~0.2s
    for offset, i in enumerate(range(9, 19)):
        user_times[i] = compressed[offset]
    # keep the rest monotonic/after the compressed region
    for i in range(19, 28):
        user_times[i] = 1.1 + (ref_times[i] - 1.8)

    alignment = _diagonal_alignment(28)
    result = elongation.score_elongation(
        alignment, _series(user_times), _series(ref_times), [verse]
    )

    candidate = result.candidates[0]
    assert candidate.ratio < 1.0
    assert candidate.score < 100.0
    assert len(result.tips) == 1
    assert result.tips[0].kind == "shortfall"
    assert result.tips[0].word_index == 4


def test_score_elongation_no_candidates_scores_100():
    # Every word roughly the same length -- no elongation candidates at all.
    words = [_word(i, i * 300, i * 300 + 300 + i * 10) for i in range(1, 6)]
    verse = VerseTimestamp(verse_key="1:1", timestamp_from_ms=0, timestamp_to_ms=2000, words=words)
    times = [i * 0.1 for i in range(20)]
    alignment = _diagonal_alignment(20)

    result = elongation.score_elongation(alignment, _series(times), _series(times), [verse])

    assert result.candidates == []
    assert result.overall_score == pytest.approx(100.0)
    assert result.tips == []


def test_score_elongation_unaligned_word_has_no_score_but_no_crash():
    verse = _verse_with_one_long_word()
    # Alignment/series only cover the first 0.5s -- nothing reaches the
    # candidate word's [900, 1800]ms range at all.
    times = [0.0, 0.1, 0.2, 0.3, 0.4]
    alignment = _diagonal_alignment(5)

    result = elongation.score_elongation(alignment, _series(times), _series(times), [verse])

    assert len(result.candidates) == 1
    assert result.candidates[0].user_duration_s is None
    assert result.candidates[0].score is None
    assert result.overall_score == pytest.approx(100.0)  # no measured candidates -> no penalty
