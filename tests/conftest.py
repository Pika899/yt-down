"""Fixtures are real yt-dlp output captured with `python -m ytdown.capture` (no network here)."""

import json
from pathlib import Path

import pytest

from ytdown.core import probe

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def multi_audio():
    """1080p video with 25 audio languages; the original track is English."""
    return probe.parse_video(load_json("multi_audio"))


@pytest.fixture(scope="session")
def low_res():
    """Single-language video whose best quality is 240p."""
    return probe.parse_video(load_json("low_res"))


@pytest.fixture(scope="session")
def uhd_hdr():
    """2160p60 video with HDR variants and no H.264 above 1080p."""
    return probe.parse_video(load_json("uhd_hdr"))


@pytest.fixture(scope="session")
def playlist_small():
    return probe.parse_playlist(load_json("playlist_small"))
