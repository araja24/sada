"""Melody scoring: DTW-aligned pitch contour comparison.

PRD §5.5, the first scored dimension. Reuses analysis.align's generic DTW
primitive on median-centered pitch semitones (analysis.pitch), then:

1. calibrates the normalized DTW distance into an overall 0-100 score;
2. restricts the alignment path to each verse's reference-time span to
   get per-verse scores;
3. walks the alignment path for contiguous divergence regions (>3
   semitones apart for >0.5s) to generate specific, located tips.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import config
from .align import AlignmentResult, align_sequences, path_indices_by_verse
from .pitch import PitchContour
from .qf_client import VerseTimestamp


@dataclass
class VoicedSeries:
    """A pitch contour's voiced (non-NaN) frames, ready for DTW.

    fastdtw can't compare against a masked/unvoiced frame, so this is
    always `contour.times`/`semitones_centered` filtered down to the
    frames where a pitch was actually detected. `frame_indices` records
    which original (unfiltered) contour frame each entry came from, so
    other per-frame features that share the same frame grid -- MFCCs, in
    particular, since analysis.tone uses the same hop_length -- can be
    looked up for the same instants the alignment path was computed over
    (PRD §5.4: "the alignment path is reused by every other scorer").
    """

    times: np.ndarray
    semitones: np.ndarray
    frame_indices: np.ndarray


def voiced_series(contour: PitchContour) -> VoicedSeries:
    mask = ~np.isnan(contour.semitones_centered)
    if not mask.any():
        raise ValueError("Pitch contour has no voiced frames to align.")
    return VoicedSeries(
        times=contour.times[mask],
        semitones=contour.semitones_centered[mask],
        frame_indices=np.nonzero(mask)[0],
    )


@dataclass
class DivergenceRegion:
    """One contiguous stretch of the alignment path where the user's pitch
    diverges from the reference by more than the configured threshold, for
    long enough to be worth a tip.

    `start_s`/`end_s`/`verse_number`/`word_index` are all in *reference*
    time -- "where in the reciter's recitation this happened" -- since
    that's what's meaningful to point the user at. `duration_s` is instead
    measured in the *user's* time: DTW can compress a whole divergent
    stretch onto a handful of reference frames when absorbing a tempo
    difference, which would make a real, sustained divergence look
    instantaneous if duration were measured in reference time too.
    """

    start_s: float
    end_s: float
    duration_s: float
    direction: str  # "too_high" or "too_low" (the user's pitch, relative to reference)
    mean_diff_semitones: float
    verse_number: int | None = None
    word_index: int | None = None


@dataclass
class MelodyScoreResult:
    overall_score: float
    per_verse_scores: dict[int, float]
    alignment: AlignmentResult
    divergences: list[DivergenceRegion] = field(default_factory=list)


def calibrate_melody_score(normalized_distance: float) -> float:
    """Map a normalized DTW distance (mean semitone gap) to a 0-100 score.

    Exponential decay per PRD §5.5: an identical contour (distance 0)
    scores 100, and the score falls off smoothly as the contour diverges.
    `config.MELODY_DECAY_RATE` is a hand-tuned starting point, meant to be
    recalibrated against real test recordings.
    """
    if normalized_distance < 0:
        raise ValueError("normalized_distance must be >= 0.")
    score = 100.0 * math.exp(-config.MELODY_DECAY_RATE * normalized_distance)
    return max(0.0, min(100.0, score))


def score_melody(
    user_contour: PitchContour,
    ref_contour: PitchContour,
    ref_verses: list[VerseTimestamp] | None = None,
    radius: int = config.DTW_RADIUS,
) -> MelodyScoreResult:
    """Overall + per-verse melody scores, and divergence regions for tips.

    `ref_verses` is optional so this also works on a single verse's worth
    of contours with no verse-boundary metadata at all (per-verse scores
    and located tips just come back empty in that case).
    """
    user_series = voiced_series(user_contour)
    ref_series = voiced_series(ref_contour)

    alignment = align_sequences(user_series.semitones, ref_series.semitones, radius=radius)
    overall_score = calibrate_melody_score(alignment.normalized_distance)

    per_verse_scores: dict[int, float] = {}
    if ref_verses:
        indices_by_verse = path_indices_by_verse(alignment.path, ref_series.times, ref_verses)
        for verse_number, indices in indices_by_verse.items():
            if not indices:
                continue
            diffs = [
                user_series.semitones[u] - ref_series.semitones[r]
                for u, r in (alignment.path[i] for i in indices)
            ]
            verse_normalized_distance = float(np.mean(np.abs(diffs)))
            per_verse_scores[verse_number] = calibrate_melody_score(verse_normalized_distance)

    divergences = detect_melody_divergences(
        alignment, user_series, ref_series, ref_verses=ref_verses
    )

    return MelodyScoreResult(
        overall_score=overall_score,
        per_verse_scores=per_verse_scores,
        alignment=alignment,
        divergences=divergences,
    )


def detect_melody_divergences(
    alignment: AlignmentResult,
    user_series: VoicedSeries,
    ref_series: VoicedSeries,
    ref_verses: list[VerseTimestamp] | None = None,
    threshold_semitones: float = config.MELODY_DIVERGENCE_SEMITONE_THRESHOLD,
    min_duration_s: float = config.MELODY_DIVERGENCE_MIN_DURATION_S,
) -> list[DivergenceRegion]:
    """Find contiguous, same-direction stretches of the alignment path where
    |user - reference| exceeds `threshold_semitones` for at least
    `min_duration_s` (PRD §5.5), and map each to a verse/word via
    `ref_verses` when given.
    """
    diffs = np.array(
        [user_series.semitones[u] - ref_series.semitones[r] for u, r in alignment.path]
    )
    ref_times_path = np.array([ref_series.times[r] for _u, r in alignment.path])
    user_times_path = np.array([user_series.times[u] for u, _r in alignment.path])

    regions: list[DivergenceRegion] = []
    n = len(diffs)
    i = 0
    while i < n:
        if abs(diffs[i]) <= threshold_semitones:
            i += 1
            continue
        sign = np.sign(diffs[i])
        j = i
        while j < n and abs(diffs[j]) > threshold_semitones and np.sign(diffs[j]) == sign:
            j += 1

        start_s = float(ref_times_path[i])
        end_s = float(ref_times_path[j - 1])
        # Duration is measured in the *user's* time, not the reference's:
        # DTW can compress a whole divergent stretch onto a handful of
        # reference frames (the warp absorbs a tempo difference), which
        # would make a real, sustained divergence look instantaneous if we
        # measured duration in reference time instead.
        duration_s = float(user_times_path[j - 1] - user_times_path[i])
        if duration_s >= min_duration_s:
            mean_diff = float(np.mean(diffs[i:j]))
            region = DivergenceRegion(
                start_s=start_s,
                end_s=end_s,
                duration_s=duration_s,
                direction="too_high" if mean_diff > 0 else "too_low",
                mean_diff_semitones=mean_diff,
            )
            if ref_verses:
                _annotate_verse_and_word(region, ref_verses)
            regions.append(region)
        i = j
    return regions


def _annotate_verse_and_word(region: DivergenceRegion, ref_verses: list[VerseTimestamp]) -> None:
    midpoint_ms = (region.start_s + region.end_s) / 2.0 * 1000.0
    for verse in ref_verses:
        if verse.timestamp_from_ms <= midpoint_ms <= verse.timestamp_to_ms:
            region.verse_number = verse.verse_number
            for word in verse.words:
                if word.start_ms <= midpoint_ms <= word.end_ms:
                    region.word_index = word.word_index
                    break
            break
