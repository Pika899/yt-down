"""Read video and playlist metadata from yt-dlp JSON."""

from __future__ import annotations

import re
from dataclasses import replace

from . import runner
from .models import AudioTrack, Playlist, PlaylistEntry, Source, VideoInfo, VideoStream, lang_key

_QUALITY_LABEL = re.compile(r"(\d{3,4})p")
ORIGINAL_LANGUAGE_PREFERENCE = 10  # yt-dlp marks the original audio track with this value


def probe_video(url: str) -> VideoInfo:
    return parse_video(runner.run_json(["-J", "--no-playlist", url]))


def expand_playlist(source: Source) -> Playlist:
    return parse_playlist(runner.run_json(["-J", "--flat-playlist", source.url], timeout=600))


def parse_playlist(data: dict) -> Playlist:
    entries = []
    for entry in data.get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        entries.append(
            PlaylistEntry(id=entry["id"], title=entry.get("title"), duration=entry.get("duration"))
        )
    return Playlist(
        id=str(data.get("id") or ""),
        title=str(data.get("title") or data.get("id") or "playlist"),
        entries=tuple(entries),
    )


def parse_video(data: dict) -> VideoInfo:
    video_streams: list[VideoStream] = []
    audio_tracks: list[AudioTrack] = []

    for fmt in data.get("formats") or []:
        if fmt.get("has_drm") or fmt.get("ext") == "mhtml":
            continue
        has_video = fmt.get("vcodec") not in (None, "none")
        has_audio = fmt.get("acodec") not in (None, "none")
        format_id = str(fmt.get("format_id") or "")
        if not format_id:
            continue
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        direct = fmt.get("protocol") in ("https", "http")

        if has_video and not has_audio:
            quality = _quality(fmt)
            if quality is None:
                continue
            video_streams.append(
                VideoStream(
                    format_id=format_id,
                    quality=quality,
                    fps=fmt.get("fps"),
                    vcodec=str(fmt["vcodec"]),
                    ext=str(fmt.get("ext") or ""),
                    tbr=fmt.get("tbr"),
                    hdr=str(fmt.get("dynamic_range") or "SDR").upper() != "SDR",
                    direct=direct,
                    size=size,
                )
            )
        elif has_audio and not has_video:
            if format_id.endswith("-drc"):  # dynamic-range-compressed duplicate
                continue
            note = str(fmt.get("format_note") or "").lower()
            audio_tracks.append(
                AudioTrack(
                    format_id=format_id,
                    language=fmt.get("language"),
                    is_original=fmt.get("language_preference") == ORIGINAL_LANGUAGE_PREFERENCE
                    or "original" in note,
                    abr=fmt.get("abr") or fmt.get("tbr"),
                    acodec=str(fmt["acodec"]),
                    ext=str(fmt.get("ext") or ""),
                    direct=direct,
                    size=size,
                )
            )

    # With a single language there is nothing to tell apart: every track is the original.
    if len({lang_key(t.language) for t in audio_tracks}) <= 1:
        audio_tracks = [replace(t, is_original=True) for t in audio_tracks]

    video_id = str(data.get("id") or "")
    return VideoInfo(
        id=video_id,
        title=str(data.get("title") or video_id),
        url=str(data.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"),
        duration=data.get("duration"),
        channel=data.get("channel") or data.get("uploader"),
        video_streams=tuple(video_streams),
        audio_tracks=tuple(audio_tracks),
    )


def _quality(fmt: dict) -> int | None:
    """Quality as YouTube labels it ("1080p60" -> 1080); falls back to the frame height."""
    match = _QUALITY_LABEL.search(str(fmt.get("format_note") or ""))
    if match:
        return int(match.group(1))
    height = fmt.get("height")
    return int(height) if height else None
