"""Unit tests for the pure helper logic in scripts/build_reference.py.

The end-to-end orchestration (fetch -> preprocess -> extract -> cache)
requires a live/mocked network round-trip and is exercised manually by
running the script against the real API, per this issue's acceptance
criteria. What's unit-tested here is the trim/timestamp-realignment math and
serialization, since those are pure and easy to get subtly wrong.
"""

from __future__ import annotations

import pytest

from analysis.qf_client import (
    ChapterAudio,
    PublicMirrorClient,
    QuranFoundationClient,
    VerseText,
    VerseTimestamp,
    WordTimestamp,
)
from scripts import build_reference


def _chapter_audio() -> ChapterAudio:
    return ChapterAudio(
        audio_url="https://example.com/1.mp3",
        audio_format="mp3",
        verses=[
            VerseTimestamp(
                verse_key="1:1",
                timestamp_from_ms=1000,
                timestamp_to_ms=3000,
                words=[WordTimestamp(word_index=1, start_ms=1000, end_ms=1500)],
            )
        ],
    )


def test_adjust_timestamps_for_trim_shifts_left_by_trimmed_amount():
    chapter_audio = _chapter_audio()
    sr = 22050
    trim_start_sample = int(0.5 * sr)  # 500ms of leading silence trimmed off

    adjusted = build_reference.adjust_timestamps_for_trim(chapter_audio, trim_start_sample, sr)

    verse = adjusted.verses[0]
    assert verse.timestamp_from_ms == 500
    assert verse.timestamp_to_ms == 2500
    assert verse.words[0].start_ms == 500
    assert verse.words[0].end_ms == 1000


def test_adjust_timestamps_for_trim_clamps_at_zero():
    chapter_audio = _chapter_audio()
    sr = 22050
    trim_start_sample = int(2.0 * sr)  # more than the verse's own start offset

    adjusted = build_reference.adjust_timestamps_for_trim(chapter_audio, trim_start_sample, sr)

    verse = adjusted.verses[0]
    assert verse.timestamp_from_ms == 0
    assert verse.words[0].start_ms == 0


def test_adjust_timestamps_for_trim_preserves_verse_and_word_identity():
    chapter_audio = _chapter_audio()
    adjusted = build_reference.adjust_timestamps_for_trim(chapter_audio, 0, 22050)

    assert adjusted.verses[0].verse_key == "1:1"
    assert adjusted.verses[0].words[0].word_index == 1


def test_chapter_audio_to_dict_includes_computed_durations():
    chapter_audio = _chapter_audio()

    result = build_reference.chapter_audio_to_dict(chapter_audio)

    verse = result["verses"][0]
    assert verse["verse_number"] == 1
    assert verse["duration_ms"] == 2000
    assert verse["words"][0]["duration_ms"] == 500


def test_verse_texts_to_dict_serializes_arabic_text():
    verse_texts = [
        VerseText(verse_key="1:1", verse_number=1, text_uthmani="بِسْمِ ٱللَّهِ", words=["بِسْمِ", "ٱللَّهِ"])
    ]

    result = build_reference.verse_texts_to_dict(verse_texts)

    assert result["verses"][0]["text_uthmani"] == "بِسْمِ ٱللَّهِ"
    assert result["verses"][0]["words"] == ["بِسْمِ", "ٱللَّهِ"]


def test_make_client_returns_public_mirror_for_mirror_source():
    assert isinstance(build_reference.make_client("public-mirror"), PublicMirrorClient)


def test_make_client_returns_qf_client_for_qf_source(monkeypatch):
    monkeypatch.setenv("QF_CLIENT_ID", "cid")
    monkeypatch.setenv("QF_CLIENT_SECRET", "secret")

    assert isinstance(build_reference.make_client("qf"), QuranFoundationClient)


def test_make_client_rejects_unknown_source():
    with pytest.raises(ValueError):
        build_reference.make_client("somewhere-else")
