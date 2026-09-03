"""Unit tests for analysis.tone -- MFCC extraction. No live API/network needed."""

from __future__ import annotations

import numpy as np
import pytest

from analysis import tone

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
