#!/usr/bin/env python3
"""Build the reference feature cache for one reciter's Al-Fatiha recitation.

This is Milestone 1 from INITIAL_PROJECT_PLAN.md (§5.2, §9): fetch a
reciter's Al-Fatiha audio + word-level timestamps from the Quran Foundation
API, preprocess the audio, extract pitch/tone features, and cache
everything under data/reference/ so every later milestone can reuse it
without re-hitting the live API.

Run manually by the developer (not at request time):

    python scripts/build_reference.py
    python scripts/build_reference.py --reciter-name "Maher Al Muaiqly" --plot-verse 1

Requires QF_CLIENT_ID / QF_CLIENT_SECRET in your environment or a .env file
in the repo root (see .env.example) -- these are free developer credentials
from https://api-docs.quran.foundation/, obtained by the developer, never
committed.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis import audio_io, pitch, tone  # noqa: E402
from analysis.qf_client import (  # noqa: E402
    AL_FATIHA_CHAPTER_NUMBER,
    ChapterAudio,
    PublicMirrorClient,
    QuranFoundationClient,
    VerseText,
    slugify,
)

DEFAULT_RECITER_NAME = "Maher Al Muaiqly"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "reference"


def _ms_to_samples(ms: float, sr: int) -> int:
    return int(round(ms / 1000.0 * sr))


def adjust_timestamps_for_trim(
    chapter_audio: ChapterAudio, trim_start_sample: int, sr: int
) -> ChapterAudio:
    """Shift API timestamps to stay in sync with silence-trimmed audio.

    `audio_io.trim_silence` drops leading silence, so sample 0 of the cached
    WAV no longer corresponds to timestamp 0 ms from the API. We shift every
    word/verse timestamp left by the trimmed amount and clamp at zero so the
    cached timestamps always index correctly into the cached audio.
    """
    shift_ms = trim_start_sample / sr * 1000.0
    adjusted_verses = []
    for verse in chapter_audio.verses:
        adjusted_words = [
            type(w)(
                word_index=w.word_index,
                start_ms=max(0, round(w.start_ms - shift_ms)),
                end_ms=max(0, round(w.end_ms - shift_ms)),
            )
            for w in verse.words
        ]
        adjusted_verses.append(
            type(verse)(
                verse_key=verse.verse_key,
                timestamp_from_ms=max(0, round(verse.timestamp_from_ms - shift_ms)),
                timestamp_to_ms=max(0, round(verse.timestamp_to_ms - shift_ms)),
                words=adjusted_words,
            )
        )
    return ChapterAudio(
        audio_url=chapter_audio.audio_url,
        audio_format=chapter_audio.audio_format,
        verses=adjusted_verses,
    )


def verse_texts_to_dict(verse_texts: list[VerseText]) -> dict:
    """Serialize verse/word Arabic text for the API's passage endpoint (§6)."""
    return {
        "verses": [
            {
                "verse_key": verse.verse_key,
                "verse_number": verse.verse_number,
                "text_uthmani": verse.text_uthmani,
                "words": verse.words,
            }
            for verse in verse_texts
        ]
    }


def chapter_audio_to_dict(chapter_audio: ChapterAudio) -> dict:
    """Serialize a ChapterAudio (with computed durations) to a JSON-able dict."""
    return {
        "audio_url": chapter_audio.audio_url,
        "audio_format": chapter_audio.audio_format,
        "verses": [
            {
                "verse_key": verse.verse_key,
                "verse_number": verse.verse_number,
                "timestamp_from_ms": verse.timestamp_from_ms,
                "timestamp_to_ms": verse.timestamp_to_ms,
                "duration_ms": verse.duration_ms,
                "words": [
                    {
                        "word_index": w.word_index,
                        "start_ms": w.start_ms,
                        "end_ms": w.end_ms,
                        "duration_ms": w.duration_ms,
                    }
                    for w in verse.words
                ],
            }
            for verse in chapter_audio.verses
        ],
    }


def make_client(source: str):
    """Build the content API client for the requested source.

    `qf` is the PRD's fixed production source and needs credentials;
    `public-mirror` is the unauthenticated development fallback (see
    docs/adr/0001-reference-data-source.md).
    """
    if source == "qf":
        return QuranFoundationClient.from_env()
    if source == "public-mirror":
        return PublicMirrorClient()
    raise ValueError(f"Unknown source {source!r}; expected 'qf' or 'public-mirror'.")


def build_reference(
    reciter_name: str,
    output_dir: Path,
    chapter_number: int = AL_FATIHA_CHAPTER_NUMBER,
    plot_verse: int | None = None,
    source: str = "qf",
    reciter_id: int | None = None,
) -> Path:
    """Fetch, preprocess, extract features, and cache one reciter's chapter.

    Returns the reciter's output directory (data/reference/<slug>/).
    """
    client = make_client(source)

    if reciter_id is None:
        print(f"Looking up chapter-reciter id for {reciter_name!r}...")
        reciter_id = client.find_reciter_id(reciter_name)
    print(f"  -> reciter_id={reciter_id}")

    print(f"Fetching chapter {chapter_number} audio + word timestamps...")
    chapter_audio = client.get_chapter_audio_with_segments(reciter_id, chapter_number)
    if not chapter_audio.verses:
        raise RuntimeError(
            f"Reciter id {reciter_id} returned no word-level timestamps for chapter "
            f"{chapter_number}. Pick a reciter that has segment data."
        )

    print(f"Fetching chapter {chapter_number} verse + word text...")
    verse_texts = client.get_verse_texts(chapter_number)

    reciter_slug = slugify(reciter_name)
    reciter_dir = output_dir / reciter_slug
    reciter_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading audio from {chapter_audio.audio_url}...")
    with tempfile.NamedTemporaryFile(suffix=f".{chapter_audio.audio_format}") as tmp:
        client.download_audio(chapter_audio.audio_url, tmp.name)

        print("Preprocessing (mono, 22050 Hz, trim silence)...")
        y_trimmed, sr, (trim_start, _trim_end) = audio_io.load_and_preprocess(tmp.name)

    chapter_audio = adjust_timestamps_for_trim(chapter_audio, trim_start, sr)

    print("Extracting pitch contour (pyin)...")
    pitch_contour = pitch.extract_pitch_contour(y_trimmed, sr)

    print("Extracting MFCCs...")
    mfcc = tone.extract_mfcc(y_trimmed, sr)

    audio_path = reciter_dir / "audio.wav"
    audio_io.save_wav(y_trimmed, sr, audio_path)
    print(f"Saved preprocessed audio -> {audio_path}")

    features_path = reciter_dir / "features.npz"
    np.savez(
        features_path,
        sample_rate=sr,
        pitch_times=pitch_contour.times,
        f0_hz=pitch_contour.f0_hz,
        voiced_flag=pitch_contour.voiced_flag,
        semitones=pitch_contour.semitones,
        semitones_centered=pitch_contour.semitones_centered,
        median_semitone=pitch_contour.median_semitone,
        mfcc=mfcc,
    )
    print(f"Saved pitch/MFCC features -> {features_path}")

    timestamps_path = reciter_dir / "timestamps.json"
    timestamps_path.write_text(
        json.dumps(
            {
                "reciter_name": reciter_name,
                "reciter_id": reciter_id,
                "source": source,
                **chapter_audio_to_dict(chapter_audio),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved word/verse timestamps -> {timestamps_path}")

    passage_path = reciter_dir / "passage.json"
    passage_path.write_text(
        json.dumps(verse_texts_to_dict(verse_texts), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved verse/word Arabic text -> {passage_path}")

    if plot_verse is not None:
        plot_path = plot_reference_pitch(chapter_audio, pitch_contour, plot_verse, reciter_dir)
        print(f"Saved verification plot for verse {plot_verse} -> {plot_path}")

    return reciter_dir


def plot_reference_pitch(
    chapter_audio: ChapterAudio,
    pitch_contour: pitch.PitchContour,
    verse_number: int,
    reciter_dir: Path,
) -> Path:
    """Plot the (trim-adjusted) pitch contour for one verse, as a sanity check.

    This satisfies the acceptance criterion "verified by plotting the
    reference pitch contour for at least one verse" -- a human can eyeball
    the PNG and confirm the extracted melody looks like plausible recitation
    (not flat/silent/garbage).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    verse = next((v for v in chapter_audio.verses if v.verse_number == verse_number), None)
    if verse is None:
        raise ValueError(f"No verse {verse_number} in fetched chapter data.")

    start_s, end_s = verse.timestamp_from_ms / 1000.0, verse.timestamp_to_ms / 1000.0
    mask = (pitch_contour.times >= start_s) & (pitch_contour.times <= end_s)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(pitch_contour.times[mask], pitch_contour.semitones_centered[mask])
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Semitones (median-centered)")
    ax.set_title(f"Reference pitch contour — verse {verse_number} ({verse.verse_key})")
    ax.grid(True, alpha=0.3)

    plots_dir = reciter_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plots_dir / f"verse_{verse_number}_pitch.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return plot_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reciter-name",
        default=DEFAULT_RECITER_NAME,
        help=f"Chapter-reciter name to search for (default: {DEFAULT_RECITER_NAME!r}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to cache reference features under (default: data/reference/).",
    )
    parser.add_argument(
        "--reciter-id",
        type=int,
        default=None,
        help="Skip the name lookup and use this chapter-reciter id directly.",
    )
    parser.add_argument(
        "--source",
        choices=["qf", "public-mirror"],
        default="qf",
        help=(
            "Where to fetch reference data from. 'qf' (default) is the Quran Foundation "
            "API and needs QF_CLIENT_ID/QF_CLIENT_SECRET; 'public-mirror' is the same v4 "
            "API served unauthenticated at api.quran.com, for local development before "
            "credentials are issued."
        ),
    )
    parser.add_argument(
        "--plot-verse",
        type=int,
        default=None,
        help="If set, save a pitch-contour PNG for this verse number (1-7) as a sanity check.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(REPO_ROOT / ".env")
    try:
        build_reference(
            args.reciter_name,
            args.output_dir,
            plot_verse=args.plot_verse,
            source=args.source,
            reciter_id=args.reciter_id,
        )
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
