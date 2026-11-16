"""Locate the external tools (yt-dlp, Deno, ffmpeg) and build the yt-dlp base command.

All three are installed as Python packages in the project environment, so the app
needs nothing on the system PATH. PATH is only a fallback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from importlib import metadata
from pathlib import Path

# The default yt-dlp clients expose only the original audio track. `web_embedded`
# also returns dubbed tracks; keeping `default` covers videos that cannot be embedded.
EXTRACTOR_ARGS = "youtube:player_client=default,web_embedded"


def python_executable() -> str:
    """Console Python for subprocesses: under pythonw.exe (Windows app) use python.exe."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").is_file():
        return str(exe.with_name("python.exe"))
    return sys.executable


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
        python_executable(),
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


# --- yt-dlp self-update -------------------------------------------------------------
# YouTube changes often, so each start upgrades yt-dlp in the background with uv. Every
# yt-dlp call waits (bounded) for the upgrade, so a run never sees a half-installed package.

_ready = threading.Event()
_ready.set()
_UPDATE_TIMEOUT = 120


def uv_path() -> str | None:
    """uv from YTDOWN_UV, the installer layout (<app>/bin next to <app>/.venv), or PATH."""
    candidates = [os.environ.get("YTDOWN_UV")]
    app_bin = Path(sys.prefix).parent / "bin"
    candidates += [str(app_bin / "uv.exe"), str(app_bin / "uv")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("uv")


_update_proc: subprocess.Popen | None = None


def start_ytdlp_update() -> threading.Thread | None:
    """Upgrade yt-dlp in this environment in the background. Offline it just keeps the
    installed version."""
    uv = uv_path()
    if uv is None:
        return None
    _ready.clear()

    def run() -> None:
        global _update_proc
        env = dict(os.environ, VIRTUAL_ENV=sys.prefix, UV_HTTP_TIMEOUT="15")
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        try:
            _update_proc = subprocess.Popen(
                [uv, "pip", "install", "--quiet", "--upgrade", "yt-dlp[default]"],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **flags,
            )
            _update_proc.wait(timeout=_UPDATE_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            stop_ytdlp_update()
        finally:
            _ready.set()

    thread = threading.Thread(target=run, name="ytdlp-update", daemon=True)
    thread.start()
    return thread


def stop_ytdlp_update() -> None:
    """Stop an update still running when the app closes (it would keep files locked)."""
    proc = _update_proc
    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait()


def wait_until_ready() -> None:
    _ready.wait(_UPDATE_TIMEOUT + 10)
