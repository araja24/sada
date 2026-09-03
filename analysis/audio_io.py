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

import os
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

    Tries libsndfile (via librosa) first -- it covers WAV/FLAC/OGG directly.
    Browser recordings are usually WebM/Opus, which libsndfile can't read,
    so anything it rejects is routed through ffmpeg via pydub (PRD §3/§5.10:
    "Convert browser uploads (webm/ogg) to mono WAV" / "convert via ffmpeg").
    """
    try:
        y, loaded_sr = librosa.load(str(path), sr=sr, mono=True)
        return y.astype(np.float32), loaded_sr
    except Exception as sndfile_error:  # noqa: BLE001 - any decode failure -> try ffmpeg
        try:
            return _load_via_ffmpeg(path, sr)
        except Exception as ffmpeg_error:
            raise AudioConversionError(
                f"Could not decode audio file {Path(path).name!r} "
                f"(libsndfile: {sndfile_error}; ffmpeg: {ffmpeg_error})."
            ) from ffmpeg_error


class AudioConversionError(RuntimeError):
    """Raised when neither libsndfile nor ffmpeg can decode an upload."""


def _ffmpeg_binary() -> str:
    """The ffmpeg executable to shell out to.

    Resolution order:
    1. SADA_FFMPEG / FFMPEG_BINARY -- an explicit path (local dev, or a host
       that puts ffmpeg somewhere non-standard);
    2. the static binary bundled with `imageio-ffmpeg`, if that package is
       installed -- this is what makes the app work on a plain Python host
       (e.g. Render's native runtime) with no system ffmpeg and no Docker;
    3. "ffmpeg" on PATH (Railway/Nixpacks, Homebrew, apt, ...).
    """
    explicit = os.environ.get("SADA_FFMPEG") or os.environ.get("FFMPEG_BINARY")
    if explicit:
        return explicit
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - package missing or no bundled binary
        return "ffmpeg"


def _load_via_ffmpeg(path: str | Path, sr: int) -> tuple[np.ndarray, int]:
    """Decode any ffmpeg-supported container (WebM/Opus, m4a, ...) to mono
    float32 at `sr` by piping a WAV stream out of ffmpeg.

    Shells out directly rather than via pydub so it needs only the ffmpeg
    binary -- no ffprobe, which isn't always installed alongside it.
    """
    import io
    import subprocess

    command = [
        _ffmpeg_binary(), "-nostdin", "-loglevel", "error",
        "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "wav", "pipe:1",
    ]
    proc = subprocess.run(command, capture_output=True, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise AudioConversionError(
            "ffmpeg could not decode the file: "
            + (proc.stderr.decode("utf-8", "replace").strip() or "no output produced")
        )
    y, loaded_sr = sf.read(io.BytesIO(proc.stdout), dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
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
