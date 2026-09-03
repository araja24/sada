"""Unit tests for scripts/compare.py.

The CLI is now a thin wrapper over `analysis.pipeline.analyze` (tested in
test_pipeline.py): these cover verse-range parsing, the printed report, and
that failure modes surface as a non-zero exit rather than a traceback.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from analysis.pitch import extract_pitch_contour
from analysis.tone import extract_mfcc
from scripts import compare


# --- parse_verse_range -----------------------------------------------


def test_parse_verse_range_single_number():
    assert compare.parse_verse_range("3") == (3, 3)


def test_parse_verse_range_span():
    assert compare.parse_verse_range("1-7") == (1, 7)


def test_parse_verse_range_rejects_reversed_range():
    with pytest.raises(ValueError):
        compare.parse_verse_range("5-2")


# --- print_report ---------------------------------------------------


def _result(**overrides):
    from analysis.pipeline import AttemptResult, PitchOverlay, Tip

    defaults = dict(
        overall_score=78,
        label="Getting close",
        sub_scores={"melody": 81, "pacing": 74, "tone": 65, "elongation": 60},
        per_verse=[{"verse": 1, "score": 84}, {"verse": 2, "score": 71}],
        pitch_overlay=PitchOverlay(time_axis=[0.0, 1.0], reference_semitones=[0.0, 0.0],
                                   user_semitones_aligned=[0.0, 0.0]),
        tips=[Tip(verse=1, word_index=4, type="elongation", text="Verse 1, word 4: hold it longer.")],
    )
    defaults.update(overrides)
    return AttemptResult(**defaults)


def test_print_report_shows_overall_label_subscores_and_tips(capsys):
    compare.print_report(_result())
    out = capsys.readouterr().out
    assert "78/100" in out
    assert "Getting close" in out
    assert "Verse 1: 84/100" in out
    assert "hold it longer" in out


def test_print_report_frames_tone_and_elongation_correctly(capsys):
    compare.print_report(_result())
    out = capsys.readouterr().out.lower()
    assert "tone similarity" in out
    assert "elongation timing" in out
    assert "correctness" not in out
    assert "tajweed" not in out


# --- run(): exit codes ----------------------------------------------


def _write_bundle(reference_dir, slug, y, sr=22050):
    reciter_dir = reference_dir / slug
    reciter_dir.mkdir(parents=True)
    contour = extract_pitch_contour(y, sr)
    np.savez(
        reciter_dir / "features.npz",
        sample_rate=sr,
        pitch_times=contour.times,
        f0_hz=contour.f0_hz,
        voiced_flag=contour.voiced_flag,
        semitones=contour.semitones,
        semitones_centered=contour.semitones_centered,
        median_semitone=contour.median_semitone,
        mfcc=extract_mfcc(y, sr),
    )
    duration_ms = int(len(y) / sr * 1000)
    (reciter_dir / "timestamps.json").write_text(
        json.dumps({"verses": [{
            "verse_key": "1:1", "verse_number": 1,
            "timestamp_from_ms": 0, "timestamp_to_ms": duration_ms,
            "words": [{"word_index": 1, "start_ms": 0, "end_ms": duration_ms}],
        }]}),
        encoding="utf-8",
    )


def _sine(freq_hz, duration_s, sr=22050):
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (0.8 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def test_run_returns_0_on_success(tmp_path, wav_file_factory, capsys):
    y = _sine(220.0, 2.5)
    reference_dir = tmp_path / "reference"
    _write_bundle(reference_dir, "r", y)
    audio = wav_file_factory(y, name="user.wav")
    assert compare.run(audio, "r", "1", reference_dir) == 0


def test_run_returns_1_on_missing_bundle(tmp_path, wav_file_factory):
    audio = wav_file_factory(_sine(220.0, 2.5), name="user.wav")
    assert compare.run(audio, "missing", "1-7", tmp_path / "reference") == 1


def test_run_returns_2_on_analysis_failure(tmp_path, wav_file_factory):
    y = _sine(220.0, 2.5)
    reference_dir = tmp_path / "reference"
    _write_bundle(reference_dir, "r", y)
    silent = wav_file_factory(np.zeros(22050 * 3, dtype=np.float32), name="silent.wav")
    assert compare.run(silent, "r", "1", reference_dir) == 2
