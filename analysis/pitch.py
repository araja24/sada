"""Pitch (f0/melody) extraction.

PRD §5.3: extract a pitch contour with librosa.pyin, convert it to
semitones, and median-center it so we compare melodic *shape* rather than
absolute register. This module is shared by the reference-building script
(M1) and, later, the live scoring pipeline (M2) -- both a reference
recitation and a user's take go through exactly the same function.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

# PRD §5.3: "roughly C2-C6".
FMIN_HZ = 65.0  # ~C2
FMAX_HZ = 1047.0  # ~C6

HOP_LENGTH = 256

# Reference pitch for the Hz -> semitone conversion. This value is
# arbitrary (it cancels out once we median-center below) -- it only fixes
# where "0 semitones" would sit before centering.
SEMITONE_REFERENCE_HZ = 55.0

# Unvoiced-frame gap (in frames) short enough to linearly interpolate across.
# At hop_length=256 / sr=22050 this is ~116 ms: long enough to bridge a brief
# voicing dropout in the middle of a sustained sound, short enough that we
# never paper over a real silence between words or verses. Gaps longer than
# this are left as NaN ("masked") rather than interpolated, since inventing a
# pitch value across a real pause would mislead DTW alignment and scoring.
DEFAULT_MAX_GAP_FRAMES = 10


@dataclass
class PitchContour:
    """The result of pitch extraction for one audio clip.

    Arrays are all frame-aligned (same length, same `times`).
    """

    times: np.ndarray  # frame center times, seconds
    f0_hz: np.ndarray  # raw f0 in Hz; NaN where pyin found no pitch
    voiced_flag: np.ndarray  # bool per frame, from pyin's voicing decision
    semitones: np.ndarray  # f0 in semitones (SEMITONE_REFERENCE_HZ-relative); NaN where unvoiced
    semitones_centered: np.ndarray  # semitones - median, short gaps interpolated
    median_semitone: float  # the value subtracted for centering


def hz_to_semitones(f0_hz: np.ndarray, reference_hz: float = SEMITONE_REFERENCE_HZ) -> np.ndarray:
    """Convert Hz to semitones relative to `reference_hz`.

    NaN in -> NaN out (unvoiced frames stay unvoiced); this is intentional,
    not an error, so we suppress numpy's divide/log warnings for NaN input.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return 12.0 * np.log2(f0_hz / reference_hz)


def _interpolate_short_gaps(values: np.ndarray, max_gap_frames: int) -> np.ndarray:
    """Linearly interpolate NaN runs of length <= max_gap_frames.

    Leading/trailing NaN runs (no value on one side) are never touched --
    there's nothing to interpolate *between*. Interior runs longer than
    max_gap_frames are also left as NaN: see the module docstring for why.
    """
    result = values.copy()
    n = len(result)
    nan_mask = np.isnan(result)
    if not nan_mask.any():
        return result

    i = 0
    while i < n:
        if not nan_mask[i]:
            i += 1
            continue
        j = i
        while j < n and nan_mask[j]:
            j += 1
        gap_len = j - i
        has_left = i > 0 and not np.isnan(result[i - 1])
        has_right = j < n and not np.isnan(result[j])
        if gap_len <= max_gap_frames and has_left and has_right:
            # linspace over gap_len+2 points includes both known endpoints;
            # drop them to fill in just the interior NaNs.
            result[i:j] = np.linspace(result[i - 1], result[j], gap_len + 2)[1:-1]
        i = j
    return result


def extract_pitch_contour(
    y: np.ndarray,
    sr: int,
    fmin: float = FMIN_HZ,
    fmax: float = FMAX_HZ,
    hop_length: int = HOP_LENGTH,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
) -> PitchContour:
    """Extract a transposition-invariant pitch contour from mono audio.

    Raises ValueError if pyin finds no voiced frames at all (silent or
    out-of-range audio) -- there is no sensible median to center on.
    """
    f0_hz, voiced_flag, _voiced_prob = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr, hop_length=hop_length
    )
    voiced_flag = voiced_flag.astype(bool)
    times = librosa.times_like(f0_hz, sr=sr, hop_length=hop_length)

    semitones = hz_to_semitones(f0_hz)

    voiced_semitones = semitones[voiced_flag]
    if voiced_semitones.size == 0:
        raise ValueError(
            "No voiced frames detected in audio; it may be silent, too quiet, "
            "or outside the expected pitch range."
        )
    median_semitone = float(np.nanmedian(voiced_semitones))

    # Transposition invariance (PRD §5.3, critical): subtract the reciter's/
    # user's own median pitch so we compare melodic shape, never absolute
    # register. A deeper or higher voice must never be penalized.
    centered = semitones - median_semitone
    centered = _interpolate_short_gaps(centered, max_gap_frames)

    return PitchContour(
        times=times,
        f0_hz=f0_hz,
        voiced_flag=voiced_flag,
        semitones=semitones,
        semitones_centered=centered,
        median_semitone=median_semitone,
    )
