"""Unit tests for analysis.tone -- MFCC extraction and DTW-aligned tone
scoring. No live API/network needed.
"""

from __future__ import annotations

import numpy as np
import pytest

from analysis import align, tone
from analysis.melody import VoicedSeries
from analysis.qf_client import VerseTimestamp

SR = 22050


def _sine(freq_hz: float, duration_s: float, sr: int = SR, amplitude: float = 0.8) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def test_extract_mfcc_drops_c0():
    y = _sine(220.0, 1.0)
    mfcc = tone.extract_mfcc(y, SR)
    assert mfcc.shape[0] == tone.N_MFCC - 1


def test_extract_mfcc_frame_count_matches_hop_length():
    y = _sine(220.0, 1.0)
    mfcc = tone.extract_mfcc(y, SR, hop_length=256)
    expected_frames = 1 + len(y) // 256
    assert mfcc.shape[1] == pytest.approx(expected_frames, abs=2)


def test_extract_mfcc_differs_for_different_timbres_at_same_pitch():
    """A pure sine vs. a harmonically rich tone at the same fundamental
    should yield different MFCCs -- evidence MFCCs capture timbre, not just
    pitch."""
    sine = _sine(220.0, 1.0)
    t = np.linspace(0, 1.0, SR, endpoint=False)
    rich = (
        0.5 * np.sin(2 * np.pi * 220 * t)
        + 0.3 * np.sin(2 * np.pi * 440 * t)
        + 0.2 * np.sin(2 * np.pi * 660 * t)
    ).astype(np.float32)

    mfcc_sine = tone.extract_mfcc(sine, SR)
    mfcc_rich = tone.extract_mfcc(rich, SR)

    assert not np.allclose(mfcc_sine.mean(axis=1), mfcc_rich.mean(axis=1), atol=0.5)


# --- _cosine_similarity / calibrate_tone_score ------------------------------


def test_cosine_similarity_identical_vectors_is_one():
    v = np.array([1.0, 2.0, 3.0])
    assert tone._cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert tone._cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_negative_one():
    a = np.array([1.0, 2.0])
    assert tone._cosine_similarity(a, -a) == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector_is_zero_not_nan():
    assert tone._cosine_similarity(np.zeros(3), np.array([1.0, 2.0, 3.0])) == 0.0


def test_calibrate_tone_score_maps_similarity_range_to_0_100():
    assert tone.calibrate_tone_score(1.0) == pytest.approx(100.0)
    assert tone.calibrate_tone_score(-1.0) == pytest.approx(0.0)
    assert tone.calibrate_tone_score(0.0) == pytest.approx(50.0)


# --- score_tone --------------------------------------------------------------


def _voiced_series(n: int, hop: float = 0.1) -> VoicedSeries:
    return VoicedSeries(times=np.arange(n) * hop, semitones=np.zeros(n), frame_indices=np.arange(n))


def test_score_tone_identical_mfccs_scores_100():
    mfcc = np.random.RandomState(0).randn(12, 10)
    alignment = align.align_sequences(np.arange(10, dtype=float), np.arange(10, dtype=float))
    result = tone.score_tone(mfcc, mfcc, alignment, _voiced_series(10), _voiced_series(10))
    assert result.overall_score == pytest.approx(100.0, abs=1e-6)


def test_score_tone_different_timbre_scores_lower_than_identical():
    rng = np.random.RandomState(0)
    ref_mfcc = rng.randn(12, 10)
    user_mfcc_identical = ref_mfcc.copy()
    user_mfcc_different = rng.randn(12, 10)  # unrelated timbre
    alignment = align.align_sequences(np.arange(10, dtype=float), np.arange(10, dtype=float))

    identical = tone.score_tone(
        user_mfcc_identical, ref_mfcc, alignment, _voiced_series(10), _voiced_series(10)
    )
    different = tone.score_tone(
        user_mfcc_different, ref_mfcc, alignment, _voiced_series(10), _voiced_series(10)
    )
    assert different.overall_score < identical.overall_score


def test_score_tone_per_verse_scores_split_by_reference_time():
    rng = np.random.RandomState(0)
    ref_mfcc = rng.randn(12, 10)
    user_mfcc = ref_mfcc.copy()
    # Verse 2 = ref frames 5-9 (times 500-900ms, see verses below); make the
    # user's timbre diverge only there.
    user_mfcc[:, 5:] = rng.randn(12, 5)
    alignment = align.align_sequences(np.arange(10, dtype=float), np.arange(10, dtype=float))
    verses = [
        VerseTimestamp(verse_key="1:1", timestamp_from_ms=0, timestamp_to_ms=400, words=[]),
        VerseTimestamp(verse_key="1:2", timestamp_from_ms=500, timestamp_to_ms=900, words=[]),
    ]
    result = tone.score_tone(
        user_mfcc, ref_mfcc, alignment, _voiced_series(10), _voiced_series(10), ref_verses=verses
    )
    assert set(result.per_verse_scores) == {1, 2}
    assert result.per_verse_scores[1] == pytest.approx(100.0, abs=1e-6)
    assert result.per_verse_scores[2] < result.per_verse_scores[1]


def test_score_tone_maps_alignment_indices_through_voiced_frame_indices():
    # Only even-numbered raw frames are "voiced": the MFCC matrix has 20 raw
    # columns but the VoicedSeries (and therefore the alignment path) only
    # covers 10 of them. score_tone must look up the *raw* frame_indices,
    # not treat the voiced-series position as the MFCC column directly.
    rng = np.random.RandomState(0)
    mfcc_full = rng.randn(12, 20)
    frame_indices = np.arange(0, 20, 2)
    series = VoicedSeries(times=frame_indices * 0.1, semitones=np.zeros(10), frame_indices=frame_indices)
    alignment = align.align_sequences(np.arange(10, dtype=float), np.arange(10, dtype=float))

    result = tone.score_tone(mfcc_full, mfcc_full, alignment, series, series)
    assert result.overall_score == pytest.approx(100.0, abs=1e-6)
