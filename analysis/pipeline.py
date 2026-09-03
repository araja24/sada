"""The full analysis pipeline: one audio file + one reference bundle -> a
scored result, or a friendly failure.

PRD §5 end to end. This is the single entry point both the CLI
(`scripts/compare.py`) and the API (issue #7) call, so failure-mode
handling and the result shape live in exactly one place.

The four dimension scorers (melody/pacing/tone/elongation) are still their
own modules and still independently testable; this module only orchestrates
them, checks §5.10 failure modes, and assembles the §6 result shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config, elongation, pacing, pitch, tone
from .melody import MelodyScoreResult, score_melody, voiced_series
from .overall import combine_overall_score, qualitative_label
from .qf_client import VerseTimestamp


# --- Failure modes (PRD §5.10) -------------------------------------------
# All user-facing; the API (issue #7) maps each to a clean 4xx response and
# the CLI prints `.message`. `AnalysisError` is the catch-all base.


class AnalysisError(RuntimeError):
    """Base class for every user-facing analysis failure."""


class UnreadableAudioError(AnalysisError):
    """Upload couldn't be decoded/converted to audio at all (bad codec)."""


class AudioDurationError(AnalysisError):
    """Audio is shorter than 2s or longer than 3min after trimming."""


class SilentAudioError(AnalysisError):
    """No pitch anywhere -- essentially silence."""


class NoisyAudioError(AnalysisError):
    """Too few voiced frames to score -- ask for a quieter re-record."""


class PassageMismatchError(AnalysisError):
    """The recording doesn't line up with the selected verses at all."""


# --- Result shape (PRD §6) ---------------------------------------------


@dataclass
class Tip:
    """One located, encouraging improvement tip (PRD §4/§6).

    `word_index` is None for verse-level tips (pacing). `type` is one of
    "melody", "pacing", "elongation".
    """

    verse: int
    type: str
    text: str
    word_index: int | None = None


@dataclass
class PitchOverlay:
    """Reference vs. user pitch contour on a shared normalized time axis
    (PRD §6, the results-page centerpiece).

    `time_axis` runs 0..1 across the selected verse range. All three arrays
    are the same length.
    """

    time_axis: list[float]
    reference_semitones: list[float]
    user_semitones_aligned: list[float]


@dataclass
class AttemptResult:
    overall_score: int
    label: str
    sub_scores: dict[str, int]
    per_verse: list[dict]  # [{"verse": int, "score": int}]
    pitch_overlay: PitchOverlay
    tips: list[Tip] = field(default_factory=list)


@dataclass
class ReferenceBundle:
    """A reciter's cached Al-Fatiha reference features (M1 output).

    Loaded once from disk (see `load_reference_bundle`) and reused across
    requests -- never re-fetched from the API per attempt (PRD §3).
    """

    slug: str
    contour: pitch.PitchContour
    mfcc: np.ndarray
    verses: list[VerseTimestamp]

    def verses_in_range(self, start_verse: int, end_verse: int) -> list[VerseTimestamp]:
        return [v for v in self.verses if start_verse <= v.verse_number <= end_verse]


PITCH_OVERLAY_POINTS = 200


def analyze(
    audio_path: str | Path,
    bundle: ReferenceBundle,
    start_verse: int,
    end_verse: int,
) -> AttemptResult:
    """Run the full pipeline for one recitation against one reference range.

    Raises an `AnalysisError` subclass for every PRD §5.10 failure mode;
    raises `ValueError` for programmer errors (empty verse range, etc.).
    """
    verses = bundle.verses_in_range(start_verse, end_verse)
    if not verses:
        raise ValueError(
            f"No reference verses in range {start_verse}-{end_verse} "
            f"for reciter {bundle.slug!r}."
        )

    y, sr = _load_user_audio(audio_path)
    _check_duration(y, sr)
    user_contour = _extract_user_pitch(y, sr)
    _check_voiced_ratio(user_contour)
    user_mfcc = tone.extract_mfcc(y, sr)

    melody_result = score_melody(user_contour, bundle.contour, ref_verses=verses)
    _check_passage_match(melody_result)

    user_vs = voiced_series(user_contour)
    ref_vs = voiced_series(bundle.contour)

    tone_result = tone.score_tone(
        user_mfcc, bundle.mfcc, melody_result.alignment, user_vs, ref_vs, ref_verses=verses
    )
    pacing_result = pacing.score_pacing(melody_result.alignment, user_vs, ref_vs, ref_verses=verses)
    elongation_result = elongation.score_elongation(
        melody_result.alignment, user_vs, ref_vs, ref_verses=verses
    )

    sub_scores = {
        "melody": round(melody_result.overall_score),
        "pacing": round(pacing_result.overall_score),
        "tone": round(tone_result.overall_score),
        "elongation": round(elongation_result.overall_score),
    }
    overall = combine_overall_score(
        melody_result.overall_score,
        pacing_result.overall_score,
        tone_result.overall_score,
        elongation_result.overall_score,
    )

    return AttemptResult(
        overall_score=round(overall),
        label=qualitative_label(overall),
        sub_scores=sub_scores,
        per_verse=_per_verse_scores(verses, melody_result, tone_result, pacing_result),
        pitch_overlay=_build_pitch_overlay(melody_result, user_vs, ref_vs),
        tips=_collect_tips(melody_result, pacing_result, elongation_result),
    )


# --- Loading -----------------------------------------------------------


def load_reference_bundle(reciter_dir: str | Path) -> ReferenceBundle:
    """Load a cached reference bundle from data/reference/<slug>/ (M1 output)."""
    reciter_dir = Path(reciter_dir)
    features_path = reciter_dir / "features.npz"
    timestamps_path = reciter_dir / "timestamps.json"
    if not features_path.exists() or not timestamps_path.exists():
        raise FileNotFoundError(
            f"No cached reference bundle at {reciter_dir}. "
            "Run scripts/build_reference.py for this reciter first."
        )

    features = np.load(features_path)
    contour = pitch.PitchContour(
        times=features["pitch_times"],
        f0_hz=features["f0_hz"],
        voiced_flag=features["voiced_flag"],
        semitones=features["semitones"],
        semitones_centered=features["semitones_centered"],
        median_semitone=float(features["median_semitone"]),
    )

    import json

    data = json.loads(timestamps_path.read_text(encoding="utf-8"))
    verses = [
        VerseTimestamp(
            verse_key=v.get("verse_key", f"1:{v['verse_number']}"),
            timestamp_from_ms=v["timestamp_from_ms"],
            timestamp_to_ms=v["timestamp_to_ms"],
            words=[
                _word_ts(w) for w in v["words"]
            ],
        )
        for v in data["verses"]
    ]
    return ReferenceBundle(
        slug=reciter_dir.name, contour=contour, mfcc=features["mfcc"], verses=verses
    )


def _word_ts(w: dict):
    from .qf_client import WordTimestamp

    return WordTimestamp(word_index=w["word_index"], start_ms=w["start_ms"], end_ms=w["end_ms"])


# --- Failure-mode checks (PRD §5.10) ----------------------------------


def _load_user_audio(audio_path: str | Path):
    from . import audio_io

    try:
        y, sr, _trim = audio_io.load_and_preprocess(audio_path)
    except AnalysisError:
        raise
    except Exception as exc:  # noqa: BLE001 - any decode/convert failure is one user-facing error
        raise UnreadableAudioError(
            "We couldn't read that audio file. Try recording again, or upload a "
            "different format (webm, ogg, wav, mp3, or m4a)."
        ) from exc
    return y, sr


def _check_duration(y: np.ndarray, sr: int) -> None:
    duration_s = len(y) / sr
    if duration_s < config.MIN_AUDIO_DURATION_S:
        raise AudioDurationError(
            "That recording is too short to analyze -- it needs to be at least "
            f"{config.MIN_AUDIO_DURATION_S:.0f} seconds. Try reciting the whole verse range."
        )
    if duration_s > config.MAX_AUDIO_DURATION_S:
        raise AudioDurationError(
            f"That recording is longer than the {config.MAX_AUDIO_DURATION_S / 60:.0f}-minute "
            "limit. Record a shorter verse range."
        )


def _extract_user_pitch(y: np.ndarray, sr: int) -> pitch.PitchContour:
    try:
        return pitch.extract_pitch_contour(y, sr)
    except ValueError as exc:
        raise SilentAudioError(
            "We couldn't hear any recitation in that recording. Check your "
            "microphone and try again."
        ) from exc


def _check_voiced_ratio(contour: pitch.PitchContour) -> None:
    total = len(contour.voiced_flag)
    if total == 0:
        raise SilentAudioError("That recording had no audio to analyze.")
    voiced_ratio = float(np.count_nonzero(contour.voiced_flag)) / total
    if voiced_ratio < config.MIN_VOICED_FRAME_RATIO:
        raise NoisyAudioError(
            "That recording is too noisy or quiet for us to follow the melody. "
            "Try re-recording somewhere quieter, closer to the microphone."
        )


def _check_passage_match(melody_result: MelodyScoreResult) -> None:
    if (
        melody_result.alignment.normalized_distance
        > config.MISMATCH_NORMALIZED_DISTANCE_THRESHOLD
    ):
        raise PassageMismatchError(
            "We couldn't match your recording to the verses you selected. Check "
            "that you recited the right verse range and try again."
        )


# --- Result assembly -------------------------------------------------


# per-verse weights: elongation has no per-verse score, so the overall
# weights are renormalized across the three dimensions that do.
_PER_VERSE_WEIGHTS = {
    "melody": config.MELODY_WEIGHT,
    "pacing": config.PACING_WEIGHT,
    "tone": config.TONE_WEIGHT,
}


def _per_verse_scores(
    verses: list[VerseTimestamp],
    melody: MelodyScoreResult,
    tone_result: tone.ToneScoreResult,
    pacing_result: pacing.PacingScoreResult,
) -> list[dict]:
    per_dimension = {
        "melody": melody.per_verse_scores,
        "pacing": pacing_result.per_verse_scores,
        "tone": tone_result.per_verse_scores,
    }
    out: list[dict] = []
    for verse in verses:
        n = verse.verse_number
        weighted_sum = 0.0
        weight_total = 0.0
        for name, scores in per_dimension.items():
            if n in scores:
                weighted_sum += _PER_VERSE_WEIGHTS[name] * scores[n]
                weight_total += _PER_VERSE_WEIGHTS[name]
        if weight_total == 0.0:
            continue  # no aligned frames landed in this verse for any dimension
        out.append({"verse": n, "score": round(weighted_sum / weight_total)})
    return out


def _build_pitch_overlay(melody: MelodyScoreResult, user_vs, ref_vs) -> PitchOverlay:
    """Resample both contours onto a shared normalized time axis, following
    melody's DTW path so the two lines are time-aligned (PRD §5.4/§6).
    """
    path = melody.alignment.path
    ref_t = np.array([ref_vs.times[r] for _u, r in path])
    ref_semi = np.array([ref_vs.semitones[r] for _u, r in path])
    user_semi = np.array([user_vs.semitones[u] for u, _r in path])

    span = ref_t[-1] - ref_t[0]
    if span <= 0:
        normalized = np.linspace(0.0, 1.0, len(ref_t))
    else:
        normalized = (ref_t - ref_t[0]) / span

    axis = np.linspace(0.0, 1.0, PITCH_OVERLAY_POINTS)
    return PitchOverlay(
        time_axis=[round(float(x), 4) for x in axis],
        reference_semitones=[round(float(v), 3) for v in np.interp(axis, normalized, ref_semi)],
        user_semitones_aligned=[round(float(v), 3) for v in np.interp(axis, normalized, user_semi)],
    )


def _collect_tips(
    melody: MelodyScoreResult,
    pacing_result: pacing.PacingScoreResult,
    elongation_result: elongation.ElongationScoreResult,
) -> list[Tip]:
    tips: list[Tip] = []
    for region in melody.divergences:
        tips.append(
            Tip(
                verse=region.verse_number or 0,
                word_index=region.word_index,
                type="melody",
                text=_melody_tip_text(region),
            )
        )
    for tip in pacing_result.tips:
        tips.append(
            Tip(verse=tip.verse_number, word_index=None, type="pacing", text=_pacing_tip_text(tip))
        )
    for tip in elongation_result.tips:
        tips.append(
            Tip(
                verse=tip.verse_number,
                word_index=tip.word_index,
                type="elongation",
                text=_elongation_tip_text(tip),
            )
        )
    # Group by verse so the results page can list them under each verse.
    tips.sort(key=lambda t: (t.verse, t.word_index if t.word_index is not None else -1))
    return tips


def _where(verse: int, word_index: int | None) -> str:
    if verse and word_index is not None:
        return f"Verse {verse}, word {word_index}"
    if verse:
        return f"Verse {verse}"
    return "This passage"


def _melody_tip_text(region) -> str:
    direction = "higher" if region.direction == "too_high" else "lower"
    return (
        f"{_where(region.verse_number or 0, region.word_index)}: the reciter's pitch "
        f"moves differently here -- yours sits about {abs(region.mean_diff_semitones):.1f} "
        f"semitones {direction} for around {region.duration_s:.1f}s. Try following the "
        "reciter's rise and fall more closely."
    )


def _pacing_tip_text(tip) -> str:
    if tip.kind == "missing_pause":
        return (
            f"Verse {tip.verse_number}: the reciter pauses about {tip.ref_pause_s:.1f}s "
            f"here; you paused only about {tip.user_pause_s:.1f}s. Take a breath before "
            "moving on."
        )
    direction = "faster" if tip.kind == "too_fast" else "slower"
    return (
        f"Verse {tip.verse_number}: you recited this about {abs(tip.percent_off):.0f}% "
        f"{direction} than your own pace for the rest of the passage. Aim for an even tempo."
    )


def _elongation_tip_text(tip) -> str:
    if tip.kind == "shortfall":
        return (
            f"Verse {tip.verse_number}, word {tip.word_index}: the reciter holds this "
            f"word noticeably longer -- yours was about {abs(tip.percent_off):.0f}% shorter. "
            "Try extending the elongation."
        )
    return (
        f"Verse {tip.verse_number}, word {tip.word_index}: you held this word about "
        f"{abs(tip.percent_off):.0f}% longer than the reciter. Ease off the elongation a little."
    )
