"""Turn pasted text into a deduplicated list of YouTube video and playlist sources."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .models import Source, SourceKind

_TOKEN = re.compile(r"[^\s<>\"',;]+")
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PLAYLIST_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_YOUTUBE_HOSTS = {"youtube.com", "youtube-nocookie.com"}
_PATH_VIDEO_PREFIXES = ("shorts", "live", "embed", "v")


def parse(text: str) -> tuple[list[Source], list[str]]:
    """Return (sources, rejected). `rejected` holds link-like tokens that are not supported."""
    sources: list[Source] = []
    rejected: list[str] = []
    seen: set[tuple[SourceKind, str]] = set()

    for token in _TOKEN.findall(text):
        if not _looks_like_link(token):
            continue
        source = classify(token)
        if source is None:
            rejected.append(token)
            continue
        key = (source.kind, source.id)
        if key not in seen:
            seen.add(key)
            sources.append(source)
    return sources, rejected


def classify(raw: str) -> Source | None:
    """Classify a single link. Returns None when it is not a YouTube video or playlist."""
    url = raw.strip().rstrip(".)]}")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    try:
        parts = urlsplit(url)
    except ValueError:
        return None

    host = (parts.hostname or "").lower()
    for prefix in ("www.", "m.", "music."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
            break
    segments = [s for s in parts.path.split("/") if s]
    query = parse_qs(parts.query)

    if host == "youtu.be":
        return _video(segments[0]) if segments else None
    if host not in _YOUTUBE_HOSTS:
        return None

    first = segments[0] if segments else ""
    if first == "watch":
        # A watch link is always one video, even when it carries a list= parameter.
        return _video(query.get("v", [""])[0])
    if first == "playlist":
        return _playlist(query.get("list", [""])[0])
    if first in _PATH_VIDEO_PREFIXES and len(segments) >= 2:
        return _video(segments[1])
    return None


def _looks_like_link(token: str) -> bool:
    lowered = token.lower()
    return lowered.startswith(("http://", "https://")) or "youtu" in lowered


def _video(video_id: str) -> Source | None:
    if not _VIDEO_ID.match(video_id):
        return None
    return Source(f"https://www.youtube.com/watch?v={video_id}", SourceKind.VIDEO, video_id)


def _playlist(playlist_id: str) -> Source | None:
    if not _PLAYLIST_ID.match(playlist_id):
        return None
    return Source(
        f"https://www.youtube.com/playlist?list={playlist_id}", SourceKind.PLAYLIST, playlist_id
    )
