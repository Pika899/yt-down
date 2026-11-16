"""The only module that launches yt-dlp."""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
import sys
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
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)


def run_json(args: list[str], timeout: float = 180) -> dict:
    """Run yt-dlp with `args` and parse the JSON it prints on stdout."""
    tools.wait_until_ready()
    try:
        proc = subprocess.run(
            tools.base_argv() + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=_env(),
            stdin=subprocess.DEVNULL,
            **_popen_flags(),
        )
    except subprocess.TimeoutExpired as exc:
        raise YtDlpError(f"yt-dlp timed out after {int(timeout)}s") from exc

    if proc.returncode != 0:
        raise YtDlpError(extract_error(proc.stderr) or f"yt-dlp exited with code {proc.returncode}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise YtDlpError(extract_error(proc.stderr) or "yt-dlp returned no metadata") from exc
    if not isinstance(data, dict):
        raise YtDlpError("yt-dlp returned no metadata")
    return data


class Download:
    """A running yt-dlp download. Iterate `lines()` until it ends, then read `returncode`."""

    def __init__(self, args: list[str]) -> None:
        tools.wait_until_ready()
        self._proc = subprocess.Popen(
            tools.base_argv() + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=_env(),
            **_popen_flags(),
        )
        self.returncode: int | None = None

    def lines(self) -> Iterator[str]:
        assert self._proc.stdout is not None
        try:
            for line in self._proc.stdout:
                yield line.rstrip("\r\n")
        finally:
            self._proc.stdout.close()
            self.returncode = self._proc.wait()

    def cancel(self) -> None:
        _kill_tree(self._proc)
