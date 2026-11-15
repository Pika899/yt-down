"""Start yt down: `python -m ytdown` opens the app in the browser."""

from __future__ import annotations

import argparse
import json
import urllib.request
import webbrowser

from .core.jobs import Manager
from .core.settings import Settings
from .server import APP_ID, make_server

DEFAULT_PORT = 8765
_PORT_ATTEMPTS = 20


def _already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as response:
            return json.load(response).get("app") == APP_ID
    except (OSError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(prog="ytdown", description="yt down - downloader locale")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="non aprire il browser")
    args = parser.parse_args()

    if _already_running(args.port):
        url = f"http://127.0.0.1:{args.port}/"
        print(f"yt down è già in esecuzione: {url}")
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
    print("Lascia aperta questa finestra. Per chiudere: Ctrl+C.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiusura in corso…")
    finally:
        manager.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
