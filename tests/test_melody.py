"""Unit tests for analysis.melody -- calibration, per-verse scoring, and
divergence detection for tips. Uses small synthetic pitch contours rather
than real audio, so these run independent of any fixture audio/pyin call.
"""

from __future__ import annotations

import numpy as np
import pytest

from analysis import align, melody
from analysis.pitch import PitchContour
from analysis.qf_client import VerseTimestamp, WordTimestamp


def _contour(semitones_centered: np.ndarray, times: np.ndarray | None = None) -> PitchContour:
    if times is None:
        times = np.arange(len(semitones_centered), dtype=float) * 0.1  # 10 frames/sec
    n = len(semitones_centered)
    return PitchContour(
        times=times,
        f0_hz=np.full(n, np.nan),
        voiced_flag=~np.isnan(semitones_centered),
        semitones=semitones_centered,
        semitones_centered=semitones_centered,
        median_semitone=0.0,
    )


# --- calibrate_melody_score ---------------------------------------------


def test_calibrate_zero_distance_is_100():
    assert melody.calibrate_melody_score(0.0) == pytest.approx(100.0)


def test_calibrate_score_decreases_as_distance_grows():
    scores = [melody.calibrate_melody_score(d) for d in (0.0, 1.0, 5.0, 20.0)]
    assert scores == sorted(scores, reverse=True)


def test_calibrate_score_bounded_between_0_and_100():
    assert 0.0 <= melody.calibrate_melody_score(1000.0) <= 100.0
    assert 0.0 <= melody.calibrate_melody_score(0.0) <= 100.0


def test_calibrate_negative_distance_raises():
    with pytest.raises(ValueError):
        melody.calibrate_melody_score(-1.0)


# --- voiced_series --------------------------------------------------------


def test_voiced_series_drops_unvoiced_frames():
    contour = _contour(np.array([1.0, np.nan, 2.0, np.nan, 3.0]))
    series = melody.voiced_series(contour)
    np.testing.assert_allclose(series.semitones, [1.0, 2.0, 3.0])
    np.testing.assert_allclose(series.times, [0.0, 0.2, 0.4])


def test_voiced_series_all_unvoiced_raises():
    contour = _contour(np.full(5, np.nan))
    with pytest.raises(ValueError):
        melody.voiced_series(contour)


# --- score_melody: overall + per-verse ------------------------------------


def test_score_melody_identical_contours_scores_100():
    shape = np.array([0.0, 3.0, 5.0, 3.0, 0.0, -3.0, 0.0])
    user = _contour(shape.copy())
    ref = _contour(shape.copy())
    result = melody.score_melody(user, ref)
    assert result.overall_score == pytest.approx(100.0, abs=1e-6)


def test_score_melody_divergent_contours_scores_lower_than_identical():
    shape = np.array([0.0, 3.0, 5.0, 3.0, 0.0, -3.0, 0.0])
    flat = np.zeros_like(shape)
    identical = melody.score_melody(_contour(shape.copy()), _contour(shape.copy()))
    divergent = melody.score_melody(_contour(flat), _contour(shape.copy()))
    assert divergent.overall_score < identical.overall_score


def test_score_melody_per_verse_scores_split_by_reference_time():
    # 10 frames/sec (see _contour default); verse 1 = seconds [0, 0.4],
    # verse 2 = seconds [0.5, 0.9]. Verse 1 matches exactly, verse 2 is
    # flat in the user but melodic in the reference, so verse 2 should
    # score lower than verse 1.
    ref_shape = np.array([0.0, 2.0, 2.0, 0.0, 0.0, 4.0, -4.0, 4.0, -4.0, 0.0])
    user_shape = ref_shape.copy()
    user_shape[5:] = 0.0  # verse 2 diverges in the user's take
    verses = [
        VerseTimestamp(verse_key="1:1", timestamp_from_ms=0, timestamp_to_ms=400, words=[]),
        VerseTimestamp(verse_key="1:2", timestamp_from_ms=500, timestamp_to_ms=900, words=[]),
    ]
    result = melody.score_melody(_contour(user_shape), _contour(ref_shape), ref_verses=verses)
    assert set(result.per_verse_scores) == {1, 2}
    assert result.per_verse_scores[1] == pytest.approx(100.0, abs=1e-6)
    assert result.per_verse_scores[2] < result.per_verse_scores[1]


def test_score_melody_without_ref_verses_has_no_per_verse_scores():
    shape = np.array([0.0, 1.0, 0.0])
    result = melody.score_melody(_contour(shape.copy()), _contour(shape.copy()))
    assert result.per_verse_scores == {}


# --- detect_melody_divergences --------------------------------------------


def test_detect_divergences_finds_sustained_gap():
    # 10 frames/sec: a 6-semitone gap held for 8 frames = 0.7s > 0.5s min.
    ref = np.zeros(12)
    user = np.zeros(12)
    user[2:10] = 6.0  # user sings 6 semitones above the reference here
    result = melody.detect_melody_divergences(
        align.align_sequences(user, ref),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=user),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=ref),
    )
    assert len(result) == 1
    region = result[0]
    assert region.direction == "too_high"
    assert region.duration_s >= 0.5
    assert region.mean_diff_semitones == pytest.approx(6.0, abs=1e-6)


def test_detect_divergences_ignores_short_gap():
    # Same 6-semitone gap, but only 2 frames (0.1s) -- below the 0.5s minimum.
    ref = np.zeros(12)
    user = np.zeros(12)
    user[5:7] = 6.0
    result = melody.detect_melody_divergences(
        align.align_sequences(user, ref),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=user),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=ref),
    )
    assert result == []


def test_detect_divergences_direction_too_low():
    ref = np.zeros(12)
    user = np.zeros(12)
    user[2:10] = -6.0  # user sings below the reference
    result = melody.detect_melody_divergences(
        align.align_sequences(user, ref),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=user),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=ref),
    )
    assert len(result) == 1
    assert result[0].direction == "too_low"


def test_detect_divergences_maps_to_verse_and_word():
    ref = np.zeros(12)
    user = np.zeros(12)
    user[2:10] = 6.0  # spans ref times 0.2s..0.9s
    verses = [
        VerseTimestamp(
            verse_key="1:1",
            timestamp_from_ms=0,
            timestamp_to_ms=1200,
            words=[
                WordTimestamp(word_index=1, start_ms=0, end_ms=400),
                WordTimestamp(word_index=2, start_ms=400, end_ms=1200),
            ],
        )
    ]
    result = melody.detect_melody_divergences(
        align.align_sequences(user, ref),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=user),
        melody.VoicedSeries(times=np.arange(12) * 0.1, semitones=ref),
        ref_verses=verses,
    )
    assert len(result) == 1
    region = result[0]
    assert region.verse_number == 1
    # midpoint of [0.2s, 0.9s] is 0.55s = 550ms, inside word 2's [400, 1200).
    assert region.word_index == 2
