import pytest

from ytdown.core import options, probe, selection
from ytdown.core.models import Choice, VideoInfo, lang_key


def ids(video: VideoInfo, spec: str):
    video_id, audio_id = spec.split("+")
    stream = next(s for s in video.video_streams if s.format_id == video_id)
    track = next(t for t in video.audio_tracks if t.format_id == audio_id)
    return stream, track


# ------------------------------------------------------------------ probe


def test_multi_audio_probe(multi_audio):
    assert multi_audio.id == "1WEAJ-DFkHE"
    assert {s.quality for s in multi_audio.video_streams} == {144, 240, 360, 480, 720, 1080}
    languages = {lang_key(t.language) for t in multi_audio.audio_tracks}
    assert {"en", "it", "es", "fr", "de", "ja"} <= languages
    assert {lang_key(t.language) for t in multi_audio.audio_tracks if t.is_original} == {"en"}
    assert not any(t.format_id.endswith("-drc") for t in multi_audio.audio_tracks)


def test_single_language_tracks_are_all_original(low_res):
    assert low_res.audio_tracks
    assert all(t.is_original for t in low_res.audio_tracks)


def test_playlist_probe(playlist_small):
    assert playlist_small.id == "PLWq4AyypkA1vd0W7DKZQqt_HLq_cqviKU"
    assert len(playlist_small.entries) == 7
    assert all(len(e.id) == 11 for e in playlist_small.entries)


def test_playlist_skips_empty_entries():
    playlist = probe.parse_playlist({"id": "PLx", "title": "t", "entries": [None, {}, {"id": "a"}]})
    assert [e.id for e in playlist.entries] == ["a"]


# -------------------------------------------------------------- selection


def test_best_quality_original_audio(multi_audio):
    resolved = selection.resolve(multi_audio, Choice(None, None))
    stream, track = ids(multi_audio, resolved.format_spec)
    assert (resolved.quality, resolved.container, resolved.notes) == (1080, "mp4", ())
    assert stream.vcodec.startswith("avc1") and stream.direct
    assert track.is_original and track.acodec.startswith("mp4a")
    assert resolved.est_size == stream.size + track.size


def test_requested_language_is_used(multi_audio):
    resolved = selection.resolve(multi_audio, Choice(720, "it"))
    _, track = ids(multi_audio, resolved.format_spec)
    assert resolved.quality == 720
    assert lang_key(track.language) == "it" and not track.is_original
    assert resolved.notes == ()


def test_language_matches_on_primary_subtag(multi_audio):
    resolved = selection.resolve(multi_audio, Choice(None, "IT-it"))
    assert lang_key(resolved.audio_language) == "it"


def test_quality_is_a_ceiling(multi_audio):
    resolved = selection.resolve(multi_audio, Choice(2160, None))
    assert resolved.quality == 1080
    assert resolved.notes == ("2160p non disponibile: scaricato a 1080p.",)


def test_fallbacks_are_reported(low_res):
    resolved = selection.resolve(low_res, Choice(1080, "it"))
    assert resolved.quality == 240
    assert len(resolved.notes) == 2
    assert "1080p non disponibile" in resolved.notes[0]
    assert "«it» non disponibile" in resolved.notes[1]


def test_ceiling_below_everything_takes_the_lowest(multi_audio):
    resolved = selection.resolve(multi_audio, Choice(100, None))
    assert resolved.quality == 144
    assert resolved.notes


def test_uhd_goes_to_mkv_and_avoids_hdr(uhd_hdr):
    resolved = selection.resolve(uhd_hdr, Choice(None, None))
    stream, _ = ids(uhd_hdr, resolved.format_spec)
    assert (resolved.quality, resolved.container) == (2160, "mkv")
    assert not stream.hdr and stream.direct
    assert stream.fps == 60


def test_uhd_video_at_1080_stays_mp4(uhd_hdr):
    resolved = selection.resolve(uhd_hdr, Choice(1080, None))
    stream, track = ids(uhd_hdr, resolved.format_spec)
    assert (resolved.quality, resolved.container) == (1080, "mp4")
    assert stream.vcodec.startswith("avc1") and track.acodec.startswith("mp4a")


def test_missing_streams_raise(low_res):
    from dataclasses import replace

    with pytest.raises(selection.SelectionError):
        selection.resolve(replace(low_res, video_streams=()), Choice(None, None))
    with pytest.raises(selection.SelectionError):
        selection.resolve(replace(low_res, audio_tracks=()), Choice(None, None))


# ---------------------------------------------------------------- options


def test_aggregate_counts_videos_per_option(multi_audio, low_res, uhd_hdr):
    result = options.aggregate([multi_audio, low_res, uhd_hdr])
    qualities = dict(result.qualities)
    assert result.total == 3
    assert qualities[2160] == 1 and qualities[1080] == 2 and qualities[240] == 3
    assert [q for q, _ in result.qualities] == sorted(qualities, reverse=True)
    assert result.multi_language
    assert dict(result.languages)["it"] == 1


def test_no_language_question_for_single_language_videos(low_res, uhd_hdr):
    assert not options.aggregate([low_res, uhd_hdr]).multi_language
    assert options.aggregate([]).total == 0
