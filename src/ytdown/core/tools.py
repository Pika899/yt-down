"""Locate the external tools (yt-dlp, Deno, ffmpeg) and build the yt-dlp base command.

All three are installed as Python packages in the project environment, so the app
needs nothing on the system PATH. PATH is only a fallback.
"""

from __future__ import annotations

import shutil
import sys
from importlib import metadata
from pathlib import Path

# The default yt-dlp clients expose only the original audio track. `web_embedded`
# also returns dubbed tracks; keeping `default` covers videos that cannot be embedded.
EXTRACTOR_ARGS = "youtube:player_client=default,web_embedded"


def deno_path() -> str | None:
    bin_dir = Path(sys.executable).parent
    for name in ("deno", "deno.exe"):
        candidate = bin_dir / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("deno")


def ffmpeg_path() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def ytdlp_version() -> str | None:
    try:
        return metadata.version("yt-dlp")
    except metadata.PackageNotFoundError:
        return None


def base_argv() -> list[str]:
    """Command prefix shared by every yt-dlp invocation."""
    argv = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--ignore-config",
        "--no-update",
        "--extractor-args",
        EXTRACTOR_ARGS,
    ]
    deno = deno_path()
    if deno:
        argv += ["--js-runtimes", f"deno:{deno}"]
    ffmpeg = ffmpeg_path()
    if ffmpeg:
        argv += ["--ffmpeg-location", ffmpeg]
    return argv


def status() -> dict[str, object]:
    return {
        "ytdlp": ytdlp_version(),
        "deno": deno_path() is not None,
        "ffmpeg": ffmpeg_path() is not None,
    }
