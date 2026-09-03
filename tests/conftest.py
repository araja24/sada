"""Shared pytest fixtures.

Test audio is synthesized in-memory (sine tones + silence) rather than
checked in as binary fixture files, so fixtures stay self-documenting and
there's nothing binary to review.
"""

from __future__ import annotations

import numpy as np
import pytest

SAMPLE_RATE = 22050


def sine_tone(
    freq_hz: float, duration_s: float, sr: int = SAMPLE_RATE, amplitude: float = 0.5
) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def silence(duration_s: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    return np.zeros(int(sr * duration_s), dtype=np.float32)


@pytest.fixture
def sample_rate() -> int:
    return SAMPLE_RATE


@pytest.fixture
def tone_with_silence_padding(sample_rate: int) -> np.ndarray:
    """0.2s silence + 1.0s of a 220 Hz tone + 0.3s silence."""
    return np.concatenate(
        [
            silence(0.2, sample_rate),
            sine_tone(220.0, 1.0, sample_rate),
            silence(0.3, sample_rate),
        ]
    )


@pytest.fixture
def wav_file_factory(tmp_path):
    """Factory fixture: write a numpy array to a temp WAV file, return its path."""
    import soundfile as sf

    def _make(y: np.ndarray, sr: int = SAMPLE_RATE, name: str = "audio.wav"):
        path = tmp_path / name
        sf.write(str(path), y, sr)
        return path

    return _make
