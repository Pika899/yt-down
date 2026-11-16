"""Start yt down.

python -m ytdown               app window (falls back to the browser)
python -m ytdown --browser     page in the browser, server stops with Ctrl+C
python -m ytdown --no-browser  server only (tests, CI)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from .applog import log_exception
from .core import runner, tools
from .core.jobs import Manager
from .core.settings import Settings
from .server import APP_ID, make_server

DEFAULT_PORT = 8765
_PORT_ATTEMPTS = 20
_IDLE_EXIT_SECONDS = 90  # browser fallback without a console: exit once the page is gone
# The Windows installer reads this to close exactly this app before updating or uninstalling.
_PID_FILE = Path(sys.prefix) / "ytdown.pid"


def _call(port: int, path: str, body: dict | None = None) -> dict | None:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def _already_running(port: int) -> bool:
    answer = _call(port, "/api/ping")
    return bool(answer) and answer.get("app") == APP_ID


def _exit_when_page_gone(server, manager: Manager) -> None:
    while True:
        time.sleep(5)
        idle = time.monotonic() - server.last_seen
        if idle > _IDLE_EXIT_SECONDS and not manager.busy():
            server.shutdown()
            return


def _write_pid() -> None:
    with contextlib.suppress(OSError):
        _PID_FILE.write_text(str(os.getpid()), encoding="ascii")


def _remove_pid() -> None:
    with contextlib.suppress(OSError):
        if _PID_FILE.read_text(encoding="ascii").strip() == str(os.getpid()):
            _PID_FILE.unlink()


def run(args: argparse.Namespace) -> int:
    window = not args.browser and not args.no_browser

    if _already_running(args.port):
        # One app at a time: bring the open window to the front instead of a second one.
        url = f"http://127.0.0.1:{args.port}/"
        print(f"yt down è già in esecuzione: {url}")
        focused = window and (_call(args.port, "/api/focus", {}) or {}).get("focused")
        if not focused and not args.no_browser:
            webbrowser.open(url)
        return 0

    manager = Manager(Settings.load())
    server = None
    for port in range(args.port, args.port + _PORT_ATTEMPTS):
        try:
            server = make_server(manager, port)
            break
        except OSError:
            continue
    if server is None:
        print(f"Nessuna porta libera tra {args.port} e {args.port + _PORT_ATTEMPTS - 1}.")
        return 1

    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"yt down in esecuzione: {url}")
    print(f"Cartella download: {manager.settings.output_dir}")
    _write_pid()
    tools.start_ytdlp_update()
    serving = threading.Thread(target=server.serve_forever, name="http", daemon=True)
    serving.start()
    stopped = threading.Event()

    def stop_everything() -> None:
        """Stop all that could outlive the window: downloads, analyses, the update."""
        if stopped.is_set():
            return
        stopped.set()
        # Each step runs even if an earlier one fails: nothing may be left running.
        for step in (manager.shutdown, runner.terminate_all, tools.stop_ytdlp_update, _remove_pid):
            try:
                step()
            except Exception:
                log_exception(f"closing: {step.__name__}")

    try:
        if window:
            from .desktop import open_window

            def register_focus(focus) -> None:
                server.focus_window = focus

            if open_window(url, manager.busy, register_focus, stop_everything):
                return 0
            # No native window available: use the browser and stop when the tab is closed.
            threading.Thread(
                target=_exit_when_page_gone, args=(server, manager), daemon=True
            ).start()
        if not args.no_browser:
            webbrowser.open(url)
        print("Lascia aperta questa finestra. Per chiudere: Ctrl+C.")
        while serving.is_alive():
            serving.join(timeout=1)
    except KeyboardInterrupt:
        print("\nChiusura in corso…")
    finally:
        stop_everything()
        server.shutdown()
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="ytdown", description="yt down - downloader locale")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--browser", action="store_true", help="apri nel browser, non in finestra")
    mode.add_argument("--no-browser", action="store_true", help="solo server, senza interfaccia")
    args = parser.parse_args()
    try:
        return run(args)
    except Exception:
        log_exception("yt down stopped with an error")  # the apps have no console
        raise


if __name__ == "__main__":
    raise SystemExit(main())
