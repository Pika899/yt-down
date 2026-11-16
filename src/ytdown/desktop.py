"""Native app window (pywebview): the same page as the browser, in its own window.

macOS uses the system WebKit, Windows the Edge WebView2 runtime that ships with
Windows 10/11. If neither works, `open_window` returns False and the caller falls back
to the browser.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

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

        info = (
            NSBundle.mainBundle().localizedInfoDictionary()
            or NSBundle.mainBundle().infoDictionary()
        )
        info["CFBundleName"] = TITLE
        image = NSImage.alloc().initWithContentsOfFile_(str(_WEB / "icon.png"))
        if image is not None:
            NSApplication.sharedApplication().setApplicationIconImage_(image)
    except Exception:
        pass  # cosmetic only


def _brand_windows() -> None:
    """Group the window under its own taskbar entry, not under Python's."""
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ytdown.app")
    except Exception:
        pass


def open_window(url: str, is_busy: Callable[[], bool]) -> bool:
    """Show the app window and block until the user closes it.

    Returns False when no native window can be created (the caller should use the browser).
    """
    try:
        import webview
    except Exception:
        return False

    if sys.platform == "darwin":
        _brand_macos()
    elif sys.platform == "win32":
        _brand_windows()

    try:
        window = webview.create_window(
            TITLE, url, width=1120, height=860, min_size=(760, 560), text_select=True
        )

        def on_closing() -> None:
            # Ask for confirmation only when closing would interrupt work.
            window.confirm_close = is_busy()

        window.events.closing += on_closing
        icon = _WEB / ("icon.ico" if sys.platform == "win32" else "icon.png")
        webview.start(localization=_LOCALIZATION, icon=str(icon), private_mode=True)
    except Exception:
        return False
    return True
