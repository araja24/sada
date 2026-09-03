"""Overall score: the weighted combination of the four sub-scores, plus the
qualitative label shown to the user.

PRD §5.9. The four dimension scorers (melody, pacing, tone, elongation) each
produce a 0-100 number independently; this is the only place they're
combined. Weights and label bands both live in `analysis.config` so a
tuning pass never touches this file.
"""

from __future__ import annotations

from . import config


def combine_overall_score(
    melody: float, pacing: float, tone: float, elongation: float
) -> float:
    """Weighted average of the four sub-scores (PRD §5.9).

    Weights (melody 45%, pacing 20%, tone 20%, elongation 15%) sum to 1.0,
    so the result is already on the same 0-100 scale as its inputs.
    """
    score = (
        config.MELODY_WEIGHT * melody
        + config.PACING_WEIGHT * pacing
        + config.TONE_WEIGHT * tone
        + config.ELONGATION_WEIGHT * elongation
    )
    return max(0.0, min(100.0, score))


def qualitative_label(overall_score: float) -> str:
    """Map an overall score to its encouraging qualitative label (PRD §5.9).

    Bands are checked from the top down; the last band's threshold is 0.0 so
    there is always a match.
    """
    for threshold, label in config.OVERALL_LABEL_BANDS:
        if overall_score >= threshold:
            return label
    # OVERALL_LABEL_BANDS always ends at 0.0, so this is unreachable in
    # practice -- kept as a defensive fallback rather than an IndexError.
    return config.OVERALL_LABEL_BANDS[-1][1]
