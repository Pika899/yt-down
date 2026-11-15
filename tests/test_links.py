import pytest

from ytdown.core import links
from ytdown.core.models import SourceKind

VIDEO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
PLAYLIST = "https://www.youtube.com/playlist?list=PLWq4AyypkA1vd0W7DKZQqt_HLq_cqviKU"


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "http://youtube.com/watch?v=jNQXAC9IVRw&t=10s",
        "https://m.youtube.com/watch?v=jNQXAC9IVRw",
        "https://music.youtube.com/watch?v=jNQXAC9IVRw",
        "https://youtu.be/jNQXAC9IVRw?si=abc",
        "youtu.be/jNQXAC9IVRw",
        "https://www.youtube.com/shorts/jNQXAC9IVRw",
        "https://www.youtube.com/embed/jNQXAC9IVRw",
        "https://www.youtube.com/live/jNQXAC9IVRw",
    ],
)
def test_video_links_normalize_to_one_url(raw):
    source = links.classify(raw)
    assert source is not None
    assert (source.kind, source.id, source.url) == (SourceKind.VIDEO, "jNQXAC9IVRw", VIDEO)


def test_playlist_link():
    source = links.classify(PLAYLIST)
    assert source is not None
    assert source.kind is SourceKind.PLAYLIST
    assert source.url == PLAYLIST


def test_watch_link_with_list_is_a_single_video():
    source = links.classify(VIDEO + "&list=PLWq4AyypkA1vd0W7DKZQqt_HLq_cqviKU&index=3")
    assert source is not None
    assert source.kind is SourceKind.VIDEO


@pytest.mark.parametrize(
    "raw",
    [
        "https://vimeo.com/12345",
        "https://www.youtube.com/@somechannel",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/playlist",
        "https://evil.example/youtube.com/watch?v=jNQXAC9IVRw",
    ],
)
def test_unsupported_links_are_rejected(raw):
    assert links.classify(raw) is None


def test_parse_mixed_text_dedups_and_reports_rejected():
    text = f"""
        guarda questo: {VIDEO}
        {PLAYLIST}, https://youtu.be/jNQXAC9IVRw
        https://vimeo.com/12345
        parole a caso senza link
    """
    sources, rejected = links.parse(text)
    assert [(s.kind, s.id) for s in sources] == [
        (SourceKind.VIDEO, "jNQXAC9IVRw"),
        (SourceKind.PLAYLIST, "PLWq4AyypkA1vd0W7DKZQqt_HLq_cqviKU"),
    ]
    assert rejected == ["https://vimeo.com/12345"]


def test_parse_empty_text():
    assert links.parse("   \n ") == ([], [])
