#!/usr/bin/env python3
"""CLI: compare a user's recitation to a cached reference reciter.

Milestone 2 (INITIAL_PROJECT_PLAN.md §5.4/§5.5/§5.6, §9): DTW-align the
user's pitch contour to a cached reference reciter's, then print the melody
score and the tone-similarity score (each overall + per-verse), plus
specific improvement tips. Reads the reference bundle that
`scripts/build_reference.py` cached under data/reference/<reciter_slug>/ --
run that first if it doesn't exist yet.

Usage:
    python scripts/compare.py --audio my_recitation.wav --reciter mishary
    python scripts/compare.py --audio my_recitation.wav --reciter mishary --verses 1-3
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis import audio_io, pacing, pitch, tone  # noqa: E402
from analysis.melody import DivergenceRegion, MelodyScoreResult, score_melody, voiced_series  # noqa: E402
from analysis.qf_client import AL_FATIHA_CHAPTER_NUMBER, VerseTimestamp, WordTimestamp  # noqa: E402

DEFAULT_REFERENCE_DIR = REPO_ROOT / "data" / "reference"


@dataclass
class CompareResult:
    melody: MelodyScoreResult
    tone: tone.ToneScoreResult
    pacing: pacing.PacingScoreResult


class ComparisonError(RuntimeError):
    """Raised for any user-facing failure (bad reciter, bad verse range, ...)."""


def load_reference_contour(reciter_dir: Path) -> pitch.PitchContour:
    """Load a cached reciter's pitch contour from features.npz (M1 output)."""
    features_path = reciter_dir / "features.npz"
    if not features_path.exists():
        raise ComparisonError(
            f"No cached reference found at {reciter_dir}. "
            "Run scripts/build_reference.py for this reciter first."
        )
    features = np.load(features_path)
    return pitch.PitchContour(
        times=features["pitch_times"],
        f0_hz=features["f0_hz"],
        voiced_flag=features["voiced_flag"],
        semitones=features["semitones"],
        semitones_centered=features["semitones_centered"],
        median_semitone=float(features["median_semitone"]),
    )


def load_reference_mfcc(reciter_dir: Path) -> np.ndarray:
    """Load a cached reciter's MFCC matrix from features.npz (M1 output)."""
    features_path = reciter_dir / "features.npz"
    if not features_path.exists():
        raise ComparisonError(
            f"No cached reference found at {reciter_dir}. "
            "Run scripts/build_reference.py for this reciter first."
        )
    return np.load(features_path)["mfcc"]


def load_reference_verses(
    reciter_dir: Path, chapter_number: int = AL_FATIHA_CHAPTER_NUMBER
) -> list[VerseTimestamp]:
    """Load a cached reciter's verse/word timestamps from timestamps.json (M1 output)."""
    timestamps_path = reciter_dir / "timestamps.json"
    if not timestamps_path.exists():
        raise ComparisonError(
            f"No cached reference found at {reciter_dir}. "
            "Run scripts/build_reference.py for this reciter first."
        )
    data = json.loads(timestamps_path.read_text(encoding="utf-8"))
    return [
        VerseTimestamp(
            verse_key=v.get("verse_key", f"{chapter_number}:{v['verse_number']}"),
            timestamp_from_ms=v["timestamp_from_ms"],
            timestamp_to_ms=v["timestamp_to_ms"],
            words=[
                WordTimestamp(word_index=w["word_index"], start_ms=w["start_ms"], end_ms=w["end_ms"])
                for w in v["words"]
            ],
        )
        for v in data["verses"]
    ]


def parse_verse_range(spec: str) -> tuple[int, int]:
    """Parse '1-7' or '3' into an inclusive (lo, hi) verse-number range."""
    if "-" in spec:
        lo_str, hi_str = spec.split("-", 1)
        lo, hi = int(lo_str), int(hi_str)
    else:
        lo = hi = int(spec)
    if lo > hi:
        raise ComparisonError(f"Invalid verse range {spec!r}: start is after end.")
    return lo, hi


def filter_verse_range(
    verses: list[VerseTimestamp], verse_range: tuple[int, int]
) -> list[VerseTimestamp]:
    lo, hi = verse_range
    return [v for v in verses if lo <= v.verse_number <= hi]


def format_tip(region: DivergenceRegion) -> str:
    direction_word = "higher" if region.direction == "too_high" else "lower"
    if region.verse_number is not None:
        where = f"verse {region.verse_number}"
        if region.word_index is not None:
            where += f", word {region.word_index}"
    else:
        where = f"~{region.start_s:.1f}s into the reference"
    return (
        f"Your pitch runs {direction_word} than the reference around {where} "
        f"(~{region.duration_s:.1f}s, avg {abs(region.mean_diff_semitones):.1f} semitones {direction_word})."
    )


def format_pacing_tip(tip: pacing.PacingTip) -> str:
    if tip.kind == "missing_pause":
        return (
            f"Verse {tip.verse_number}: the reciter pauses ~{tip.ref_pause_s:.1f}s here; "
            f"you paused only ~{tip.user_pause_s:.1f}s. Take a breath before continuing."
        )
    direction_word = "faster" if tip.kind == "too_fast" else "slower"
    return (
        f"Verse {tip.verse_number}: you recited this ~{abs(tip.percent_off):.0f}% {direction_word} "
        f"than your own average pace for this passage."
    )


def print_report(result: CompareResult) -> None:
    melody, tone_result, pacing_result = result.melody, result.tone, result.pacing

    print()
    print(f"Melody score: {melody.overall_score:.0f}/100")
    if melody.per_verse_scores:
        print("Per-verse melody scores:")
        for verse_number in sorted(melody.per_verse_scores):
            print(f"  Verse {verse_number}: {melody.per_verse_scores[verse_number]:.0f}/100")

    # Framing requirement (PRD §5.6): "tone similarity," never "correctness"
    # -- different voices legitimately differ.
    print()
    print(f"Tone similarity score: {tone_result.overall_score:.0f}/100")
    print("(How closely your vocal tone resembles the reciter's -- every voice is different.)")
    if tone_result.per_verse_scores:
        print("Per-verse tone similarity scores:")
        for verse_number in sorted(tone_result.per_verse_scores):
            print(f"  Verse {verse_number}: {tone_result.per_verse_scores[verse_number]:.0f}/100")

    print()
    print(f"Pacing score: {pacing_result.overall_score:.0f}/100")
    print(f"(Overall tempo: {pacing_result.global_tempo_ratio:.2f}x the reference's pace.)")
    if pacing_result.per_verse_scores:
        print("Per-verse pacing scores:")
        for verse_number in sorted(pacing_result.per_verse_scores):
            print(f"  Verse {verse_number}: {pacing_result.per_verse_scores[verse_number]:.0f}/100")

    print()
    tips = list(melody.divergences) + list(pacing_result.tips)
    if tips:
        print("Tips:")
        for region in melody.divergences:
            print(f"  - {format_tip(region)}")
        for tip in pacing_result.tips:
            print(f"  - {format_pacing_tip(tip)}")
    else:
        print("No significant issues detected.")


def compare(
    audio_path: Path,
    reciter: str,
    verse_range_spec: str = "1-7",
    reference_dir: Path = DEFAULT_REFERENCE_DIR,
) -> CompareResult:
    reciter_dir = reference_dir / reciter

    print(f"Loading reference bundle for {reciter!r}...")
    ref_contour = load_reference_contour(reciter_dir)
    ref_mfcc = load_reference_mfcc(reciter_dir)
    ref_verses = load_reference_verses(reciter_dir)

    verse_range = parse_verse_range(verse_range_spec)
    verses_in_range = filter_verse_range(ref_verses, verse_range)
    if not verses_in_range:
        raise ComparisonError(
            f"No verses in range {verse_range_spec!r} for reciter {reciter!r} "
            f"(available: 1-{len(ref_verses)})."
        )

    print(f"Loading and preprocessing {audio_path}...")
    y, sr, _trim = audio_io.load_and_preprocess(audio_path)

    print("Extracting pitch contour and MFCCs...")
    user_contour = pitch.extract_pitch_contour(y, sr)
    user_mfcc = tone.extract_mfcc(y, sr)

    print("Aligning and scoring melody...")
    melody_result = score_melody(user_contour, ref_contour, ref_verses=verses_in_range)

    print("Scoring tone similarity...")
    # Reuse melody's alignment path (PRD §5.4/§5.6), not a fresh DTW pass --
    # voiced_series() itself is cheap (array masking), only the DTW alignment
    # it fed into is expensive, and that's already computed above.
    tone_result = tone.score_tone(
        user_mfcc,
        ref_mfcc,
        melody_result.alignment,
        voiced_series(user_contour),
        voiced_series(ref_contour),
        ref_verses=verses_in_range,
    )

    print("Scoring pacing...")
    pacing_result = pacing.score_pacing(
        melody_result.alignment,
        voiced_series(user_contour),
        voiced_series(ref_contour),
        ref_verses=verses_in_range,
    )

    return CompareResult(melody=melody_result, tone=tone_result, pacing=pacing_result)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audio", required=True, type=Path, help="Path to the user's recorded audio file."
    )
    parser.add_argument(
        "--reciter", required=True, help="Reference reciter's slug under data/reference/."
    )
    parser.add_argument(
        "--verses",
        default="1-7",
        help="Verse range to compare, e.g. '1-7' or '3' (default: 1-7, all of Al-Fatiha).",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=DEFAULT_REFERENCE_DIR,
        help="Directory reference bundles are cached under (default: data/reference/).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = compare(args.audio, args.reciter, args.verses, args.reference_dir)
    except (ComparisonError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
