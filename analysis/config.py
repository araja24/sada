"""Scoring constants: weights, thresholds, calibration.

PRD §5.9: "All scoring constants (thresholds, weights, calibration) belong
in one config module for easy tuning." Kept separate from algorithm code
(align.py, melody.py, ...) so a hand-tuning pass against real test
recordings only ever touches this file.
"""

from __future__ import annotations

# --- Overall score: weighted average of the four dimensions (PRD §5.9) ---
# Only melody is implemented so far (M2); the rest are placeholders for
# when pacing/tone/elongation scorers land.
MELODY_WEIGHT = 0.45
PACING_WEIGHT = 0.20
TONE_WEIGHT = 0.20
ELONGATION_WEIGHT = 0.15

# --- DTW alignment (PRD §5.4) ---
# fastdtw's approximation radius. Higher = closer to exact DTW but slower;
# Al-Fatiha recordings are short (seconds, not minutes) so this can be
# generous without a real performance cost.
DTW_RADIUS = 10

# --- Melody score calibration (PRD §5.5) ---
# normalized DTW distance (mean semitone difference along the alignment
# path) -> 0-100 score via exponential decay: identical melodic contours
# (distance 0) score 100, and the score falls off smoothly as the
# contour diverges. Hand-tuned starting point -- PRD §5.5 explicitly
# expects this to be recalibrated against real test recordings.
MELODY_DECAY_RATE = 0.15

# --- Melody divergence detection, for tips (PRD §5.5) ---
MELODY_DIVERGENCE_SEMITONE_THRESHOLD = 3.0
MELODY_DIVERGENCE_MIN_DURATION_S = 0.5
