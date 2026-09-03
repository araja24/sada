"""Unit tests for analysis.audio_io -- pure preprocessing, no live API/network."""

from __future__ import annotations

import numpy as np
import pytest

from analysis import audio_io


def test_load_audio_resamples_to_target_rate(wav_file_factory, tone_with_silence_padding):
    path = wav_file_factory(tone_with_silence_padding, sr=44100)
    y, sr = audio_io.load_audio(path, sr=audio_io.TARGET_SAMPLE_RATE)
    assert sr == audio_io.TARGET_SAMPLE_RATE
    assert y.ndim == 1
    assert y.dtype == np.float32


def test_load_audio_downmixes_stereo_to_mono(wav_file_factory, sample_rate):
    left = np.zeros(sample_rate, dtype=np.float32)
    right = np.ones(sample_rate, dtype=np.float32)
    stereo = np.stack([left, right], axis=1)
    path = wav_file_factory(stereo, sr=sample_rate, name="stereo.wav")

    y, sr = audio_io.load_audio(path, sr=sample_rate)

    assert y.ndim == 1
    assert y.shape[0] == pytest.approx(sample_rate, abs=2)


def test_trim_silence_removes_leading_and_trailing_silence(tone_with_silence_padding, sample_rate):
    y_trimmed, (start, end) = audio_io.trim_silence(tone_with_silence_padding)

    assert 0 < start < end < len(tone_with_silence_padding)
    assert len(y_trimmed) < len(tone_with_silence_padding)
    # The kept region should be roughly the 1.0s tone, not the padding either side.
    assert 0.9 * sample_rate <= len(y_trimmed) <= 1.1 * sample_rate


def test_trim_silence_is_a_no_op_on_already_trimmed_audio(sample_rate):
    y = sine_tone_like(sample_rate)
    y_trimmed, (start, end) = audio_io.trim_silence(y)

    assert start == 0
    assert end == len(y)
    np.testing.assert_array_equal(y_trimmed, y)


def sine_tone_like(sr: int) -> np.ndarray:
    t = np.linspace(0, 1.0, sr, endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_load_and_preprocess_trims_and_resamples(wav_file_factory, tone_with_silence_padding):
    path = wav_file_factory(tone_with_silence_padding, sr=44100)

    y, sr, (start, _end) = audio_io.load_and_preprocess(path, sr=audio_io.TARGET_SAMPLE_RATE)

    assert sr == audio_io.TARGET_SAMPLE_RATE
    assert start > 0
    # Trimmed length should be much closer to the 1.0s tone than to the full 1.5s clip.
    assert len(y) < 1.2 * audio_io.TARGET_SAMPLE_RATE


def test_save_wav_round_trip(tmp_path, tone_with_silence_padding, sample_rate):
    out_path = tmp_path / "nested" / "out.wav"

    audio_io.save_wav(tone_with_silence_padding, sample_rate, out_path)

    assert out_path.exists()
    y_reloaded, sr = audio_io.load_audio(out_path, sr=sample_rate)
    assert sr == sample_rate
    assert len(y_reloaded) == pytest.approx(len(tone_with_silence_padding), rel=0.01)
