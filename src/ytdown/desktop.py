"""Native app window (pywebview): the same page as the browser, in its own window.

macOS uses the system WebKit, Windows the Edge WebView2 runtime that ships with
Windows 10/11. If no window can be shown, `open_window` returns False and the caller
falls back to the browser.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from pathlib import Path

from .applog import log_exception

_WEB = Path(__file__).parent / "web"
TITLE = "yt down"
_LOCALIZATION = {
    "global.quitConfirmation": "Ci sono video in analisi o in download: chiudendo yt down "
    "verranno interrotti. Chiudere comunque?",
    "global.quit": "Chiudi",
    "global.cancel": "Annulla",
    "global.ok": "OK",
}


def _brand_macos() -> None:
    """Show "yt down" and its icon in the menu bar and Dock instead of "Python"."""
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle

        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        info["CFBundleName"] = TITLE
        image = NSImage.alloc().initWithContentsOfFile_(str(_WEB / "icon.png"))
        if image is not None:
            NSApplication.sharedApplication().setApplicationIconImage_(image)
    except Exception:
        pass  # cosmetic only


_observers: list = []  # keep the Objective-C observer alive


def _on_macos_quit(callback: Callable[[], None]) -> None:
    """Run `callback` when the app quits with Cmd+Q / Quit: macOS then ends the process
    directly, without returning from webview.start()."""
    try:
        from AppKit import NSApplicationWillTerminateNotification
        from Foundation import NSNotificationCenter, NSObject

        class _QuitObserver(NSObject):
            def appWillTerminate_(self, _notification) -> None:
                callback()

        observer = _QuitObserver.alloc().init()
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            observer, "appWillTerminate:", NSApplicationWillTerminateNotification, None
        )
        _observers.append(observer)
    except Exception:
        log_exception("registering the quit handler")


def _brand_windows() -> None:
    """Group the window under its own taskbar entry, not under Python's."""
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ytdown.app")
    except Exception:
        pass


def open_window(
    url: str,
    is_busy: Callable[[], bool],
    on_focus_ready: Callable[[Callable[[], None]], None] | None = None,
    on_quit: Callable[[], None] | None = None,
) -> bool:
    """Show the app window and block until the user closes it.

    `on_focus_ready` receives a function that brings the window to the front (used when the
    app is started a second time). `on_quit` runs when macOS quits the app directly.
    Returns False only when no window could be shown, so the
    caller can fall back to the browser without ever showing two interfaces.
    """
    try:
        import webview
    except Exception:
        log_exception("pywebview not available, using the browser")
        return False

    if sys.platform == "darwin":
        _brand_macos()
        if on_quit is not None:
            _on_macos_quit(on_quit)
    elif sys.platform == "win32":
        _brand_windows()

    shown = threading.Event()
    try:
        window = webview.create_window(
            TITLE, url, width=1120, height=860, min_size=(760, 560), text_select=True
        )

        def on_closing() -> None:
            # Ask for confirmation only when closing would interrupt work.
            window.confirm_close = is_busy()

        def focus() -> None:
            try:
                window.restore()
                window.show()
                window.on_top = True
                window.on_top = False
            except Exception:
                log_exception("focusing the window")

        window.events.closing += on_closing
        window.events.shown += shown.set
        if on_focus_ready is not None:
            on_focus_ready(focus)
        icon = _WEB / ("icon.ico" if sys.platform == "win32" else "icon.png")
        webview.start(localization=_LOCALIZATION, icon=str(icon), private_mode=True)
    except Exception:
        log_exception("app window")
        # The window was already on screen: it has been closed, do not open the browser too.
        return shown.is_set()
    return True
