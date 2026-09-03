"""Unit tests for analysis/overall.py (PRD §5.9)."""

from __future__ import annotations

import pytest

from analysis import config
from analysis.overall import combine_overall_score, qualitative_label


def test_combine_is_weighted_average():
    # All 80 -> 80, regardless of the weight split.
    assert combine_overall_score(80, 80, 80, 80) == pytest.approx(80.0)


def test_combine_weights_melody_most():
    # Melody 100, everything else 0: result is exactly the melody weight * 100.
    assert combine_overall_score(100, 0, 0, 0) == pytest.approx(config.MELODY_WEIGHT * 100)


def test_combine_clamps_to_0_100():
    assert combine_overall_score(200, 200, 200, 200) == 100.0
    assert combine_overall_score(-50, -50, -50, -50) == 0.0


@pytest.mark.parametrize(
    "score,expected",
    [
        (95, "Very close"),
        (85, "Very close"),
        (84, "Getting close"),
        (70, "Getting close"),
        (69, "On your way"),
        (50, "On your way"),
        (49, "Keep practicing"),
        (0, "Keep practicing"),
    ],
)
def test_qualitative_label_bands(score, expected):
    assert qualitative_label(score) == expected


def test_labels_are_encouraging_never_gamified():
    labels = [label for _threshold, label in config.OVERALL_LABEL_BANDS]
    joined = " ".join(labels).lower()
    for banned in ("fail", "wrong", "bad", "loser", "score of shame"):
        assert banned not in joined
