"""Pure function: (VideoInfo, Choice) -> ResolvedFormat with explicit format ids."""

from __future__ import annotations

from .models import AudioTrack, Choice, ResolvedFormat, VideoInfo, VideoStream, lang_key


class SelectionError(Exception):
    """The video has no separate video or audio stream to download."""


MP3_BITRATE = 192_000  # bits per second of the MP3 we produce


def resolve(video: VideoInfo, choice: Choice) -> ResolvedFormat:
    if choice.audio_only:
        return _resolve_audio_only(video, choice)
    if not video.video_streams:
        raise SelectionError("Nessuno stream video scaricabile per questo video.")
    if not video.audio_tracks:
        raise SelectionError("Nessuna traccia audio scaricabile per questo video.")

    notes: list[str] = []
    quality = _pick_quality(video, choice, notes)
    stream, container = _pick_stream(video, quality)
    track = _pick_audio(video, choice, container, notes)

    size = stream.size + track.size if stream.size and track.size else None
    return ResolvedFormat(
        format_spec=f"{stream.format_id}+{track.format_id}",
        quality=quality,
        audio_language=track.language,
        container=container,
        est_size=size,
        notes=tuple(notes),
    )


def _resolve_audio_only(video: VideoInfo, choice: Choice) -> ResolvedFormat:
    """Only the audio track (same language rules as video downloads), converted to MP3."""
    if not video.audio_tracks:
        raise SelectionError("Nessuna traccia audio scaricabile per questo video.")
    notes: list[str] = []
    track = _pick_audio(video, choice, "mp3", notes)
    size = int(video.duration * MP3_BITRATE / 8) if video.duration else None
    return ResolvedFormat(
        format_spec=track.format_id,
        quality=0,
        audio_language=track.language,
        container="mp3",
        est_size=size,
        notes=tuple(notes),
    )


def _pick_quality(video: VideoInfo, choice: Choice, notes: list[str]) -> int:
    qualities = sorted({s.quality for s in video.video_streams})
    if choice.max_quality is None:
        return qualities[-1]
    at_or_below = [q for q in qualities if q <= choice.max_quality]
    quality = at_or_below[-1] if at_or_below else qualities[0]
    if quality != choice.max_quality:
        notes.append(f"{choice.max_quality}p non disponibile: scaricato a {quality}p.")
    return quality


def _pick_stream(video: VideoInfo, quality: int) -> tuple[VideoStream, str]:
    """H.264 goes in mp4 for compatibility; anything else (VP9/AV1) goes in mkv."""
    streams = [s for s in video.video_streams if s.quality == quality]
    sdr = [s for s in streams if not s.hdr]
    streams = sdr or streams

    h264 = [s for s in streams if s.vcodec.startswith("avc1")]
    pool, container = (h264, "mp4") if h264 else (streams, "mkv")
    best = max(
        pool, key=lambda s: (s.direct, s.fps or 0, s.tbr or 0, -len(s.format_id), s.format_id)
    )
    return best, container


def _pick_audio(video: VideoInfo, choice: Choice, container: str, notes: list[str]) -> AudioTrack:
    tracks = list(video.audio_tracks)
    originals = [t for t in tracks if t.is_original]
    if not originals:
        originals = tracks
        notes.append("Traccia audio originale non identificata: usata la migliore disponibile.")

    wanted = lang_key(choice.audio_language)
    if wanted is None:
        pool = originals
    else:
        pool = [t for t in tracks if lang_key(t.language) == wanted]
        if not pool:
            pool = originals
            notes.append(
                f"Audio «{choice.audio_language}» non disponibile: usata la traccia originale."
            )

    def rank(track: AudioTrack) -> tuple:
        fits_mp4 = container == "mp4" and track.acodec.startswith("mp4a")
        return (
            fits_mp4,
            track.direct,
            track.abr or 0,
            -len(track.format_id),
            track.format_id,
        )

    return max(pool, key=rank)
