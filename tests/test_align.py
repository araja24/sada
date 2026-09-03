"""Unit tests for analysis.align -- the shared DTW alignment primitive."""

from __future__ import annotations

import numpy as np
import pytest

from analysis import align


def test_identical_sequences_have_zero_distance():
    seq = np.array([0.0, 1.0, 2.0, 3.0, 2.0, 1.0, 0.0])
    result = align.align_sequences(seq, seq)
    assert result.distance == pytest.approx(0.0, abs=1e-9)
    assert result.normalized_distance == pytest.approx(0.0, abs=1e-9)


def test_identical_sequences_produce_diagonal_path():
    seq = np.array([0.0, 1.0, 2.0, 3.0])
    result = align.align_sequences(seq, seq)
    assert result.path == [(0, 0), (1, 1), (2, 2), (3, 3)]


def test_time_stretched_but_same_shape_sequence_has_low_distance():
    # ref is user with one frame repeated (a slower delivery of the same
    # melodic shape) -- DTW should absorb the stretch and still find a
    # near-zero distance.
    user = np.array([0.0, 2.0, 4.0, 2.0, 0.0])
    ref = np.array([0.0, 2.0, 2.0, 4.0, 2.0, 0.0])
    result = align.align_sequences(user, ref)
    assert result.normalized_distance == pytest.approx(0.0, abs=1e-6)


def test_differently_shaped_sequence_has_higher_distance_than_identical():
    seq = np.array([0.0, 3.0, -3.0, 3.0, -3.0, 0.0])
    flat = np.zeros_like(seq)
    identical_result = align.align_sequences(seq, seq)
    divergent_result = align.align_sequences(seq, flat)
    assert divergent_result.normalized_distance > identical_result.normalized_distance


def test_path_indices_are_within_bounds():
    user = np.array([0.0, 1.0, 2.0])
    ref = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    result = align.align_sequences(user, ref)
    user_indices = [u for u, _r in result.path]
    ref_indices = [r for _u, r in result.path]
    assert min(user_indices) == 0 and max(user_indices) == len(user) - 1
    assert min(ref_indices) == 0 and max(ref_indices) == len(ref) - 1


def test_empty_sequence_raises():
    with pytest.raises(ValueError, match="empty"):
        align.align_sequences(np.array([]), np.array([1.0, 2.0]))


def test_nan_in_sequence_raises():
    with pytest.raises(ValueError, match="NaN"):
        align.align_sequences(np.array([1.0, np.nan, 3.0]), np.array([1.0, 2.0, 3.0]))
