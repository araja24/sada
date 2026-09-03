"""Unit tests for analysis/pipeline.py -- the full pipeline + §5.10 failure modes."""

from __future__ import annotations

import json

import numpy as np
import pytest

from analysis import config, pipeline
from analysis.align import AlignmentResult
from analysis.melody import MelodyScoreResult
from analysis.pitch import extract_pitch_contour
from analysis.tone import extract_mfcc


def _sine(freq_hz: float, duration_s: float, sr: int = 22050) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (0.8 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def _passage(freqs: list[float], seg_s: float, sr: int = 22050) -> np.ndarray:
    return np.concatenate([_sine(f, seg_s, sr) for f in freqs])


def _write_bundle(reference_dir, slug: str, y: np.ndarray, freqs: list[float], seg_s: float,
                  sr: int = 22050) -> None:
    reciter_dir = reference_dir / slug
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
    seg_ms = int(seg_s * 1000)
    verses = []
    for i, _f in enumerate(freqs):
        start = i * seg_ms
        # three equal "words" per verse
        words = [
            {"word_index": w + 1, "start_ms": start + w * seg_ms // 3,
             "end_ms": start + (w + 1) * seg_ms // 3}
            for w in range(3)
        ]
        verses.append({
            "verse_key": f"1:{i + 1}",
            "verse_number": i + 1,
            "timestamp_from_ms": start,
            "timestamp_to_ms": start + seg_ms,
            "words": words,
        })
    (reciter_dir / "timestamps.json").write_text(json.dumps({"verses": verses}), encoding="utf-8")


@pytest.fixture
def bundle_and_audio(tmp_path, wav_file_factory):
    sr = 22050
    freqs = [220.0, 247.0, 277.0]
    seg_s = 1.5
    y = _passage(freqs, seg_s, sr)
    reference_dir = tmp_path / "reference"
    _write_bundle(reference_dir, "test-reciter", y, freqs, seg_s, sr)
    bundle = pipeline.load_reference_bundle(reference_dir / "test-reciter")
    audio_path = wav_file_factory(y, sr=sr, name="user.wav")
    return bundle, audio_path


def test_identical_recitation_scores_very_high(bundle_and_audio):
    bundle, audio_path = bundle_and_audio
    result = pipeline.analyze(audio_path, bundle, 1, 3)

    assert result.overall_score >= 90
    assert result.label == "Very close"
    assert set(result.sub_scores) == {"melody", "pacing", "tone", "elongation"}
    assert [e["verse"] for e in result.per_verse] == [1, 2, 3]
    assert all(e["score"] >= 80 for e in result.per_verse)


def test_imitating_recitation_beats_a_flat_one(bundle_and_audio, tmp_path, wav_file_factory):
    # Sanity check (PRD §10 / issue #6): a take that follows the reference's
    # melodic movement scores higher than a flat monotone drone.
    bundle, imitating_path = bundle_and_audio
    flat = wav_file_factory(_sine(220.0, 4.5), name="flat.wav")

    imitating = pipeline.analyze(imitating_path, bundle, 1, 3)
    monotone = pipeline.analyze(flat, bundle, 1, 3)

    assert imitating.sub_scores["melody"] > monotone.sub_scores["melody"]
    assert imitating.overall_score > monotone.overall_score


def test_pitch_overlay_shape(bundle_and_audio):
    bundle, audio_path = bundle_and_audio
    overlay = pipeline.analyze(audio_path, bundle, 1, 3).pitch_overlay
    n = pipeline.PITCH_OVERLAY_POINTS
    assert len(overlay.time_axis) == n
    assert len(overlay.reference_semitones) == n
    assert len(overlay.user_semitones_aligned) == n
    assert overlay.time_axis[0] == 0.0 and overlay.time_axis[-1] == 1.0


def test_subset_verse_range(bundle_and_audio):
    bundle, audio_path = bundle_and_audio
    result = pipeline.analyze(audio_path, bundle, 2, 2)
    assert [e["verse"] for e in result.per_verse] == [2]


def test_empty_verse_range_is_valueerror(bundle_and_audio):
    bundle, audio_path = bundle_and_audio
    with pytest.raises(ValueError):
        pipeline.analyze(audio_path, bundle, 5, 6)


def test_silent_audio_raises_silent_error(bundle_and_audio, wav_file_factory):
    bundle, _ = bundle_and_audio
    silent = wav_file_factory(np.zeros(22050 * 3, dtype=np.float32), name="silent.wav")
    with pytest.raises(pipeline.SilentAudioError):
        pipeline.analyze(silent, bundle, 1, 3)


def test_too_short_audio_raises_duration_error(bundle_and_audio, wav_file_factory):
    bundle, _ = bundle_and_audio
    short = wav_file_factory(_sine(220.0, 1.0), name="short.wav")
    with pytest.raises(pipeline.AudioDurationError):
        pipeline.analyze(short, bundle, 1, 3)


def test_unreadable_audio_raises_unreadable_error(bundle_and_audio, tmp_path):
    bundle, _ = bundle_and_audio
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not really audio at all")
    with pytest.raises(pipeline.UnreadableAudioError):
        pipeline.analyze(junk, bundle, 1, 3)


def test_missing_bundle_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        pipeline.load_reference_bundle(tmp_path / "nope")


# --- failure-mode checks in isolation --------------------------------


def test_check_passage_match_flags_extreme_distance():
    bad = MelodyScoreResult(
        overall_score=1.0,
        per_verse_scores={},
        alignment=AlignmentResult(
            path=[(0, 0)],
            distance=999.0,
            normalized_distance=config.MISMATCH_NORMALIZED_DISTANCE_THRESHOLD + 1.0,
        ),
        divergences=[],
    )
    with pytest.raises(pipeline.PassageMismatchError):
        pipeline._check_passage_match(bad)


def test_check_voiced_ratio_flags_noisy_recording():
    class _Contour:
        voiced_flag = np.array([True] + [False] * 99)

    with pytest.raises(pipeline.NoisyAudioError):
        pipeline._check_voiced_ratio(_Contour())
