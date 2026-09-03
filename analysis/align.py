"""DTW sequence alignment -- the primitive every dimension scorer reuses.

PRD §5.4: run DTW (fastdtw) between the user's and reference's normalized
feature sequences for the selected verse range, to find a time alignment
that's robust to differences in delivery speed/pausing. Melody aligns
median-centered pitch semitones; later scorers (tone, elongation) reuse
this same function on their own per-frame feature sequences, so there is
exactly one alignment algorithm in the codebase, not one per dimension.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from fastdtw import fastdtw

from . import config


@dataclass
class AlignmentResult:
    """The result of aligning two 1-D feature sequences.

    `path` holds (user_index, ref_index) pairs in path order -- indices
    into the two arrays that were passed to `align_sequences`, in the
    order fastdtw visited them.
    """

    path: list[tuple[int, int]]
    distance: float  # raw cumulative DTW distance
    normalized_distance: float  # distance / len(path); length-independent


def align_sequences(
    user_values: np.ndarray,
    ref_values: np.ndarray,
    radius: int = config.DTW_RADIUS,
) -> AlignmentResult:
    """Align two 1-D sequences with fastdtw.

    Both sequences must be finite (no NaN) -- fastdtw's distance function
    can't compare against a masked/unvoiced frame, so callers must filter
    those out first (see `analysis.melody.voiced_series`).
    """
    user_values = np.asarray(user_values, dtype=float)
    ref_values = np.asarray(ref_values, dtype=float)

    if user_values.size == 0 or ref_values.size == 0:
        raise ValueError("Cannot align an empty sequence.")
    if np.isnan(user_values).any() or np.isnan(ref_values).any():
        raise ValueError(
            "align_sequences requires NaN-free sequences; filter unvoiced/masked "
            "frames out before aligning."
        )

    distance, path = fastdtw(user_values, ref_values, radius=radius)
    normalized_distance = distance / len(path)
    return AlignmentResult(
        path=path, distance=float(distance), normalized_distance=float(normalized_distance)
    )
