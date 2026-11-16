"""The queue: analyze links, wait for the user's choice, then download.

A video that fails never stops the others.
"""

from __future__ import annotations

import itertools
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import links, options, probe, progress, runner, selection, tools
from .models import (
    Choice,
    ItemState,
    Playlist,
    ResolvedFormat,
    Source,
    SourceKind,
    VideoInfo,
)
from .settings import Settings

_ACTIVE = {ItemState.DOWNLOADING, ItemState.MERGING}
_FINISHED = {ItemState.DONE, ItemState.FAILED, ItemState.CANCELLED}
_FORMAT_GONE = "Requested format is not available"
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass
class Item:
    """One output file. The same video in two playlists yields two items."""

    id: str
    video_id: str
    url: str
    title: str | None = None
    duration: float | None = None
    playlist_id: str | None = None
    playlist_title: str | None = None
    playlist_index: int | None = None
    playlist_count: int | None = None
    state: ItemState = ItemState.ANALYZING
    progress: float | None = None  # 0..1 over the whole download; None = unknown
    speed: float | None = None
    eta: float | None = None
    info: VideoInfo | None = None
    choice: Choice | None = None
    resolved: ResolvedFormat | None = None
    output_path: str | None = None
    error: str | None = None
    notes: list[str] = field(default_factory=list)
    cancel_requested: bool = False
    download: Any = None  # running runner.Download, if any
    # Bumped by every new attempt (choice, retry, cancel). A worker only writes to the item
    # while the attempt it was started for is still current, so stale workers are inert.
    attempt: int = 0

    def public(self) -> dict:
        resolved = self.resolved
        return {
            "id": self.id,
            "video_id": self.video_id,
            "url": self.url,
            "title": self.title,
            "duration": self.duration,
            "playlist_title": self.playlist_title,
            "playlist_index": self.playlist_index,
            "state": self.state.value,
            "progress": self.progress,
            "speed": self.speed,
            "eta": self.eta,
            "quality": resolved.quality if resolved else None,
            "audio_language": resolved.audio_language if resolved else None,
            "container": resolved.container if resolved else None,
            "est_size": resolved.est_size if resolved else None,
            "output_path": self.output_path,
            "error": self.error,
            "notes": list(self.notes),
        }


class Manager:
    def __init__(
        self,
        settings: Settings,
        *,
        probe_video: Callable[[str], VideoInfo] = probe.probe_video,
        expand_playlist: Callable[[Source], Playlist] = probe.expand_playlist,
        spawn_download: Callable[[list[str]], Any] = runner.Download,
        probe_workers: int = 3,
        download_workers: int = 2,
    ) -> None:
        self.settings = settings
        self._probe_video = probe_video
        self._expand_playlist = expand_playlist
        self._spawn_download = spawn_download
        self._lock = threading.RLock()
        self._items: dict[str, Item] = {}  # insertion order is display order
        self._info_cache: dict[str, VideoInfo] = {}
        self._problems: list[dict[str, str]] = []
        self._expanding = 0
        self._ids = itertools.count(1)
        self._probe_pool = ThreadPoolExecutor(probe_workers, thread_name_prefix="probe")
        self._download_pool = ThreadPoolExecutor(download_workers, thread_name_prefix="download")

    # ------------------------------------------------------------------ input

    def add(self, text: str) -> dict:
        sources, rejected = links.parse(text)
        added = 0
        with self._lock:
            for token in rejected:
                self._problems.append(
                    {
                        "input": token,
                        "message": "Link non supportato (serve un video o una playlist YouTube).",
                    }
                )
            for source in sources:
                if source.kind is SourceKind.VIDEO:
                    added += int(self._add_item(source.id))
                else:
                    self._expanding += 1
                    self._probe_pool.submit(self._expand, source)
        return {
            "videos": added,
            "playlists": sum(s.kind is SourceKind.PLAYLIST for s in sources),
            "rejected": len(rejected),
        }

    def _add_item(
        self,
        video_id: str,
        title: str | None = None,
        duration: float | None = None,
        playlist: Playlist | None = None,
        index: int | None = None,
    ) -> bool:
        """Create an item unless the same video is already queued in the same playlist context."""
        playlist_id = playlist.id if playlist else None
        for existing in self._items.values():
            if existing.video_id == video_id and existing.playlist_id == playlist_id:
                return False
        item = Item(
            id=str(next(self._ids)),
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=title,
            duration=duration,
            playlist_id=playlist_id,
            playlist_title=playlist.title if playlist else None,
            playlist_index=index,
            playlist_count=len(playlist.entries) if playlist else None,
        )
        self._items[item.id] = item
        self._probe_pool.submit(self._analyze, item.id, item.attempt)
        return True

    def _expand(self, source: Source) -> None:
        try:
            playlist = self._expand_playlist(source)
        except Exception as exc:  # the batch must go on whatever a single source does
            with self._lock:
                self._expanding -= 1
                self._problems.append({"input": source.url, "message": _message(exc)})
            return
        with self._lock:
            self._expanding -= 1
            if not playlist.entries:
                self._problems.append({"input": source.url, "message": "La playlist è vuota."})
            for index, entry in enumerate(playlist.entries, start=1):
                self._add_item(entry.id, entry.title, entry.duration, playlist, index)

    # --------------------------------------------------------------- analysis

    @staticmethod
    def _current(item: Item, attempt: int, *states: ItemState) -> bool:
        """True while `attempt` is still the item's live attempt (and in one of `states`)."""
        return item.attempt == attempt and (not states or item.state in states)

    def _analyze(self, item_id: str, attempt: int) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if item is None or not self._current(item, attempt, ItemState.ANALYZING):
                return
            info = self._info_cache.get(item.video_id)
            url = item.url
        try:
            if info is None:
                info = self._probe_video(url)
        except Exception as exc:
            with self._lock:
                if self._current(item, attempt, ItemState.ANALYZING):
                    item.state = ItemState.FAILED
                    item.error = _message(exc)
            return

        with self._lock:
            self._info_cache[info.id] = info
            if not self._current(item, attempt, ItemState.ANALYZING):
                return
            item.info = info
            item.title = info.title
            item.duration = info.duration
            if item.choice is not None:  # retry of an item whose choice was already made
                self._queue(item, item.choice)
            else:
                item.state = ItemState.READY

    # ----------------------------------------------------------------- choice

    def start(self, choice: Choice) -> int:
        """Apply `choice` to every analyzed item waiting for it and queue the downloads."""
        started = 0
        with self._lock:
            for item in self._items.values():
                if item.state is ItemState.READY:
                    started += int(self._queue(item, choice))
        return started

    def _queue(self, item: Item, choice: Choice) -> bool:
        assert item.info is not None
        item.attempt += 1
        item.choice = choice
        item.error = None
        item.progress = None
        item.speed = item.eta = None
        item.cancel_requested = False
        try:
            item.resolved = selection.resolve(item.info, choice)
        except selection.SelectionError as exc:
            item.state = ItemState.FAILED
            item.error = str(exc)
            return False
        item.notes = list(item.resolved.notes)
        item.state = ItemState.QUEUED
        self._download_pool.submit(self._download, item.id, item.attempt)
        return True

    # --------------------------------------------------------------- download

    def _download(self, item_id: str, attempt: int) -> None:
        try:
            self._download_unsafe(item_id, attempt)
        except Exception as exc:  # never let a worker die silently
            with self._lock:
                item = self._items.get(item_id)
                if (
                    item is not None
                    and self._current(item, attempt)
                    and item.state not in _FINISHED
                ):
                    item.state = ItemState.FAILED
                    item.error = _message(exc)
                    item.download = None

    def _download_unsafe(self, item_id: str, attempt: int) -> None:
        reprobed = False
        while True:
            tools.wait_until_ready()  # never wait for the yt-dlp update while holding the lock
            with self._lock:
                item = self._items.get(item_id)
                if (
                    item is None
                    or not self._current(item, attempt, ItemState.QUEUED)
                    or item.resolved is None
                ):
                    return
                resolved = item.resolved
                template = self._output_template(item)
                item.state = ItemState.DOWNLOADING
                item.progress = 0.0
                args = progress.download_args(
                    resolved.format_spec, resolved.container, template, item.url
                )
                download = self._spawn_download(args)
                item.download = download

            error = self._follow(item, attempt, download, resolved)

            with self._lock:
                if not self._current(item, attempt):
                    return
                item.download = None
                item.speed = item.eta = None
                if item.cancel_requested:
                    item.state = ItemState.CANCELLED
                    return
                if download.returncode == 0:
                    item.state = ItemState.DONE
                    item.progress = 1.0
                    return
                if error and _FORMAT_GONE in error and not reprobed:
                    reprobed = True  # format ids changed since the analysis: look again once
                    self._info_cache.pop(item.video_id, None)
                    item.state = ItemState.QUEUED
                    choice = item.choice
                else:
                    item.state = ItemState.FAILED
                    item.error = error or f"yt-dlp si è chiuso con codice {download.returncode}."
                    return

            info = self._probe_video(item.url)
            with self._lock:
                self._info_cache[info.id] = info
                if not self._current(item, attempt, ItemState.QUEUED) or choice is None:
                    return
                item.info = info
                item.resolved = selection.resolve(info, choice)
                item.notes = [
                    *item.resolved.notes,
                    "I formati sono cambiati durante l'attesa: scelta ricalcolata.",
                ]

    def _follow(
        self, item: Item, attempt: int, download: Any, resolved: ResolvedFormat
    ) -> str | None:
        """Consume the download's output, updating the item. Returns the last error message."""
        error: str | None = None
        files_done = 0  # bytes of the streams already completed
        current_file = ""
        current_total = 0
        streams_seen = 0

        for line in download.lines():
            event = progress.parse_line(line)
            if event is None:
                continue
            with self._lock:
                if not self._current(item, attempt):
                    continue  # keep draining the pipe, but this attempt no longer owns the item
                if isinstance(event, progress.DownloadProgress):
                    if event.filename != current_file:
                        files_done += current_total
                        current_file, current_total = event.filename, 0
                        streams_seen += 1
                    current_total = event.total or event.downloaded
                    item.speed, item.eta = event.speed, event.eta
                    if resolved.est_size:
                        fraction = (files_done + event.downloaded) / resolved.est_size
                    elif event.total:
                        # no size estimate: video and audio count as half each
                        fraction = (streams_seen - 1 + event.downloaded / event.total) / 2
                    else:
                        fraction = None
                    item.progress = None if fraction is None else max(0.0, min(fraction, 0.99))
                elif isinstance(event, progress.PostProcess):
                    if event.status == "started" and item.state is ItemState.DOWNLOADING:
                        item.state = ItemState.MERGING
                        item.progress = 0.99
                        item.speed = item.eta = None
                elif isinstance(event, progress.FinalFile):
                    item.output_path = event.path
                elif isinstance(event, progress.ErrorLine):
                    error = event.message
        return error

    def _output_template(self, item: Item) -> str:
        folder = Path(self.settings.output_dir)
        prefix = ""
        if item.playlist_title:
            folder = folder / safe_name(item.playlist_title)
            width = max(2, len(str(item.playlist_count or 0)))
            prefix = f"{item.playlist_index or 0:0{width}d} - "
        # Everything but the last part is literal text: escape "%" for yt-dlp's template.
        literal = str(folder / "_")[:-1].replace("%", "%%")
        return f"{literal}{prefix}%(title).150B [%(id)s].%(ext)s"

    # ---------------------------------------------------------------- actions

    def cancel(self, item_id: str) -> bool:
        with self._lock:
            item = self._items.get(item_id)
            if item is None or item.state in _FINISHED:
                return False
            if item.state in _ACTIVE:
                # The download worker sees the flag and marks the item cancelled itself.
                item.cancel_requested = True
                if item.download is not None:
                    item.download.cancel()
            else:
                item.attempt += 1  # pending analysis or queued download becomes stale
                item.state = ItemState.CANCELLED
            return True

    def retry(self, item_id: str) -> bool:
        with self._lock:
            item = self._items.get(item_id)
            if item is None or item.state not in (ItemState.FAILED, ItemState.CANCELLED):
                return False
            item.error = None
            item.cancel_requested = False
            if item.info is not None and item.choice is not None:
                return self._queue(item, item.choice)
            item.attempt += 1
            if item.info is not None:
                item.state = ItemState.READY
                return True
            item.state = ItemState.ANALYZING
            self._probe_pool.submit(self._analyze, item.id, item.attempt)
            return True

    def remove(self, item_id: str) -> bool:
        with self._lock:
            item = self._items.get(item_id)
            if item is None or item.state in _ACTIVE:
                return False
            del self._items[item_id]
            return True

    def clear_finished(self) -> int:
        with self._lock:
            finished = [i.id for i in self._items.values() if i.state in _FINISHED]
            for item_id in finished:
                del self._items[item_id]
            self._problems.clear()
            return len(finished)

    def shutdown(self) -> None:
        with self._lock:
            for item in self._items.values():
                item.cancel_requested = True
                if item.download is not None:
                    item.download.cancel()
        self._probe_pool.shutdown(wait=False, cancel_futures=True)
        self._download_pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ state

    def busy(self) -> bool:
        """True while anything is being analyzed, queued or downloaded."""
        working = {ItemState.ANALYZING, ItemState.QUEUED, *_ACTIVE}
        with self._lock:
            return bool(self._expanding) or any(i.state in working for i in self._items.values())

    def snapshot(self) -> dict:
        with self._lock:
            items = [item.public() for item in self._items.values()]
            waiting = [
                i.info
                for i in self._items.values()
                if i.state is ItemState.READY and i.info is not None
            ]
            analyzing = sum(i.state is ItemState.ANALYZING for i in self._items.values())
            return {
                "items": items,
                "analyzing": analyzing,
                "expanding": self._expanding,
                "options": asdict(options.aggregate(waiting)),
                "problems": list(self._problems),
                "output_dir": self.settings.output_dir,
            }


def safe_name(name: str, limit: int = 100) -> str:
    """Make a playlist title usable as a folder name on Windows and macOS."""
    cleaned = _UNSAFE_NAME.sub(" ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    cleaned = cleaned[:limit].rstrip(" .") or "playlist"
    if cleaned.split(".")[0].strip().upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"  # CON, NUL, COM1… cannot be folder names on Windows
    return cleaned


def _message(exc: Exception) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__
