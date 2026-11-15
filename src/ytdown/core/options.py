"""Aggregate what a set of videos offers, so one question can cover all of them."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from .models import VideoInfo, lang_key


@dataclass(frozen=True)
class BatchOptions:
    total: int
    qualities: tuple[tuple[int, int], ...]  # (quality, videos offering it), highest first
    languages: tuple[tuple[str, int], ...]  # (language key, videos offering it)
    multi_language: bool  # at least one video has more than one audio language


def aggregate(videos: Iterable[VideoInfo]) -> BatchOptions:
    quality_counts: Counter[int] = Counter()
    language_counts: Counter[str] = Counter()
    multi_language = False
    total = 0

    for video in videos:
        total += 1
        quality_counts.update({s.quality for s in video.video_streams})
        langs = {key for t in video.audio_tracks if (key := lang_key(t.language))}
        language_counts.update(langs)
        if len(langs) > 1:
            multi_language = True

    return BatchOptions(
        total=total,
        qualities=tuple(sorted(quality_counts.items(), reverse=True)),
        languages=tuple(sorted(language_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        multi_language=multi_language,
    )
