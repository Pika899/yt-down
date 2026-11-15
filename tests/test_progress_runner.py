from conftest import load_text

from ytdown.core import progress, runner


def events(name: str):
    return [progress.parse_line(line) for line in load_text(name).splitlines()]


def test_real_download_output_is_fully_parsed():
    parsed = events("download_output.txt")
    assert None not in parsed

    downloads = [e for e in parsed if isinstance(e, progress.DownloadProgress)]
    files = list(dict.fromkeys(e.filename for e in downloads))
    assert len(files) == 2  # video stream, then audio stream
    assert all(e.total for e in downloads)
    assert downloads[-1].finished

    post = [(e.name, e.status) for e in parsed if isinstance(e, progress.PostProcess)]
    assert ("Merger", "started") in post

    final = [e for e in parsed if isinstance(e, progress.FinalFile)]
    assert len(final) == 1
    assert final[0].path == "/downloads/Me at the zoo [jNQXAC9IVRw].mp4"


def test_already_downloaded_file_still_reports_its_path():
    parsed = events("download_output_existing.txt")
    assert not any(isinstance(e, progress.DownloadProgress) for e in parsed)
    assert [e.path for e in parsed if isinstance(e, progress.FinalFile)] == [
        "/downloads/Me at the zoo [jNQXAC9IVRw].mp4"
    ]


def test_unrelated_and_broken_lines_are_ignored():
    assert progress.parse_line("[youtube] Extracting URL") is None
    assert progress.parse_line(progress.DL_PREFIX + "{not json") is None
    assert progress.parse_line("") is None


def test_error_line_is_cleaned():
    line = "ERROR: [youtube] aaaaaaaaaaa: " + load_text("unavailable.error.txt").strip()
    event = progress.parse_line(line)
    assert isinstance(event, progress.ErrorLine)
    assert event.message == "This video is unavailable"


def test_extract_error_takes_the_last_error():
    output = (
        "WARNING: something\nERROR: first\n[info] noise\nERROR: [youtube] abcdefghijk: second\n"
    )
    assert runner.extract_error(output) == "second"
    assert runner.extract_error("no errors here") is None


def test_download_args_keep_the_url_last_and_template_literal():
    args = progress.download_args("137+140", "mp4", "/out/%(title)s.%(ext)s", "https://x/watch?v=1")
    assert args[-1] == "https://x/watch?v=1"
    assert args[args.index("-f") + 1] == "137+140"
    assert args[args.index("-o") + 1] == "/out/%(title)s.%(ext)s"
    assert "--no-playlist" in args


def test_malformed_numbers_are_tolerated():
    line = progress.DL_PREFIX + '{"downloaded_bytes": "lots", "total_bytes": "NA", "speed": "x"}'
    event = progress.parse_line(line)
    assert isinstance(event, progress.DownloadProgress)
    assert (event.downloaded, event.total, event.speed) == (0, None, None)
