"""Unit tests for scripts/compare.py.

Pure-logic pieces (verse-range parsing/filtering, tip formatting, reference
loading) are tested directly; `compare()` itself is exercised end-to-end
against a small synthetic reference bundle + fixture audio, independent of
any live API call or scripts/build_reference.py run.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from analysis.pitch import extract_pitch_contour
from analysis.qf_client import VerseTimestamp, WordTimestamp
from analysis.tone import extract_mfcc
from scripts import compare


# --- parse_verse_range / filter_verse_range -------------------------------


def test_parse_verse_range_single_number():
    assert compare.parse_verse_range("3") == (3, 3)


def test_parse_verse_range_span():
    assert compare.parse_verse_range("1-7") == (1, 7)


def test_parse_verse_range_rejects_reversed_range():
    with pytest.raises(compare.ComparisonError):
        compare.parse_verse_range("5-2")


def test_filter_verse_range_keeps_only_verses_in_range():
    verses = [
        VerseTimestamp(verse_key=f"1:{n}", timestamp_from_ms=0, timestamp_to_ms=0, words=[])
        for n in range(1, 8)
    ]
    filtered = compare.filter_verse_range(verses, (2, 4))
    assert [v.verse_number for v in filtered] == [2, 3, 4]


# --- format_tip -------------------------------------------------------------


def test_format_tip_includes_verse_and_word_when_known():
    from analysis.melody import DivergenceRegion

    region = DivergenceRegion(
        start_s=1.0,
        end_s=1.6,
        duration_s=0.6,
        direction="too_high",
        mean_diff_semitones=4.2,
        verse_number=2,
        word_index=3,
    )
    tip = compare.format_tip(region)
    assert "verse 2" in tip
    assert "word 3" in tip
    assert "higher" in tip


def test_format_tip_falls_back_to_timestamp_when_verse_unknown():
    from analysis.melody import DivergenceRegion

    region = DivergenceRegion(
        start_s=2.5, end_s=3.1, duration_s=0.6, direction="too_low", mean_diff_semitones=-4.0
    )
    tip = compare.format_tip(region)
    assert "2.5s" in tip
    assert "lower" in tip


# --- load_reference_contour / load_reference_verses -------------------------


def test_load_reference_contour_missing_bundle_raises(tmp_path):
    with pytest.raises(compare.ComparisonError):
        compare.load_reference_contour(tmp_path / "nonexistent")


def test_load_reference_verses_missing_bundle_raises(tmp_path):
    with pytest.raises(compare.ComparisonError):
        compare.load_reference_verses(tmp_path / "nonexistent")


def test_load_reference_verses_round_trips_word_timestamps(tmp_path):
    reciter_dir = tmp_path / "reciter"
    reciter_dir.mkdir()
    (reciter_dir / "timestamps.json").write_text(
        json.dumps(
            {
                "verses": [
                    {
                        "verse_key": "1:1",
                        "verse_number": 1,
                        "timestamp_from_ms": 0,
                        "timestamp_to_ms": 1000,
                        "words": [{"word_index": 1, "start_ms": 0, "end_ms": 500}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    verses = compare.load_reference_verses(reciter_dir)
    assert len(verses) == 1
    assert verses[0].verse_number == 1
    assert verses[0].words[0].word_index == 1


# --- compare(): end-to-end against a synthetic reference bundle -------------


def _sine(freq_hz: float, duration_s: float, sr: int = 22050) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (0.8 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def _write_reference_bundle(reference_dir, reciter: str, y: np.ndarray, sr: int) -> None:
    reciter_dir = reference_dir / reciter
    reciter_dir.mkdir(parents=True)
    contour = extract_pitch_contour(y, sr)
    mfcc = extract_mfcc(y, sr)
    np.savez(
        reciter_dir / "features.npz",
        sample_rate=sr,
        pitch_times=contour.times,
        f0_hz=contour.f0_hz,
        voiced_flag=contour.voiced_flag,
        semitones=contour.semitones,
        semitones_centered=contour.semitones_centered,
        median_semitone=contour.median_semitone,
        mfcc=mfcc,
    )
    duration_ms = int(len(y) / sr * 1000)
    (reciter_dir / "timestamps.json").write_text(
        json.dumps(
            {
                "verses": [
                    {
                        "verse_key": "1:1",
                        "verse_number": 1,
                        "timestamp_from_ms": 0,
                        "timestamp_to_ms": duration_ms,
                        "words": [{"word_index": 1, "start_ms": 0, "end_ms": duration_ms}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_compare_identical_recitation_scores_highly(tmp_path, wav_file_factory):
    sr = 22050
    tone = _sine(220.0, 2.0, sr)

    reference_dir = tmp_path / "reference"
    _write_reference_bundle(reference_dir, "test-reciter", tone, sr)

    audio_path = wav_file_factory(tone, sr=sr, name="user.wav")

    result = compare.compare(audio_path, "test-reciter", "1", reference_dir)

    assert result.melody.overall_score > 90.0
    assert result.melody.per_verse_scores[1] > 90.0
    assert result.tone.overall_score > 90.0
    assert result.tone.per_verse_scores[1] > 90.0
    assert result.pacing.overall_score > 90.0
    assert result.pacing.global_tempo_ratio == pytest.approx(1.0, abs=0.1)


def test_compare_unknown_verse_range_raises(tmp_path, wav_file_factory):
    sr = 22050
    tone = _sine(220.0, 1.0, sr)
    reference_dir = tmp_path / "reference"
    _write_reference_bundle(reference_dir, "test-reciter", tone, sr)
    audio_path = wav_file_factory(tone, sr=sr, name="user.wav")

    with pytest.raises(compare.ComparisonError):
        compare.compare(audio_path, "test-reciter", "5-6", reference_dir)


def test_compare_missing_reciter_raises(tmp_path, wav_file_factory):
    sr = 22050
    audio_path = wav_file_factory(_sine(220.0, 1.0, sr), sr=sr, name="user.wav")
    with pytest.raises(compare.ComparisonError):
        compare.compare(audio_path, "nonexistent-reciter", "1-7", tmp_path / "reference")


# --- print_report: product-level framing requirement (PRD §5.6) ------------


def test_print_report_frames_tone_as_similarity_never_correctness(capsys):
    from analysis.melody import MelodyScoreResult
    from analysis.pacing import PacingScoreResult, PacingTip
    from analysis.tone import ToneScoreResult

    result = compare.CompareResult(
        melody=MelodyScoreResult(
            overall_score=80.0, per_verse_scores={1: 80.0}, alignment=None, divergences=[]
        ),
        tone=ToneScoreResult(overall_score=65.0, per_verse_scores={1: 65.0}),
        pacing=PacingScoreResult(
            overall_score=70.0,
            global_tempo_ratio=1.1,
            per_verse_scores={1: 70.0},
            tips=[PacingTip(verse_number=1, kind="too_fast", percent_off=-30.0)],
        ),
    )
    compare.print_report(result)
    output = capsys.readouterr().out.lower()

    assert "tone similarity" in output
    assert "correctness" not in output
    assert "wrong" not in output
