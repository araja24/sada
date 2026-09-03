"""Tone/timbre similarity: extraction, then DTW-aligned scoring.

PRD §5.6: MFCCs are used to compare vocal *tone* between a reference
reciter and a user, never as a correctness signal.

**Framing requirement (product-level, not a naming nit):** this module (and
anything that prints its output) must call this "tone similarity," never
"correctness." Different voices legitimately differ -- a user's tone
scoring low means "your vocal timbre differs from this reciter's," never
"your voice is wrong." See PRD §5.6 and CONTEXT.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

from .align import AlignmentResult, path_indices_by_verse
from .melody import VoicedSeries
from .qf_client import VerseTimestamp

# PRD §5.6: "13-coefficient MFCC extraction (dropping c0)". We ask librosa
# for 13 coefficients (c0..c12) and drop c0 ourselves below, so the returned
# matrix has 12 rows.
N_MFCC = 13

HOP_LENGTH = 256


def extract_mfcc(
    y: np.ndarray, sr: int, hop_length: int = HOP_LENGTH, n_mfcc: int = N_MFCC
) -> np.ndarray:
    """Extract an MFCC matrix, shape (n_mfcc - 1, n_frames), with c0 dropped.

    c0 mostly reflects frame energy/loudness. We drop it because tone
    similarity should be about vocal timbre, not volume: a softly-spoken and
    a loudly-spoken recitation with the same vocal quality should still
    score as similar.

    Uses the same `hop_length` as `analysis.pitch.extract_pitch_contour`, so
    an MFCC column index lines up 1:1 with a pitch-contour frame index for
    the same audio -- this is what lets `score_tone` reuse melody's voiced
    frame indices to look up the right MFCC column for each aligned pair.
    """
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, hop_length=hop_length)
    return mfcc[1:, :]


@dataclass
class ToneScoreResult:
    overall_score: float
    per_verse_scores: dict[int, float]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two MFCC frame vectors, in [-1, 1].

    A zero vector (silence/no signal in that frame) has no defined
    direction, so we call it maximally dissimilar (0.0, the middle of the
    [-1, 1] range) rather than raising or returning a NaN that would
    silently poison an average.
    """
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def calibrate_tone_score(mean_cosine_similarity: float) -> float:
    """Map a mean cosine similarity ([-1, 1]) to a 0-100 score.

    Cosine similarity is already a bounded, roughly-linear similarity
    measure (1 = identical timbre direction, 0 = orthogonal, -1 = opposite),
    so this is a direct rescale rather than melody's hand-tuned
    exponential-decay calibration -- no extra constant to tune.
    """
    return max(0.0, min(100.0, (mean_cosine_similarity + 1.0) / 2.0 * 100.0))


def score_tone(
    user_mfcc: np.ndarray,
    ref_mfcc: np.ndarray,
    alignment: AlignmentResult,
    user_series: VoicedSeries,
    ref_series: VoicedSeries,
    ref_verses: list[VerseTimestamp] | None = None,
) -> ToneScoreResult:
    """Overall + per-verse tone-similarity scores.

    Deliberately reuses melody's alignment path (PRD §5.4: "the alignment
    path is reused by every other scorer") rather than computing a fresh
    DTW alignment on the MFCCs -- tone similarity is scored at exactly the
    same user-moment <-> reference-moment pairs that melody was, so a
    tip referencing a location means the same thing across dimensions.

    `user_series`/`ref_series` are the same `VoicedSeries` values used to
    produce `alignment` (see `analysis.melody.voiced_series`): their
    `frame_indices` map an aligned pair's position back to the original
    (unfiltered) frame grid that `user_mfcc`/`ref_mfcc` are indexed by.
    """
    similarities = np.array(
        [
            _cosine_similarity(
                user_mfcc[:, user_series.frame_indices[u]],
                ref_mfcc[:, ref_series.frame_indices[r]],
            )
            for u, r in alignment.path
        ]
    )
    overall_score = calibrate_tone_score(float(np.mean(similarities)))

    per_verse_scores: dict[int, float] = {}
    if ref_verses:
        indices_by_verse = path_indices_by_verse(alignment.path, ref_series.times, ref_verses)
        for verse_number, indices in indices_by_verse.items():
            if not indices:
                continue
            per_verse_scores[verse_number] = calibrate_tone_score(
                float(np.mean(similarities[indices]))
            )

    return ToneScoreResult(overall_score=overall_score, per_verse_scores=per_verse_scores)
