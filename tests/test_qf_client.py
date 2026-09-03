"""Unit tests for analysis.qf_client.

The acceptance criteria for this issue only require fixture-based tests for
audio_io/pitch/tone, but the OAuth2 + retry logic here is easy to get subtly
wrong, so it's covered too -- fully mocked, no network calls.
"""

from __future__ import annotations

import json

import pytest

from analysis import qf_client


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text or json.dumps(self._json_data)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._json_data


class _FakeSession:
    """Returns pre-programmed responses in call order; records every call."""

    def __init__(self, responses: list[_FakeResponse]):
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict]] = []

    def post(self, url: str, **kwargs) -> _FakeResponse:
        self.requests.append(("POST", url, kwargs))
        return self._responses.pop(0)

    def get(self, url: str, **kwargs) -> _FakeResponse:
        self.requests.append(("GET", url, kwargs))
        return self._responses.pop(0)


def _token_response(token: str = "tok-123") -> _FakeResponse:
    return _FakeResponse(json_data={"access_token": token, "expires_in": 3600})


def _client(responses: list[_FakeResponse]) -> tuple[qf_client.QuranFoundationClient, _FakeSession]:
    session = _FakeSession(responses)
    client = qf_client.QuranFoundationClient(
        client_id="cid", client_secret="secret", env="prelive", session=session
    )
    return client, session


def test_invalid_env_raises_value_error():
    with pytest.raises(ValueError):
        qf_client.QuranFoundationClient(client_id="a", client_secret="b", env="staging")


def test_from_env_raises_when_credentials_missing(monkeypatch):
    monkeypatch.delenv("QF_CLIENT_ID", raising=False)
    monkeypatch.delenv("QF_CLIENT_SECRET", raising=False)
    with pytest.raises(qf_client.QuranFoundationError):
        qf_client.QuranFoundationClient.from_env()


def test_get_access_token_uses_basic_auth_and_client_credentials_grant():
    client, session = _client([_token_response()])

    token = client._get_access_token()

    assert token == "tok-123"
    method, url, kwargs = session.requests[0]
    assert method == "POST"
    assert url.endswith("/oauth2/token")
    assert kwargs["auth"] == ("cid", "secret")
    assert kwargs["data"]["grant_type"] == "client_credentials"
    assert kwargs["data"]["scope"] == "content"


def test_get_access_token_is_cached_until_expiry():
    client, session = _client([_token_response()])

    client._get_access_token()
    client._get_access_token()

    assert len(session.requests) == 1


def test_request_refreshes_token_and_retries_once_on_401():
    responses = [
        _token_response("tok-1"),
        _FakeResponse(status_code=401, text="expired"),
        _token_response("tok-2"),
        _FakeResponse(json_data={"chapters": []}),
    ]
    client, session = _client(responses)

    result = client._request("GET", "/content/api/v4/chapters")

    assert result == {"chapters": []}
    get_calls = [r for r in session.requests if r[0] == "GET"]
    assert get_calls[0][2]["headers"]["x-auth-token"] == "tok-1"
    assert get_calls[1][2]["headers"]["x-auth-token"] == "tok-2"


def test_request_raises_on_non_recoverable_error():
    client, session = _client([_token_response(), _FakeResponse(status_code=500, text="boom")])

    with pytest.raises(qf_client.QuranFoundationError):
        client._request("GET", "/content/api/v4/chapters")


def test_list_chapter_reciters_returns_raw_list():
    reciters = [{"id": 7, "name": "Maher Al Muaiqly"}]
    client, session = _client([_token_response(), _FakeResponse(json_data={"reciters": reciters})])

    assert client.list_chapter_reciters() == reciters


def test_find_reciter_id_matches_case_insensitive_substring():
    reciters = [
        {"id": 7, "name": "Maher Al Muaiqly", "translated_name": {"name": "Maher Al Muaiqly"}}
    ]
    client, session = _client([_token_response(), _FakeResponse(json_data={"reciters": reciters})])

    assert client.find_reciter_id("maher al muaiqly") == 7


def test_find_reciter_id_raises_when_no_match():
    reciters = [
        {"id": 3, "name": "Abu Bakr al-Shatri", "translated_name": {"name": "Abu Bakr al-Shatri"}}
    ]
    client, session = _client([_token_response(), _FakeResponse(json_data={"reciters": reciters})])

    with pytest.raises(qf_client.QuranFoundationError):
        client.find_reciter_id("nonexistent reciter")


def test_find_reciter_id_raises_when_ambiguous():
    reciters = [
        {"id": 1, "name": "Abdul Rahman", "translated_name": {"name": "Abdul Rahman"}},
        {"id": 2, "name": "Abdul Rahman Al Sudais", "translated_name": {"name": "Abdul Rahman Al Sudais"}},
    ]
    client, session = _client([_token_response(), _FakeResponse(json_data={"reciters": reciters})])

    with pytest.raises(qf_client.QuranFoundationError):
        client.find_reciter_id("abdul rahman")


def test_get_chapter_audio_with_segments_parses_response():
    raw = {
        "audio_file": {
            "audio_url": "https://example.com/1.mp3",
            "format": "mp3",
            "timestamps": [
                {
                    "verse_key": "1:1",
                    "timestamp_from": 0,
                    "timestamp_to": 6493,
                    "segments": [[1, 0, 630], [2, 650, 1570]],
                }
            ],
        }
    }
    client, session = _client([_token_response(), _FakeResponse(json_data=raw)])

    chapter_audio = client.get_chapter_audio_with_segments(reciter_id=7, chapter_number=1)

    assert chapter_audio.audio_url == "https://example.com/1.mp3"
    assert len(chapter_audio.verses) == 1
    verse = chapter_audio.verses[0]
    assert verse.verse_number == 1
    assert verse.duration_ms == 6493
    assert len(verse.words) == 2
    assert verse.words[0].duration_ms == 630


def test_get_chapter_audio_with_segments_skips_malformed_segments():
    raw = {
        "audio_file": {
            "audio_url": "https://example.com/1.mp3",
            "format": "mp3",
            "timestamps": [
                {
                    "verse_key": "1:1",
                    "timestamp_from": 0,
                    "timestamp_to": 6493,
                    "segments": [[0], [1, 0, 630]],
                }
            ],
        }
    }
    client, session = _client([_token_response(), _FakeResponse(json_data=raw)])

    chapter_audio = client.get_chapter_audio_with_segments(reciter_id=7, chapter_number=1)

    assert len(chapter_audio.verses[0].words) == 1


def test_get_verse_texts_parses_text_and_drops_verse_number_glyph():
    raw = {
        "verses": [
            {
                "verse_key": "1:1",
                "verse_number": 1,
                "text_uthmani": "بِسْمِ ٱللَّهِ",
                "words": [
                    {"char_type_name": "word", "text_uthmani": "بِسْمِ"},
                    {"char_type_name": "word", "text_uthmani": "ٱللَّهِ"},
                    # the trailing verse-number glyph must not become a word
                    {"char_type_name": "end", "text_uthmani": "١"},
                ],
            }
        ]
    }
    client, session = _client([_token_response(), _FakeResponse(json_data=raw)])

    verses = client.get_verse_texts(chapter_number=1)

    assert len(verses) == 1
    assert verses[0].verse_number == 1
    assert verses[0].text_uthmani == "بِسْمِ ٱللَّهِ"
    assert verses[0].words == ["بِسْمِ", "ٱللَّهِ"]


def test_slugify_normalizes_names_for_filesystem_use():
    assert qf_client.slugify("Maher Al Muaiqly") == "maher_al_muaiqly"
    assert qf_client.slugify("Abu Bakr al-Shatri") == "abu_bakr_al_shatri"


class TestPublicMirrorClient:
    """The unauthenticated development source (see ADR-0001)."""

    def test_requests_go_to_mirror_without_auth_headers(self):
        session = _FakeSession([_FakeResponse(json_data={"chapters": []})])
        client = qf_client.PublicMirrorClient(session=session)

        client._request("/api/v4/chapters")

        method, url, kwargs = session.requests[0]
        assert url == "https://api.quran.com/api/v4/chapters"
        assert "headers" not in kwargs

    def test_uses_unprefixed_v4_path(self):
        raw = {
            "audio_file": {
                "audio_url": "https://example.com/1.mp3",
                "format": "mp3",
                "timestamps": [
                    {
                        "verse_key": "1:1",
                        "timestamp_from": 0,
                        "timestamp_to": 100,
                        "segments": [[1, 0, 100]],
                    }
                ],
            }
        }
        session = _FakeSession([_FakeResponse(json_data=raw)])
        client = qf_client.PublicMirrorClient(session=session)

        client.get_chapter_audio_with_segments(reciter_id=6, chapter_number=1)

        _method, url, _kwargs = session.requests[0]
        assert url == "https://api.quran.com/api/v4/chapter_recitations/6/1"

    def test_list_chapter_reciters_falls_back_to_recitations(self):
        session = _FakeSession(
            [
                _FakeResponse(status_code=503, text="Service Unavailable"),
                _FakeResponse(json_data={"recitations": [{"id": 6, "reciter_name": "Al-Husary"}]}),
            ]
        )
        client = qf_client.PublicMirrorClient(session=session)

        reciters = client.list_chapter_reciters()

        assert reciters == [{"id": 6, "reciter_name": "Al-Husary"}]

    def test_find_reciter_id_matches_reciter_name_key_from_fallback(self):
        session = _FakeSession(
            [
                _FakeResponse(status_code=503, text="Service Unavailable"),
                _FakeResponse(
                    json_data={"recitations": [{"id": 6, "reciter_name": "Mahmoud Al-Husary"}]}
                ),
            ]
        )
        client = qf_client.PublicMirrorClient(session=session)

        assert client.find_reciter_id("al-husary") == 6
