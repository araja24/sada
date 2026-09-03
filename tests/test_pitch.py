"""Unit tests for analysis.pitch -- pyin extraction, semitone conversion,
median-centering, and unvoiced-gap handling. No live API/network needed.
"""

from __future__ import annotations

import numpy as np
import pytest

from analysis import pitch

SR = 22050


def _sine(freq_hz: float, duration_s: float, sr: int = SR, amplitude: float = 0.8) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def test_hz_to_semitones_reference_pitch_is_zero():
    result = pitch.hz_to_semitones(np.array([pitch.SEMITONE_REFERENCE_HZ]))
    assert result[0] == pytest.approx(0.0, abs=1e-9)


def test_hz_to_semitones_octave_up_is_twelve_semitones():
    result = pitch.hz_to_semitones(np.array([pitch.SEMITONE_REFERENCE_HZ * 2]))
    assert result[0] == pytest.approx(12.0, abs=1e-6)


def test_hz_to_semitones_propagates_nan_for_unvoiced_input():
    result = pitch.hz_to_semitones(np.array([np.nan]))
    assert np.isnan(result[0])


def test_interpolate_short_gaps_fills_interior_gap():
    values = np.array([1.0, np.nan, np.nan, 4.0])
    filled = pitch._interpolate_short_gaps(values, max_gap_frames=2)
    assert not np.isnan(filled).any()
    np.testing.assert_allclose(filled, [1.0, 2.0, 3.0, 4.0])


def test_interpolate_short_gaps_leaves_long_gap_masked():
    values = np.array([1.0, np.nan, np.nan, np.nan, np.nan, 5.0])
    filled = pitch._interpolate_short_gaps(values, max_gap_frames=2)
    assert np.isnan(filled[1:5]).all()
    assert filled[0] == 1.0 and filled[5] == 5.0


def test_interpolate_short_gaps_leaves_leading_and_trailing_nan():
    values = np.array([np.nan, 1.0, 2.0, np.nan])
    filled = pitch._interpolate_short_gaps(values, max_gap_frames=5)
    assert np.isnan(filled[0])
    assert np.isnan(filled[-1])
    assert filled[1] == 1.0


def test_extract_pitch_contour_detects_expected_frequency():
    y = _sine(220.0, 1.0)  # comfortably inside fmin=65Hz/fmax=1047Hz
    contour = pitch.extract_pitch_contour(y, SR)

    assert contour.voiced_flag.any()
    voiced_f0 = contour.f0_hz[contour.voiced_flag]
    assert np.nanmean(voiced_f0) == pytest.approx(220.0, rel=0.05)


def test_extract_pitch_contour_frame_arrays_are_aligned():
    y = _sine(220.0, 1.0)
    contour = pitch.extract_pitch_contour(y, SR)

    n = len(contour.times)
    assert len(contour.f0_hz) == n
    assert len(contour.voiced_flag) == n
    assert len(contour.semitones) == n
    assert len(contour.semitones_centered) == n


def test_extract_pitch_contour_centers_on_its_own_median():
    y = _sine(220.0, 1.0)
    contour = pitch.extract_pitch_contour(y, SR)

    voiced_centered = contour.semitones_centered[contour.voiced_flag]
    assert np.nanmedian(voiced_centered) == pytest.approx(0.0, abs=0.5)


def test_extract_pitch_contour_is_transposition_invariant():
    """A constant tone an octave higher should still center near zero, just
    like the original -- proving comparisons happen on shape, not register
    (PRD §5.3)."""
    low = pitch.extract_pitch_contour(_sine(220.0, 1.0), SR)
    high = pitch.extract_pitch_contour(_sine(440.0, 1.0), SR)

    assert np.nanmedian(low.semitones_centered[low.voiced_flag]) == pytest.approx(0.0, abs=0.5)
    assert np.nanmedian(high.semitones_centered[high.voiced_flag]) == pytest.approx(0.0, abs=0.5)
    assert high.median_semitone - low.median_semitone == pytest.approx(12.0, abs=1.0)


def test_extract_pitch_contour_raises_on_silence():
    y = np.zeros(SR, dtype=np.float32)
    with pytest.raises(ValueError):
        pitch.extract_pitch_contour(y, SR)
