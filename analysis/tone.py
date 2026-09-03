"""Tone/timbre feature extraction.

PRD §5.6: MFCCs are used to compare vocal *tone* between a reference
reciter and a user, never as a correctness signal. Framing this as
"tone similarity" (not "the right voice") is a product requirement, not
just a naming nit -- see PRD §5.6 and CONTEXT.md.
"""

from __future__ import annotations

import librosa
import numpy as np

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
    """
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, hop_length=hop_length)
    return mfcc[1:, :]
