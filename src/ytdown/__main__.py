"""Start yt down.

python -m ytdown               app window (falls back to the browser)
python -m ytdown --browser     page in the browser, server stops with Ctrl+C
python -m ytdown --no-browser  server only (tests, CI)
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

from .core import tools
from .core.jobs import Manager
from .core.settings import Settings
from .server import APP_ID, make_server

DEFAULT_PORT = 8765
_PORT_ATTEMPTS = 20
_IDLE_EXIT_SECONDS = 90  # browser fallback without a console: exit once the page is gone
_LOG = Path.home() / ".ytdown" / "ytdown.log"


def _already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as response:
            return json.load(response).get("app") == APP_ID
    except (OSError, ValueError):
        return False


def _exit_when_page_gone(server, manager: Manager) -> None:
    while True:
        time.sleep(5)
        idle = time.monotonic() - server.last_seen
        if idle > _IDLE_EXIT_SECONDS and not manager.busy():
            server.shutdown()
            return


def run(args: argparse.Namespace) -> int:
    window = not args.browser and not args.no_browser

    if _already_running(args.port):
        url = f"http://127.0.0.1:{args.port}/"
        print(f"yt down è già in esecuzione: {url}")
        if window:
            from .desktop import open_window

            if open_window(url, lambda: False):
                return 0
        if not args.no_browser:
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
    tools.start_ytdlp_update()
    serving = threading.Thread(target=server.serve_forever, name="http", daemon=True)
    serving.start()
    try:
        if window:
            from .desktop import open_window

            if open_window(url, manager.busy):
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
        manager.shutdown()
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
        # The Windows/macOS apps have no console: keep a trace for troubleshooting.
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with _LOG.open("a", encoding="utf-8") as log:
            log.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
