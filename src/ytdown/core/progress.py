"""Parse the lines yt-dlp prints during a download (see `download_args`)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import runner

DL_PREFIX = "YTD-DL "
PP_PREFIX = "YTD-PP "
FILE_PREFIX = "YTD-FILE "


@dataclass(frozen=True)
class DownloadProgress:
    filename: str  # changes when yt-dlp moves from the video stream to the audio stream
    downloaded: int
    total: int | None
    speed: float | None  # bytes per second
    eta: float | None  # seconds
    finished: bool


@dataclass(frozen=True)
class PostProcess:
    name: str  # e.g. "Merger"
    status: str  # "started" | "processing" | "finished"


@dataclass(frozen=True)
class FinalFile:
    path: str


@dataclass(frozen=True)
class ErrorLine:
    message: str


Event = DownloadProgress | PostProcess | FinalFile | ErrorLine


def download_args(format_spec: str, container: str, output_template: str, url: str) -> list[str]:
    """yt-dlp arguments for one download, with machine-readable progress on stdout.

    For "mp3" only the audio stream is downloaded, then converted by ffmpeg; title and
    channel go into the MP3 tags.
    """
    if container == "mp3":
        output = ["-x", "--audio-format", "mp3", "--audio-quality", "192K", "--embed-metadata"]
    else:
        output = ["--merge-output-format", container]
    return [
        "-f",
        format_spec,
        *output,
        "--no-playlist",
        "--no-simulate",
        "--progress",
        "--newline",
        "--progress-template",
        f"download:{DL_PREFIX}%(progress)j",
        "--progress-template",
        f"postprocess:{PP_PREFIX}%(progress)j",
        "--print",
        f"after_move:{FILE_PREFIX}%(filepath)s",
        "-o",
        output_template,
        url,
    ]


def parse_line(line: str) -> Event | None:
    line = line.strip()
    if line.startswith(DL_PREFIX):
        data = _json(line[len(DL_PREFIX) :])
        if data is None:
            return None
        return DownloadProgress(
            filename=str(data.get("filename") or ""),
            downloaded=_int(data.get("downloaded_bytes")) or 0,
            total=_int(data.get("total_bytes") or data.get("total_bytes_estimate")),
            speed=_float(data.get("speed")),
            eta=_float(data.get("eta")),
            finished=data.get("status") == "finished",
        )
    if line.startswith(PP_PREFIX):
        data = _json(line[len(PP_PREFIX) :])
        if data is None:
            return None
        return PostProcess(
            name=str(data.get("postprocessor") or ""), status=str(data.get("status") or "")
        )
    if line.startswith(FILE_PREFIX):
        return FinalFile(line[len(FILE_PREFIX) :])
    if line.startswith("ERROR:"):
        return ErrorLine(runner.extract_error(line) or line)
    return None


def _json(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _int(value: object) -> int | None:
    number = _float(value)
    return int(number) if number else None


def _float(value: object) -> float | None:
    """Numbers from yt-dlp JSON; anything else (None, text, NaN) becomes None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if number == number and number >= 0 else None
