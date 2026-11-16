"""The only module that launches yt-dlp."""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
from collections.abc import Iterator

from . import tools

_ERROR_LINE = re.compile(r"^ERROR:\s*(?:\[[^\]]+\]\s*)?(?:[A-Za-z0-9_-]{11}:\s*)?(.*)$")


class YtDlpError(Exception):
    """yt-dlp failed; the message is the cleaned text of its last ERROR line."""


def extract_error(output: str) -> str | None:
    """Return the message of the last `ERROR:` line in yt-dlp output, if any."""
    message = None
    for line in output.splitlines():
        match = _ERROR_LINE.match(line.strip())
        if match and match.group(1):
            message = match.group(1).strip()
    return message


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"  # yt-dlp must emit UTF-8 regardless of the Windows code page
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _popen_flags() -> dict[str, object]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    # Own process group, so cancelling also stops the ffmpeg child that yt-dlp starts.
    return {"start_new_session": True}


def _kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    else:
        # EPERM: the group is already exiting (macOS), e.g. a cancelled download killed again.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGTERM)


# Every running yt-dlp process, so the app can stop them all when it closes.
_live: set[subprocess.Popen] = set()
_live_lock = threading.Lock()
_closed = False


def _start(args: list[str], **kwargs: object) -> subprocess.Popen:
    with _live_lock:
        if _closed:
            raise YtDlpError("yt down si sta chiudendo.")
        proc = subprocess.Popen(
            tools.base_argv() + args,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_env(),
            stdin=subprocess.DEVNULL,
            **_popen_flags(),
            **kwargs,
        )
        _live.add(proc)
        return proc


def _forget(proc: subprocess.Popen) -> None:
    with _live_lock:
        _live.discard(proc)


def terminate_all() -> None:
    """Stop every yt-dlp process (and its ffmpeg) and refuse to start new ones."""
    global _closed
    with _live_lock:
        _closed = True
        procs = list(_live)
    for proc in procs:
        _kill_tree(proc)


def run_json(args: list[str], timeout: float = 180) -> dict:
    """Run yt-dlp with `args` and parse the JSON it prints on stdout."""
    tools.wait_until_ready()
    proc = _start(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_tree(proc)
        proc.communicate()
        raise YtDlpError(f"yt-dlp timed out after {int(timeout)}s") from exc
    finally:
        _forget(proc)

    if proc.returncode != 0:
        raise YtDlpError(extract_error(stderr) or f"yt-dlp exited with code {proc.returncode}")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise YtDlpError(extract_error(stderr) or "yt-dlp returned no metadata") from exc
    if not isinstance(data, dict):
        raise YtDlpError("yt-dlp returned no metadata")
    return data


class Download:
    """A running yt-dlp download. Iterate `lines()` until it ends, then read `returncode`."""

    def __init__(self, args: list[str]) -> None:
        self._proc = _start(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        self.returncode: int | None = None

    def lines(self) -> Iterator[str]:
        assert self._proc.stdout is not None
        try:
            for line in self._proc.stdout:
                yield line.rstrip("\r\n")
        finally:
            self._proc.stdout.close()
            self.returncode = self._proc.wait()
            _forget(self._proc)

    def cancel(self) -> None:
        _kill_tree(self._proc)
