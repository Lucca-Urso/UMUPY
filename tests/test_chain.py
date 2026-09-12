import os
from types import SimpleNamespace

import history
import yt_downloader
from api import chain


def test_safe_folder_name_and_default_folder(project_dir):
    assert chain.safe_folder_name('  Mix: "Best/Of" 2026?  ') == "Mix Best Of 2026"
    assert chain.safe_folder_name("") == "Playlist"
    assert chain.safe_folder_name("x" * 100) == "x" * 80
    assert chain.default_sync_folder("Test Playlist") == str(project_dir / "Downloads" / "Test Playlist")


def test_start_chain_creates_folder_from_playlist_name(api, project_dir, monkeypatch, spotify_env):
    spotify_env(tracks=[{"spotify_id": "s1", "title": "Zzz", "artists": ["A"], "duration": 1}], local_files=[])

    api.start_chain("https://open.spotify.com/playlist/abc")
    status = api.get_chain_status()

    assert status["stage"] == "analyzing"
    assert status["sync"]["folder"] == str(project_dir / "Downloads" / "Mix")
    assert os.path.isdir(project_dir / "Downloads" / "Mix")
    assert [m["title"] for m in status["sync"]["missing"]] == ["Zzz"]


def test_start_chain_with_explicit_folder(api, project_dir, spotify_env, tmp_path):
    spotify_env(tracks=[{"spotify_id": "s1", "title": "Zzz", "artists": ["A"], "duration": 1}], local_files=[])
    folder = tmp_path / "custom"
    folder.mkdir()

    api.start_chain(["https://open.spotify.com/playlist/abc"], str(folder))

    assert api.get_sync_status()["folder"] == str(folder)
    assert api.get_sync_status()["error"] is None


def test_sync_without_folder_or_factory_fails(api, project_dir, spotify_env):
    spotify_env(tracks=[{"spotify_id": "s1", "title": "Zzz", "artists": ["A"], "duration": 1}], local_files=[])

    api.start_sync_analysis("https://open.spotify.com/playlist/abc")

    assert api.get_sync_status()["error"] == "Choose a folder to sync into."


def test_chain_download_requires_analysis(api):
    assert api.start_chain_download([{"id": "v"}]) == {"error": "Run the analysis first."}


def test_chain_download_then_rekordbox_plan(api, project_dir, monkeypatch, tmp_path):
    folder = tmp_path / "Mix"
    folder.mkdir()
    api._sync.update(folder=str(folder), playlist="Mix")
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(yt_downloader, "download_video", lambda *a, **k: (0, None))
    plan = {"playlist": "Mix", "exists": False, "folder": str(folder), "running": False, "add": [], "keep": 0, "remove": []}
    monkeypatch.setattr(api, "rekordbox_sync_plan", lambda f, name: {**plan, "folder": f, "playlist": name})

    assert api.start_chain_download([{"id": "v1", "title": "Song", "url": "u", "source": "youtube"}]) == str(folder)
    status = api.get_chain_status()

    assert status["running"] is False
    assert status["stage"] == "review"
    assert status["rekordbox"]["folder"] == str(folder)
    assert status["rekordbox"]["playlist"] == "Mix"
    assert status["download"]["items"][0]["ok"] is True
    assert status["download"]["running"] is False
    run = history.list_runs()[0]
    assert run["operation"] == "sync_download"
    assert run["target"] == "Mix"


def test_chain_download_without_rekordbox_and_without_videos(api, project_dir, tmp_path):
    api._sync.update(folder=str(tmp_path), playlist=None)

    api.start_chain_download([], rekordbox=False)
    status = api.get_chain_status()

    assert status["stage"] == "review"
    assert status["rekordbox"] is None
    assert history.list_runs() == []


def test_chain_reports_rekordbox_plan_error(api, project_dir, monkeypatch, tmp_path):
    api._sync.update(folder=str(tmp_path), playlist="Mix")
    monkeypatch.setattr(api, "rekordbox_sync_plan", lambda f, name: (_ for _ in ()).throw(RuntimeError("db locked")))

    api.start_chain_download([])
    status = api.get_chain_status()

    assert status["error"] == "db locked"
    assert status["stage"] == "planning"
    assert history.list_runs()[0]["status"] == "failed"
