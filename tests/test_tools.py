import sys
from pathlib import Path

from ytdown.core import tools


def test_console_python_replaces_pythonw(tmp_path, monkeypatch):
    (tmp_path / "pythonw.exe").write_text("")
    (tmp_path / "python.exe").write_text("")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "pythonw.exe"))
    assert tools.python_executable() == str(tmp_path / "python.exe")


def test_regular_python_is_kept(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")
    assert tools.python_executable() == "/venv/bin/python"


def test_uv_from_env_then_installer_layout(tmp_path, monkeypatch):
    env_uv = tmp_path / "custom" / "uv"
    env_uv.parent.mkdir()
    env_uv.write_text("")
    monkeypatch.setenv("YTDOWN_UV", str(env_uv))
    assert tools.uv_path() == str(env_uv)

    # Windows installer layout: <app>\.venv is sys.prefix, uv.exe is in <app>\bin.
    monkeypatch.delenv("YTDOWN_UV")
    app = tmp_path / "app"
    (app / "bin").mkdir(parents=True)
    (app / "bin" / "uv.exe").write_text("")
    monkeypatch.setattr(sys, "prefix", str(app / ".venv"))
    assert Path(tools.uv_path()) == app / "bin" / "uv.exe"


def test_without_uv_no_update_and_yt_dlp_is_not_blocked(monkeypatch):
    monkeypatch.setattr(tools, "uv_path", lambda: None)
    assert tools.start_ytdlp_update() is None
    tools.wait_until_ready()  # returns at once
