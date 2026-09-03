#!/usr/bin/env python3
"""CLI: compare a user's recitation to a cached reference reciter.

Milestone 2 (INITIAL_PROJECT_PLAN.md §5, §9): run the full analysis
pipeline (`analysis.pipeline.analyze`) on a recorded recitation and print
the overall score + label, all four sub-scores, per-verse scores, and the
combined tips list. Reads the reference bundle that
`scripts/build_reference.py` cached under data/reference/<reciter_slug>/ --
run that first if it doesn't exist yet.

Usage:
    python scripts/compare.py --audio my_recitation.wav --reciter mishary
    python scripts/compare.py --audio my_recitation.wav --reciter mishary --verses 1-3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis import pipeline  # noqa: E402

DEFAULT_REFERENCE_DIR = REPO_ROOT / "data" / "reference"


def parse_verse_range(spec: str) -> tuple[int, int]:
    """Parse '1-7' or '3' into an inclusive (lo, hi) verse-number range."""
    if "-" in spec:
        lo_str, hi_str = spec.split("-", 1)
        lo, hi = int(lo_str), int(hi_str)
    else:
        lo = hi = int(spec)
    if lo > hi:
        raise ValueError(f"Invalid verse range {spec!r}: start is after end.")
    return lo, hi


def print_report(result: pipeline.AttemptResult) -> None:
    print()
    print(f"Overall score: {result.overall_score}/100  --  {result.label}")
    print()
    print("Sub-scores:")
    # Framing (PRD §5.6/§5.8): "tone similarity" and "elongation timing",
    # never "correctness" or "tajweed".
    labels = {
        "melody": "Melody",
        "pacing": "Pacing",
        "tone": "Tone similarity",
        "elongation": "Elongation timing",
    }
    for key, label in labels.items():
        print(f"  {label}: {result.sub_scores[key]}/100")

    if result.per_verse:
        print()
        print("Per-verse scores:")
        for entry in result.per_verse:
            print(f"  Verse {entry['verse']}: {entry['score']}/100")

    print()
    if result.tips:
        print("Tips:")
        for tip in result.tips:
            print(f"  - {tip.text}")
    else:
        print("No specific issues stood out -- nicely done.")
    print()


def run(audio_path: Path, reciter: str, verses_spec: str, reference_dir: Path) -> int:
    try:
        start_verse, end_verse = parse_verse_range(verses_spec)
        bundle = pipeline.load_reference_bundle(reference_dir / reciter)
        result = pipeline.analyze(audio_path, bundle, start_verse, end_verse)
    except pipeline.AnalysisError as exc:
        print(f"Couldn't score this recording: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print_report(result)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, type=Path, help="Path to the recorded audio.")
    parser.add_argument(
        "--reciter", required=True, help="Reference reciter's slug under data/reference/."
    )
    parser.add_argument(
        "--verses", default="1-7", help="Verse range, e.g. '1-7' or '3' (default: 1-7)."
    )
    parser.add_argument(
        "--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR,
        help="Directory reference bundles are cached under (default: data/reference/).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.audio, args.reciter, args.verses, args.reference_dir)


if __name__ == "__main__":
    raise SystemExit(main())
