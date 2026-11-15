"""Capture real yt-dlp metadata as a test fixture.

    uv run python -m ytdown.capture <url> <name> [--flat]

Writes tests/fixtures/<name>.json using the same yt-dlp options as the app. Signed
stream URLs and bulky fields the app never reads are removed. When yt-dlp fails, its
error message is saved to tests/fixtures/<name>.error.txt instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import runner

_FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
_DROP_TOP = {
    "automatic_captions",
    "subtitles",
    "thumbnails",
    "heatmap",
    "chapters",
    "description",
    "tags",
    "categories",
    "requested_formats",
    "requested_downloads",
    "http_headers",
    "_version",
}
_DROP_FORMAT = {
    "url",
    "manifest_url",
    "fragment_base_url",
    "fragments",
    "http_headers",
    "cookies",
    "downloader_options",
}


def scrub(data: dict) -> dict:
    out = {k: v for k, v in data.items() if k not in _DROP_TOP}
    if isinstance(out.get("formats"), list):
        out["formats"] = [
            {k: v for k, v in fmt.items() if k not in _DROP_FORMAT} for fmt in out["formats"]
        ]
    if isinstance(out.get("entries"), list):
        out["entries"] = [
            {k: v for k, v in entry.items() if k != "thumbnails"} if entry else entry
            for entry in out["entries"]
        ]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("name")
    parser.add_argument("--flat", action="store_true", help="playlist fixture (--flat-playlist)")
    args = parser.parse_args()

    _FIXTURES.mkdir(parents=True, exist_ok=True)
    mode = ["--flat-playlist"] if args.flat else ["--no-playlist"]
    try:
        data = runner.run_json(["-J", *mode, args.url], timeout=600)
    except runner.YtDlpError as exc:
        path = _FIXTURES / f"{args.name}.error.txt"
        path.write_text(str(exc) + "\n", encoding="utf-8")
        print(f"yt-dlp failed; saved message to {path}", file=sys.stderr)
        return 1

    path = _FIXTURES / f"{args.name}.json"
    path.write_text(json.dumps(scrub(data), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
