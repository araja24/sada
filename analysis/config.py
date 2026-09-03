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

# --- Pacing score calibration (PRD §5.7) ---
# Per-verse pacing is scored on the *residual* ratio -- the verse's own
# user/reference duration ratio, divided by the whole-passage tempo ratio --
# so a uniformly slower/faster reciter isn't penalized per-verse for
# something that's really one global offset (PRD: "reciting uniformly
# slower is less of an error than rushing one verse"). Scored via
# exponential decay on |ln(residual_ratio)|, symmetric in speeding up vs.
# slowing down: a verse recited at exactly the passage's own average pace
# scores 100; the further its ratio departs from that average (either
# direction), the lower the score.
PACING_DECAY_RATE = 1.5

# A tip fires when a verse's residual ratio implies it was recited more
# than this percentage faster/slower than the passage's own average pace
# (PRD §5.7: "verses >25% faster/slower... after removing global tempo
# offset").
PACING_TIP_THRESHOLD_PERCENT = 25.0

# Inter-verse pauses shorter than this in the *reference* aren't treated as
# a clear waqf (stop) -- there's nothing meaningful to compare the user's
# pause against.
PACING_MIN_REFERENCE_PAUSE_S = 0.2

# A user's pause is flagged as missing/short when it's under this fraction
# of the reference's pause at the same verse boundary.
PACING_SHORT_PAUSE_RATIO = 0.5
