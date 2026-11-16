"""Local web server: serves the page and a small JSON API on 127.0.0.1 only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import tools
from .core.jobs import Manager
from .core.models import Choice
from .core.settings import validate_output_dir

_INDEX = Path(__file__).parent / "web" / "index.html"
_MAX_BODY = 1_000_000
APP_ID = "ytdown"


class ApiError(Exception):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


def make_server(manager: Manager, port: int) -> ThreadingHTTPServer:
    class Handler(_Handler):
        pass

    Handler.manager = manager
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.last_seen = time.monotonic()  # last page poll; used to exit once the page is gone
    server.focus_window = None  # set by the app window: brings it to the front
    return server


class _Handler(BaseHTTPRequestHandler):
    manager: Manager
    server_version = "ytdown"
    timeout = 30  # seconds; a client that stops sending cannot hold a thread forever

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        return  # the page polls every second: keep the terminal readable

    # ------------------------------------------------------------- transport

    def _allowed_hosts(self) -> set[str]:
        port = self.server.server_address[1]
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _check_origin(self) -> None:
        """Refuse requests that do not come from our own page (other sites, DNS rebinding)."""
        if self.headers.get("Host", "") not in self._allowed_hosts():
            raise ApiError("Host non valido.", HTTPStatus.FORBIDDEN)
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{h}" for h in self._allowed_hosts()}:
            raise ApiError("Origine non valida.", HTTPStatus.FORBIDDEN)

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ApiError("Serve Content-Type application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ApiError("Content-Length non valido.") from exc
        if length < 0:
            raise ApiError("Content-Length non valido.")
        if length > _MAX_BODY:
            raise ApiError("Richiesta troppo grande.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError as exc:
            raise ApiError("JSON non valido.") from exc
        if not isinstance(data, dict):
            raise ApiError("JSON non valido.")
        return data

    def _dispatch(self, handler) -> None:
        try:
            self._check_origin()
            handler()
        except ApiError as exc:
            self._send_json({"error": str(exc)}, exc.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # report instead of dropping the connection
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    # ---------------------------------------------------------------- routes

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._dispatch(self._get)

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        self._dispatch(self._post)

    def _get(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            body = _INDEX.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/ping":
            self._send_json({"app": APP_ID})
        elif path == "/api/state":
            self.server.last_seen = time.monotonic()
            state = self.manager.snapshot()
            state["tools"] = tools.status()
            self._send_json(state)
        else:
            raise ApiError("Non trovato.", HTTPStatus.NOT_FOUND)

    def _post(self) -> None:
        path = self.path.split("?", 1)[0]
        data = self._read_json()
        manager = self.manager

        if path == "/api/add":
            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ApiError("Incolla almeno un link.")
            self._send_json(manager.add(text))
        elif path == "/api/start":
            self._send_json({"started": manager.start(_choice(data))})
        elif path == "/api/focus":
            # A second start of the app asks the running one to show its window.
            focus = self.server.focus_window
            if focus is not None:
                focus()
            self._send_json({"focused": focus is not None})
        elif path == "/api/clear":
            self._send_json({"removed": manager.clear_finished()})
        elif path == "/api/settings":
            try:
                folder = validate_output_dir(str(data.get("output_dir") or ""))
            except ValueError as exc:
                raise ApiError(str(exc)) from exc
            manager.settings.output_dir = str(folder)
            manager.settings.save()
            self._send_json({"output_dir": manager.settings.output_dir})
        elif path == "/api/open":
            try:
                folder = validate_output_dir(manager.settings.output_dir)
            except ValueError as exc:
                raise ApiError(str(exc)) from exc
            _open_folder(folder)
            self._send_json({"opened": str(folder)})
        elif path.startswith("/api/items/"):
            parts = path.split("/")
            if len(parts) != 5 or parts[4] not in ("cancel", "retry", "remove"):
                raise ApiError("Non trovato.", HTTPStatus.NOT_FOUND)
            action = getattr(manager, parts[4])
            self._send_json({"ok": bool(action(parts[3]))})
        else:
            raise ApiError("Non trovato.", HTTPStatus.NOT_FOUND)


def _choice(data: dict) -> Choice:
    quality = data.get("max_quality")
    if quality is not None and (isinstance(quality, bool) or not isinstance(quality, int)):
        raise ApiError("max_quality deve essere un numero o null.")
    language = data.get("audio_language")
    if language is not None and (not isinstance(language, str) or not language.strip()):
        raise ApiError("audio_language deve essere un codice lingua o null.")
    return Choice(max_quality=quality, audio_language=language)


def _open_folder(folder: Path) -> None:
    if sys.platform == "win32":
        os.startfile(folder)  # noqa: S606 - opening the user's own download folder
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])
