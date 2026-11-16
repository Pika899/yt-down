"""Queue and HTTP API, with yt-dlp replaced by fakes fed from the real fixtures."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest
from conftest import load_text

from ytdown.core import runner
from ytdown.core.jobs import Manager, safe_name
from ytdown.core.models import Choice, ItemState
from ytdown.core.settings import Settings
from ytdown.server import make_server

VIDEO_URL = "https://www.youtube.com/watch?v=1WEAJ-DFkHE"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLWq4AyypkA1vd0W7DKZQqt_HLq_cqviKU"


class FakeDownload:
    """Replays captured yt-dlp output instead of downloading."""

    def __init__(self, lines, returncode=0, gate=None):
        self._lines, self._returncode, self._gate = lines, returncode, gate
        self.returncode = None
        self.cancelled = False

    def lines(self):
        yield from self._lines
        if self._gate is not None:
            self._gate.wait(5)
        self.returncode = -15 if self.cancelled else self._returncode

    def cancel(self):
        self.cancelled = True
        if self._gate is not None:
            self._gate.set()


class Backend:
    def __init__(self, videos, playlist=None):
        self.videos = videos  # video id -> VideoInfo
        self.playlist = playlist
        self.spawned = []
        self.outputs = []  # per-download (lines, returncode); default replays a real success
        self.gate = None
        self.probes = 0

    def probe_video(self, url):
        self.probes += 1
        video_id = url.rsplit("=", 1)[-1]
        if video_id not in self.videos:
            raise runner.YtDlpError(load_text("unavailable.error.txt").strip())
        return self.videos[video_id]

    def expand_playlist(self, source):
        if self.playlist is None:
            raise runner.YtDlpError("The playlist does not exist.")
        return self.playlist

    def spawn(self, args):
        self.spawned.append(args)
        lines, code = (
            self.outputs.pop(0)
            if self.outputs
            else (load_text("download_output.txt").splitlines(), 0)
        )
        return FakeDownload(lines, code, self.gate)


def make_manager(tmp_path, backend):
    return Manager(
        Settings(output_dir=str(tmp_path / "out")),
        probe_video=backend.probe_video,
        expand_playlist=backend.expand_playlist,
        spawn_download=backend.spawn,
    )


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached in time")


def states(manager):
    return [item["state"] for item in manager.snapshot()["items"]]


@pytest.fixture
def backend(multi_audio, low_res, playlist_small):
    videos = {multi_audio.id: multi_audio, low_res.id: low_res}
    return Backend(videos, playlist_small)


# ------------------------------------------------------------------ queue


def test_single_video_flow(tmp_path, backend, multi_audio):
    manager = make_manager(tmp_path, backend)
    assert manager.add(VIDEO_URL) == {"videos": 1, "playlists": 0, "rejected": 0}
    wait_for(lambda: states(manager) == ["ready"])

    snapshot = manager.snapshot()
    assert snapshot["options"]["total"] == 1
    assert snapshot["options"]["multi_language"] is True
    assert snapshot["items"][0]["title"] == multi_audio.title

    assert manager.start(Choice(720, "it")) == 1
    wait_for(lambda: states(manager) == ["done"])

    item = manager.snapshot()["items"][0]
    assert item["progress"] == 1.0
    assert (item["quality"], item["audio_language"], item["container"]) == (720, "it", "mp4")
    assert item["output_path"] == "/downloads/Me at the zoo [jNQXAC9IVRw].mp4"
    args = backend.spawned[0]
    assert args[-1] == VIDEO_URL
    assert args[args.index("-o") + 1].startswith(str(tmp_path / "out"))
    assert manager.snapshot()["options"]["total"] == 0


def test_same_link_twice_is_added_once(tmp_path, backend):
    manager = make_manager(tmp_path, backend)
    manager.add(VIDEO_URL)
    assert manager.add(VIDEO_URL)["videos"] == 0
    assert len(manager.snapshot()["items"]) == 1


def test_playlist_expands_and_failures_do_not_stop_the_batch(tmp_path, backend, playlist_small):
    # Only one playlist entry is known to the backend: the other six fail to analyze.
    known = playlist_small.entries[2].id
    backend.videos[known] = backend.videos["jNQXAC9IVRw"]
    manager = make_manager(tmp_path, backend)

    manager.add(PLAYLIST_URL)
    wait_for(lambda: len(states(manager)) == 7 and "analyzing" not in states(manager))
    assert states(manager).count("failed") == 6
    assert states(manager).count("ready") == 1
    failed = next(i for i in manager.snapshot()["items"] if i["state"] == "failed")
    assert failed["error"] == "This video is unavailable"

    assert manager.start(Choice(None, None)) == 1
    wait_for(lambda: "done" in states(manager))
    template = backend.spawned[0][backend.spawned[0].index("-o") + 1]
    assert f"{safe_name(playlist_small.title)}" in template
    assert "03 - %(title)" in template


def test_unknown_playlist_and_bad_links_become_problems(tmp_path, multi_audio):
    manager = make_manager(tmp_path, Backend({multi_audio.id: multi_audio}, playlist=None))
    result = manager.add(f"{PLAYLIST_URL}\nhttps://vimeo.com/1")
    assert result == {"videos": 0, "playlists": 1, "rejected": 1}
    wait_for(lambda: manager.snapshot()["expanding"] == 0)
    problems = manager.snapshot()["problems"]
    assert {p["input"] for p in problems} == {PLAYLIST_URL, "https://vimeo.com/1"}


def test_failed_download_reports_the_error_and_can_be_retried(tmp_path, backend):
    backend.outputs = [(["ERROR: [youtube] 1WEAJ-DFkHE: HTTP Error 403: Forbidden"], 1)]
    manager = make_manager(tmp_path, backend)
    manager.add(VIDEO_URL)
    wait_for(lambda: states(manager) == ["ready"])
    manager.start(Choice(None, None))
    wait_for(lambda: states(manager) == ["failed"])
    item = manager.snapshot()["items"][0]
    assert item["error"] == "HTTP Error 403: Forbidden"

    assert manager.retry(item["id"])
    wait_for(lambda: states(manager) == ["done"])
    assert manager.snapshot()["items"][0]["error"] is None


def test_changed_format_ids_trigger_one_reprobe(tmp_path, backend):
    gone = "ERROR: [youtube] 1WEAJ-DFkHE: Requested format is not available. Use --list-formats"
    backend.outputs = [([gone], 1)]
    manager = make_manager(tmp_path, backend)
    manager.add(VIDEO_URL)
    wait_for(lambda: states(manager) == ["ready"])
    manager.start(Choice(None, None))
    wait_for(lambda: states(manager) == ["done"])
    assert backend.probes == 2
    assert len(backend.spawned) == 2
    assert any("ricalcolata" in note for note in manager.snapshot()["items"][0]["notes"])


def test_cancel_running_download_then_remove(tmp_path, backend):
    backend.gate = threading.Event()
    manager = make_manager(tmp_path, backend)
    manager.add(VIDEO_URL)
    wait_for(lambda: states(manager) == ["ready"])
    manager.start(Choice(None, None))
    wait_for(lambda: states(manager) == ["merging"])

    item_id = manager.snapshot()["items"][0]["id"]
    assert manager.remove(item_id) is False  # active downloads cannot be removed
    assert manager.cancel(item_id)
    wait_for(lambda: states(manager) == ["cancelled"])
    assert manager.remove(item_id)
    assert manager.snapshot()["items"] == []


def test_cancel_before_choice_and_clear(tmp_path, backend):
    manager = make_manager(tmp_path, backend)
    manager.add(VIDEO_URL)
    wait_for(lambda: states(manager) == ["ready"])
    item_id = manager.snapshot()["items"][0]["id"]
    assert manager.cancel(item_id)
    assert manager.start(Choice(None, None)) == 0
    assert backend.spawned == []
    assert manager.clear_finished() == 1


def test_safe_name():
    assert safe_name('  My: "Play/list"?  ') == "My Play list"
    assert safe_name("...") == "playlist"
    assert safe_name("a" * 300) == "a" * 100
    assert safe_name("ends with dot.") == "ends with dot"


def test_output_template_escapes_percent(tmp_path, backend):
    manager = make_manager(tmp_path / "100% mine", backend)
    manager.add(VIDEO_URL)
    wait_for(lambda: states(manager) == ["ready"])
    manager.start(Choice(None, None))
    wait_for(lambda: states(manager) == ["done"])
    template = backend.spawned[0][backend.spawned[0].index("-o") + 1]
    assert "100%% mine" in template
    assert template.endswith("%(title).150B [%(id)s].%(ext)s")


# -------------------------------------------------------------------- API


@pytest.fixture
def api(tmp_path, backend, monkeypatch):
    monkeypatch.setattr("ytdown.core.settings.SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(Settings, "save", lambda self, path=tmp_path / "settings.json": None)
    manager = make_manager(tmp_path, backend)
    server = make_server(manager, 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def call(path, body=None, headers=None, method=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    call.manager = manager
    call.port = port
    call.server = server
    yield call
    server.shutdown()
    server.server_close()
    manager.shutdown()


def test_api_full_flow(api):
    assert api("/api/ping") == (200, {"app": "ytdown"})
    status, result = api("/api/add", {"text": VIDEO_URL})
    assert (status, result["videos"]) == (200, 1)
    wait_for(lambda: api("/api/state")[1]["options"]["total"] == 1)

    status, state = api("/api/state")
    assert state["tools"]["ytdlp"]
    assert [q for q, _ in state["options"]["qualities"]][0] == 1080

    assert api("/api/start", {"max_quality": 1080, "audio_language": "it"}) == (200, {"started": 1})
    wait_for(lambda: api("/api/state")[1]["items"][0]["state"] == "done")
    assert api("/api/clear", {}) == (200, {"removed": 1})


def test_api_starts_audio_only(api, backend):
    assert api("/api/add", {"text": VIDEO_URL})[0] == 200
    wait_for(lambda: api("/api/state")[1]["options"]["total"] == 1)
    assert api("/api/start", {"max_quality": None, "audio_language": None, "audio_only": True}) == (
        200,
        {"started": 1},
    )
    wait_for(lambda: bool(backend.spawned))
    assert api("/api/state")[1]["items"][0]["container"] == "mp3"
    assert "-x" in backend.spawned[0]


def test_api_serves_the_page(api):
    with urllib.request.urlopen(f"http://127.0.0.1:{api.port}/", timeout=5) as response:
        body = response.read().decode()
    assert response.status == 200
    assert "<title>yt down</title>" in body


def test_api_rejects_bad_input(api):
    assert api("/api/add", {"text": "  "})[0] == 400
    assert api("/api/start", {"max_quality": "1080"})[0] == 400
    assert api("/api/start", {"max_quality": True})[0] == 400
    assert api("/api/start", {"audio_only": "yes"})[0] == 400
    assert api("/api/settings", {"output_dir": "relative/path"})[0] == 400
    assert api("/api/items/999/explode", {})[0] == 404
    assert api("/api/items/999/cancel", {}) == (200, {"ok": False})
    assert api("/api/nope")[0] == 404


def test_api_refuses_other_origins_and_hosts(api):
    assert api("/api/add", {"text": VIDEO_URL}, {"Origin": "https://evil.example"})[0] == 403
    assert api("/api/state", headers={"Host": "evil.example"})[0] == 403
    assert api.manager.snapshot()["items"] == []


def test_api_requires_json_content_type(api):
    request = urllib.request.Request(
        f"http://127.0.0.1:{api.port}/api/add",
        data=b"text=" + VIDEO_URL.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=5)
    assert error.value.code == 400
    assert api.manager.snapshot()["items"] == []


def test_api_changes_the_output_folder(api, tmp_path):
    target = tmp_path / "nuova cartella"
    status, result = api("/api/settings", {"output_dir": str(target)})
    assert (status, result["output_dir"]) == (200, str(target))
    assert target.is_dir()
    assert api("/api/state")[1]["output_dir"] == str(target)


def test_item_state_values_match_the_page():
    page = load_text("../../src/ytdown/web/index.html")
    for state in ItemState:
        assert f"{state.value}:" in page


# ------------------------------------------------- regressions (Codex review)


def test_stale_analysis_cannot_overwrite_a_retry(tmp_path, multi_audio):
    release = threading.Event()
    calls = []

    class SlowBackend(Backend):
        def probe_video(self, url):
            calls.append(url)
            if len(calls) == 1:  # the first, soon-stale analysis blocks, then fails
                release.wait(5)
                raise runner.YtDlpError("stale failure")
            return multi_audio

    backend = SlowBackend({multi_audio.id: multi_audio})
    manager = make_manager(tmp_path, backend)
    manager.add(VIDEO_URL)
    wait_for(lambda: len(calls) == 1)
    item_id = manager.snapshot()["items"][0]["id"]
    assert manager.cancel(item_id)
    assert manager.retry(item_id)
    wait_for(lambda: states(manager) == ["ready"])
    release.set()
    time.sleep(0.2)
    assert states(manager) == ["ready"]
    assert manager.snapshot()["items"][0]["error"] is None


def test_cancelled_queued_item_retried_downloads_once(tmp_path, backend, multi_audio):
    manager = Manager(
        Settings(output_dir=str(tmp_path / "out")),
        probe_video=backend.probe_video,
        expand_playlist=backend.expand_playlist,
        spawn_download=backend.spawn,
        download_workers=1,
    )
    backend.gate = threading.Event()
    manager.add(VIDEO_URL + "\nhttps://www.youtube.com/watch?v=jNQXAC9IVRw")
    wait_for(lambda: states(manager) == ["ready", "ready"])
    manager.start(Choice(None, None))
    wait_for(lambda: "merging" in states(manager) and "queued" in states(manager))
    queued = next(i for i in manager.snapshot()["items"] if i["state"] == "queued")["id"]
    manager.cancel(queued)
    manager.retry(queued)  # its old worker is still waiting in the pool
    backend.gate.set()
    wait_for(lambda: states(manager) == ["done", "done"])
    time.sleep(0.2)
    assert len(backend.spawned) == 2


def test_windows_reserved_names():
    assert safe_name("CON") == "_CON"
    assert safe_name("nul.txt") == "_nul.txt"
    assert safe_name("Console") == "Console"


def test_api_rejects_negative_content_length(api):
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", api.port, timeout=5)
    connection.putrequest("POST", "/api/add")
    connection.putheader("Content-Type", "application/json")
    connection.putheader("Content-Length", "-1")
    connection.endheaders()
    assert connection.getresponse().status == 400


def test_busy_only_while_work_is_running(tmp_path, backend):
    """The app asks before closing only when closing would interrupt something."""
    backend.gate = threading.Event()
    manager = make_manager(tmp_path, backend)
    assert not manager.busy()
    manager.add(VIDEO_URL)
    wait_for(lambda: states(manager) == ["ready"])
    assert not manager.busy()  # waiting for the user's choice: nothing to interrupt
    manager.start(Choice(None, None))
    wait_for(lambda: states(manager) == ["merging"])
    assert manager.busy()
    backend.gate.set()
    wait_for(lambda: states(manager) == ["done"])
    assert not manager.busy()


def test_second_start_focuses_the_open_window(api):
    assert api("/api/focus", {}) == (200, {"focused": False})  # browser mode: no window
    calls = []
    api.server.focus_window = lambda: calls.append(1)
    assert api("/api/focus", {}) == (200, {"focused": True})
    assert calls == [1]
