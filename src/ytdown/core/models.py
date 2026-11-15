"""Shared data contract between the core modules and the web server."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceKind(StrEnum):
    VIDEO = "video"
    PLAYLIST = "playlist"


@dataclass(frozen=True)
class Source:
    """A user-supplied link after parsing and normalization."""

    url: str  # canonical URL
    kind: SourceKind
    id: str


@dataclass(frozen=True)
class VideoStream:
    format_id: str
    quality: int  # YouTube quality label as a number, e.g. 1080 for "1080p60"
    fps: float | None
    vcodec: str
    ext: str
    tbr: float | None  # total bitrate in kbps, used as tie-breaker
    hdr: bool
    direct: bool  # plain HTTPS file (faster, known size) rather than HLS/DASH segments
    size: int | None  # bytes, exact or approximate


@dataclass(frozen=True)
class AudioTrack:
    format_id: str
    language: str | None  # as reported by yt-dlp, e.g. "en", "en-US", "zh-Hans"
    is_original: bool
    abr: float | None
    acodec: str
    ext: str
    direct: bool
    size: int | None


@dataclass(frozen=True)
class VideoInfo:
    """Probe result for one video id."""

    id: str
    title: str
    url: str
    duration: float | None
    channel: str | None
    video_streams: tuple[VideoStream, ...]
    audio_tracks: tuple[AudioTrack, ...]


@dataclass(frozen=True)
class PlaylistEntry:
    id: str
    title: str | None
    duration: float | None


@dataclass(frozen=True)
class Playlist:
    id: str
    title: str
    entries: tuple[PlaylistEntry, ...]


@dataclass(frozen=True)
class Choice:
    """One decision applied to every video waiting for it."""

    max_quality: int | None  # None = best available
    audio_language: str | None  # None = original track; matched on the primary subtag


@dataclass(frozen=True)
class ResolvedFormat:
    """Result of applying a Choice to one VideoInfo."""

    format_spec: str  # explicit ids, e.g. "137+140-10"
    quality: int
    audio_language: str | None
    container: str  # "mp4" or "mkv"
    est_size: int | None  # bytes; None when yt-dlp reports no size
    notes: tuple[str, ...] = ()  # user-facing notes on every deviation from the Choice


class ItemState(StrEnum):
    ANALYZING = "analyzing"
    READY = "ready"  # analyzed, waiting for the user's choice
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


def lang_key(code: str | None) -> str | None:
    """Primary language subtag, lowercased: 'en-US' -> 'en'."""
    if not code:
        return None
    return code.replace("_", "-").split("-")[0].lower()
