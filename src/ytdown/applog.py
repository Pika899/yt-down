"""Error log for the desktop apps, which have no console: ~/.ytdown/ytdown.log."""

from __future__ import annotations

import time
import traceback
from pathlib import Path

LOG = Path.home() / ".ytdown" / "ytdown.log"


def log_exception(context: str) -> None:
    """Append the current exception's traceback to the log. Never raises."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {context}\n{traceback.format_exc()}\n")
    except OSError:
        pass
