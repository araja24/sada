"""Quran Foundation Content API client (OAuth2 client-credentials flow).

Used by scripts/build_reference.py to fetch a reciter's chapter audio and
word-level timestamps. Kept separate from FastAPI/web concerns (PRD §3: "The
audio analysis pipeline... [lives] in its own module, independent of
FastAPI") and separate from the DSP modules (audio_io/pitch/tone) because it
does network I/O rather than pure computation -- it has its own test
strategy (mocked HTTP), not fixture-audio unit tests.

Reference: https://api-docs.quran.foundation/docs/quickstart/
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import requests

# Al-Fatiha is chapter 1 in the Quran Foundation content API.
AL_FATIHA_CHAPTER_NUMBER = 1

_AUTH_BASE_URLS = {
    "prelive": "https://prelive-oauth2.quran.foundation",
    "production": "https://oauth2.quran.foundation",
}
_API_BASE_URLS = {
    "prelive": "https://apis-prelive.quran.foundation",
    "production": "https://apis.quran.foundation",
}

# Re-request the token this many seconds before it actually expires, to
# avoid racing a request against expiry.
_TOKEN_EXPIRY_SAFETY_MARGIN_S = 60


class QuranFoundationError(RuntimeError):
    """Raised for any non-recoverable Quran Foundation API failure."""


@dataclass
class WordTimestamp:
    """One word's timing within a verse, per PRD §5.2: [word_index, start_ms, end_ms]."""

    word_index: int
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass
class VerseTimestamp:
    """Timing for one verse, plus its word-level breakdown."""

    verse_key: str  # e.g. "1:1"
    timestamp_from_ms: int
    timestamp_to_ms: int
    words: list[WordTimestamp] = field(default_factory=list)

    @property
    def verse_number(self) -> int:
        return int(self.verse_key.split(":")[1])

    @property
    def duration_ms(self) -> int:
        return self.timestamp_to_ms - self.timestamp_from_ms


@dataclass
class ChapterAudio:
    """A reciter's audio file for one chapter, with per-verse/per-word timing."""

    audio_url: str
    audio_format: str
    verses: list[VerseTimestamp]


def slugify(name: str) -> str:
    """Turn a reciter's display name into a filesystem-safe slug."""
    keep = (c.lower() if c.isalnum() else "_" for c in name)
    slug = "".join(keep)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def parse_chapter_audio_response(data: dict) -> ChapterAudio:
    """Parse the raw `/chapter_recitations/{reciter}/{chapter}?segments=true` body."""
    audio_file = data["audio_file"]
    verses: list[VerseTimestamp] = []
    for entry in audio_file.get("timestamps", []):
        words = []
        for segment in entry.get("segments", []):
            # The API's own docs show a malformed `[0]` placeholder in one
            # example schema; be defensive and skip anything that isn't a
            # full [word_index, start_ms, end_ms] triple.
            if len(segment) < 3:
                continue
            word_index, start_ms, end_ms = segment[0], segment[1], segment[2]
            words.append(WordTimestamp(word_index=word_index, start_ms=start_ms, end_ms=end_ms))
        verses.append(
            VerseTimestamp(
                verse_key=entry["verse_key"],
                timestamp_from_ms=entry["timestamp_from"],
                timestamp_to_ms=entry["timestamp_to"],
                words=words,
            )
        )
    return ChapterAudio(
        audio_url=audio_file["audio_url"],
        audio_format=audio_file.get("format", "mp3"),
        verses=verses,
    )


class QuranFoundationClient:
    """Minimal client for the parts of the Content API build_reference.py needs.

    Handles the OAuth2 client-credentials token dance (fetch, cache,
    refresh-once-on-401) so callers just call methods like
    `get_chapter_audio_with_segments`.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        env: str = "prelive",
        timeout_s: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        if env not in _AUTH_BASE_URLS:
            raise ValueError(f"Invalid QF_ENV {env!r}; expected 'prelive' or 'production'.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.env = env
        self.timeout_s = timeout_s
        self._session = session or requests.Session()
        self._auth_base_url = _AUTH_BASE_URLS[env]
        self._api_base_url = _API_BASE_URLS[env]
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    @classmethod
    def from_env(cls) -> "QuranFoundationClient":
        """Build a client from QF_CLIENT_ID / QF_CLIENT_SECRET / QF_ENV env vars.

        Does not itself load a .env file -- call `dotenv.load_dotenv()` (or
        equivalent) before this if you want .env support, matching how the
        rest of the project treats environment configuration.
        """
        client_id = os.environ.get("QF_CLIENT_ID")
        client_secret = os.environ.get("QF_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise QuranFoundationError(
                "QF_CLIENT_ID and QF_CLIENT_SECRET must be set (see .env.example) "
                "to talk to the live Quran Foundation API."
            )
        env = os.environ.get("QF_ENV", "prelive")
        return cls(client_id=client_id, client_secret=client_secret, env=env)

    def _fetch_access_token(self) -> None:
        response = self._session.post(
            f"{self._auth_base_url}/oauth2/token",
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": "content"},
            timeout=self.timeout_s,
        )
        if not response.ok:
            raise QuranFoundationError(
                f"Failed to obtain Quran Foundation access token: "
                f"{response.status_code} {response.text}"
            )
        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = payload.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in - _TOKEN_EXPIRY_SAFETY_MARGIN_S

    def _get_access_token(self, force_refresh: bool = False) -> str:
        if force_refresh or self._access_token is None or time.monotonic() >= self._token_expires_at:
            self._fetch_access_token()
        assert self._access_token is not None
        return self._access_token

    def _request(self, method: str, path: str, params: dict | None = None) -> dict:
        """Make one authenticated Content API request, retrying once on 401.

        Follows the Quran Foundation quickstart's documented status-code
        handling: 401 -> refresh token and retry once; 403/429/5xx -> raise
        (this script is run manually, so surfacing the failure to the
        developer is preferable to silent retries/backoff loops).
        """
        url = f"{self._api_base_url}{path}"
        for attempt in range(2):
            token = self._get_access_token(force_refresh=(attempt == 1))
            response = self._session.get(
                url,
                params=params,
                headers={"x-auth-token": token, "x-client-id": self.client_id},
                timeout=self.timeout_s,
            )
            if response.status_code == 401 and attempt == 0:
                continue
            if not response.ok:
                raise QuranFoundationError(
                    f"Quran Foundation API request to {path} failed: "
                    f"{response.status_code} {response.text}"
                )
            return response.json()
        raise QuranFoundationError(f"Quran Foundation API request to {path} failed after retry.")

    def list_chapter_reciters(self) -> list[dict]:
        """GET /resources/chapter_reciters -> raw reciter dicts."""
        data = self._request("GET", "/content/api/v4/resources/chapter_reciters")
        return data["reciters"]

    def find_reciter_id(self, name_query: str) -> int:
        """Find a chapter-reciter id by (case-insensitive, substring) name match.

        Raises QuranFoundationError if there's no match or more than one --
        the developer should tighten `name_query` rather than have this
        script silently guess.
        """
        reciters = self.list_chapter_reciters()
        query = name_query.strip().lower()
        matches = [
            r
            for r in reciters
            if query in r.get("name", "").lower()
            or query in r.get("translated_name", {}).get("name", "").lower()
        ]
        if not matches:
            names = ", ".join(r.get("name", "?") for r in reciters)
            raise QuranFoundationError(
                f"No chapter reciter matched {name_query!r}. Available reciters: {names}"
            )
        if len(matches) > 1:
            names = ", ".join(f"{r['name']} (id={r['id']})" for r in matches)
            raise QuranFoundationError(
                f"Ambiguous reciter name {name_query!r}; matches: {names}. "
                "Pass a more specific name."
            )
        return int(matches[0]["id"])

    def get_chapter_audio_with_segments(
        self, reciter_id: int, chapter_number: int = AL_FATIHA_CHAPTER_NUMBER
    ) -> ChapterAudio:
        """GET /chapter_recitations/{reciter_id}/{chapter_number}?segments=true."""
        data = self._request(
            "GET",
            f"/content/api/v4/chapter_recitations/{reciter_id}/{chapter_number}",
            params={"segments": "true"},
        )
        return parse_chapter_audio_response(data)

    def download_audio(self, url: str, destination: str) -> None:
        """Stream an audio file to disk (used for the reciter's chapter mp3)."""
        with self._session.get(url, stream=True, timeout=self.timeout_s) as response:
            if not response.ok:
                raise QuranFoundationError(
                    f"Failed to download audio from {url}: {response.status_code}"
                )
            with open(destination, "wb") as fh:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
