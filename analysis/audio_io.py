"""Audio loading and preprocessing.

PRD §5.1 (preprocessing step 1-2): every audio file that enters the analysis
pipeline -- reference recitations fetched by scripts/build_reference.py, and
later, user uploads -- goes through the same two steps so downstream code
(pitch/tone extraction, DTW alignment) never has to worry about sample rate,
channel count, or leading/trailing silence.

Pure functions only: no FastAPI imports, no globals, easy to unit test with
small synthetic fixtures.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

# PRD §3/§5.1: convert everything to mono WAV at this rate before analysis.
TARGET_SAMPLE_RATE = 22050

# librosa's own default for effects.trim; works well for recitation audio
# recorded without heavy background noise. Frames quieter than this many dB
# below the clip's peak are treated as silence.
DEFAULT_TRIM_TOP_DB = 30


def load_audio(path: str | Path, sr: int = TARGET_SAMPLE_RATE) -> tuple[np.ndarray, int]:
    """Load an audio file as mono float32 PCM, resampled to `sr`.

    librosa.load handles the format sniffing (wav/mp3/ogg/webm/m4a/...) via
    soundfile with an audioread+ffmpeg fallback, downmixes to mono, and
    resamples -- so every caller gets a uniform (samples,) float32 array
    regardless of what the source file looked like.
    """
    y, loaded_sr = librosa.load(str(path), sr=sr, mono=True)
    return y.astype(np.float32), loaded_sr


def trim_silence(
    y: np.ndarray, top_db: int = DEFAULT_TRIM_TOP_DB
) -> tuple[np.ndarray, tuple[int, int]]:
    """Trim leading/trailing silence from a mono waveform.

    Returns the trimmed audio plus the (start_sample, end_sample) index into
    the *input* array that was kept, so callers that need to keep other data
    (e.g. API word timestamps) in sync with the trimmed audio can shift it by
    the same amount.
    """
    y_trimmed, index = librosa.effects.trim(y, top_db=top_db)
    return y_trimmed, (int(index[0]), int(index[1]))


def load_and_preprocess(
    path: str | Path,
    sr: int = TARGET_SAMPLE_RATE,
    top_db: int = DEFAULT_TRIM_TOP_DB,
) -> tuple[np.ndarray, int, tuple[int, int]]:
    """Load + trim in one call -- the standard preprocessing step (PRD §5.1).

    Returns (trimmed_audio, sample_rate, trim_index) where trim_index is the
    (start_sample, end_sample) window kept from the freshly-loaded (untrimmed)
    audio, in case a caller needs to realign external timing data.
    """
    y, loaded_sr = load_audio(path, sr=sr)
    y_trimmed, trim_index = trim_silence(y, top_db=top_db)
    return y_trimmed, loaded_sr, trim_index


def save_wav(y: np.ndarray, sr: int, path: str | Path) -> None:
    """Write mono PCM audio to a 16-bit WAV file.

    Used to cache preprocessed reference audio under data/reference/ so
    later milestones can reload it without re-fetching/re-trimming.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), y, sr, subtype="PCM_16")
