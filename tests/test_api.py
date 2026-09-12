import os
import platform
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

import app
import history
import spotify_converter
import sync_playlists
import yt_downloader
from app import UmupyApi


class SyncThread:
    def __init__(self, target, args=(), daemon=None):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def api(project_dir, monkeypatch):
    monkeypatch.setattr(threading, "Thread", SyncThread)
    return UmupyApi()


VIDEO = {"id": "v1", "title": "Song", "url": "https://youtube/v1"}


def test_scan_paths_and_index(api, project_dir, monkeypatch):
    downloads = str(project_dir / "Downloads")
    assert api._scan_paths(None) == [downloads]
    assert api._scan_paths(["__all__", "x"]) == [downloads]
    assert api._scan_paths(["A"]) == [os.path.join(downloads, "A")]

    assert api._build_scan_index(None) == {}
    monkeypatch.setattr(yt_downloader, "build_library_index", lambda paths: {"paths": paths})
    assert api._build_scan_index(["A"]) == {"paths": [os.path.join(downloads, "A")]}


def test_list_download_folders(api, project_dir):
    (project_dir / "Downloads" / "B").mkdir(parents=True)
    (project_dir / "Downloads" / "A").mkdir()
    (project_dir / "Downloads" / "file.mp3").write_bytes(b"")

    assert api.list_download_folders() == ["A", "B"]


def test_analyze_url_marks_duplicates(api, monkeypatch):
    monkeypatch.setattr(yt_downloader, "detect_playlist", lambda *_: "Mix")
    monkeypatch.setattr(yt_downloader, "extract_videos", lambda *_: [dict(VIDEO), {**VIDEO, "id": "v2"}])
    monkeypatch.setattr(yt_downloader, "build_library_index", lambda _: {"v2": "p"})
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")

    result = api.analyze_url("url", ["__all__"])

    assert result["playlist"] == "Mix"
    assert [v["duplicate"] for v in result["videos"]] == [False, True]
    assert result["error"] is None
    assert result["ffmpeg"] is True


def test_analyze_url_reports_probe_error(api, monkeypatch):
    monkeypatch.setattr(yt_downloader, "detect_playlist", lambda *_: "")
    monkeypatch.setattr(yt_downloader, "extract_videos", lambda *_: [])
    monkeypatch.setattr(yt_downloader, "probe_url_error", lambda *_: "bad")
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: None)

    result = api.analyze_url("url")

    assert result == {"playlist": None, "videos": [], "error": "bad", "ffmpeg": False}


def test_start_download_directories(api, project_dir, monkeypatch):
    monkeypatch.setattr(api, "_download_worker", lambda *_: None)
    monkeypatch.setattr(yt_downloader, "get_today", lambda: "01_01")

    assert api.start_download([VIDEO]) == str(project_dir / "Downloads")
    assert api.start_download([VIDEO], playlist_name="Mix") == str(project_dir / "Downloads" / "Mix_01_01")
    custom = str(project_dir / "custom")
    assert api.start_download([VIDEO], output_directory=custom) == custom
    assert os.path.isdir(custom)
    assert api.get_status()["total"] == 1


def test_download_worker_records_results(api, project_dir, monkeypatch):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(
        yt_downloader, "download_video",
        lambda video, *a, **k: (0, None) if video["id"] == "v1" else (1, "ERROR: nope"),
    )

    api.start_download([VIDEO, {**VIDEO, "id": "v2", "title": "Bad"}], operation="spotify")
    status = api.get_status()

    assert status["running"] is False
    assert status["current"] is None
    assert [item["ok"] for item in status["items"]] == [True, False]
    assert status["items"][1]["error"] == "ERROR: nope"
    runs = history.list_runs()
    assert runs[0]["operation"] == "spotify_download"
    assert runs[0]["status"] == "completed_with_errors"


def test_download_worker_unknown_operation_label(api, project_dir, monkeypatch):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(yt_downloader, "download_video", lambda *a, **k: (0, None))

    api.start_download([VIDEO], operation="other")

    assert history.list_runs()[0]["operation"] == "youtube_download"
    assert history.list_runs()[0]["status"] == "completed"


@pytest.mark.parametrize("system,expected", [("Darwin", ["open"]), ("Linux", ["xdg-open"])])
def test_open_output_directory_unix(api, project_dir, monkeypatch, system, expected):
    calls = []
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(subprocess, "run", lambda command: calls.append(command))

    directory = api.open_output_directory()

    assert directory == str(project_dir / "Downloads")
    assert calls == [expected + [directory]]


def test_open_output_directory_windows(api, monkeypatch):
    opened = []
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(os, "startfile", lambda path: opened.append(path), raising=False)
    api._status["output_directory"] = "/out"

    assert api.open_output_directory() == "/out"
    assert opened == ["/out"]


def test_spotify_ready(api, project_dir):
    assert api.spotify_ready()["ready"] is False

    (project_dir / "Dependencies").mkdir()
    (project_dir / "Dependencies" / "spotify_credentials.json").write_text("{}")

    assert api.spotify_ready()["ready"] is True


def spotify_track(spotify_id, title="Song"):
    return {"spotify_id": spotify_id, "title": title, "artists": ["Artist"], "duration": 200}


def prepare_spotify(monkeypatch, tracks, searcher):
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: "spotify")
    monkeypatch.setattr(spotify_converter, "fetch_playlist", lambda *_: {"name": "Mix", "tracks": tracks})
    monkeypatch.setattr(spotify_converter, "open_ytmusic", lambda: "yt")
    monkeypatch.setattr(spotify_converter, "search_youtube_equivalent", searcher)


def test_spotify_worker_matches_and_marks_duplicates(api, project_dir, monkeypatch):
    videos = {
        "s1": {"id": "yt1", "title": "A", "url": "u"},
        "s2": None,
        "s3": {"id": "yt3", "title": "C", "url": "u"},
    }
    prepare_spotify(monkeypatch, [spotify_track(s) for s in videos], lambda _, t: videos[t["spotify_id"]])
    monkeypatch.setattr(yt_downloader, "build_library_index", lambda _: {"yt1": "p"})
    monkeypatch.setattr(spotify_converter, "build_spotify_index", lambda _: {"s3": "p"})

    api.start_spotify_analysis("url", ["__all__"])
    status = api.get_spotify_status()

    assert status["running"] is False
    assert status["playlist"] == "Mix"
    assert status["processed"] == 3
    assert [v["duplicate"] for v in status["matched"]] == [True, True]
    assert status["matched"][0]["source"] == {"title": "Song", "artists": ["Artist"]}
    assert len(status["unmatched"]) == 1
    assert history.list_runs()[0]["status"] == "completed"


def test_spotify_worker_search_errors_and_abort(api, project_dir, monkeypatch):
    def searcher(_, track):
        raise ConnectionError("down")

    prepare_spotify(monkeypatch, [spotify_track(str(i)) for i in range(3)], searcher)
    monkeypatch.setattr(spotify_converter, "MAX_CONSECUTIVE_FAILURES", 2)

    api.start_spotify_analysis("url")
    status = api.get_spotify_status()

    assert "Network failed 2 times" in status["error"]
    assert len(status["unmatched"]) == 2
    assert history.list_runs()[0]["status"] == "failed"


def test_spotify_worker_single_search_error_continues(api, project_dir, monkeypatch):
    calls = []

    def searcher(_, track):
        calls.append(track["spotify_id"])

        if track["spotify_id"] == "0":
            raise ConnectionError("blip")

        return {"id": "yt", "title": "T", "url": "u"}

    prepare_spotify(monkeypatch, [spotify_track("0"), spotify_track("1")], searcher)

    api.start_spotify_analysis("url")
    status = api.get_spotify_status()

    assert status["error"] is None
    assert len(status["matched"]) == 1
    assert len(status["unmatched"]) == 1


def test_spotify_worker_credentials_missing(api, project_dir, monkeypatch):
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: (_ for _ in ()).throw(SystemExit(1)))

    api.start_spotify_analysis("url")

    assert api.get_spotify_status()["error"] == "Spotify credentials not found or invalid."
    assert history.list_runs() == []


def test_spotify_worker_credentials_missing_after_run_started(api, project_dir, monkeypatch):
    def searcher(*_):
        raise SystemExit(1)

    prepare_spotify(monkeypatch, [spotify_track("0")], lambda *_: None)
    monkeypatch.setattr(spotify_converter, "open_ytmusic", searcher)

    api.start_spotify_analysis("url")

    assert history.list_runs()[0]["status"] == "failed"


def test_spotify_worker_generic_error_before_run(api, project_dir, monkeypatch):
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: (_ for _ in ()).throw(RuntimeError("bad url")))

    api.start_spotify_analysis("url")

    assert api.get_spotify_status()["error"] == "bad url"
    run = history.list_runs()[0]
    assert run["status"] == "failed"
    assert run["target"] == "url"


def fake_webview(monkeypatch, result):
    window = SimpleNamespace(create_file_dialog=lambda *a, **k: result)
    module = SimpleNamespace(windows=[window], FOLDER_DIALOG="folder", OPEN_DIALOG="open")
    monkeypatch.setitem(sys.modules, "webview", module)


def test_file_dialogs(api, monkeypatch):
    fake_webview(monkeypatch, ["/picked"])
    assert api.rekordbox_select_source("folder") == "/picked"
    assert api.rekordbox_select_source("file") == "/picked"
    assert api.select_folder() == "/picked"

    fake_webview(monkeypatch, "/single")
    assert api.select_folder() == "/single"
    assert api.rekordbox_select_source("file") == "/single"

    fake_webview(monkeypatch, None)
    assert api.select_folder() is None
    assert api.rekordbox_select_source("file") is None


class FakeContent:
    def __init__(self, title):
        self.Title = title
        self.Artist = None


class FakeDB:
    def __init__(self, collection, names=()):
        self.collection = collection
        self.names = names
        self.closed = False

    def get_content(self):
        return iter(self.collection)

    def get_playlist(self):
        return iter(SimpleNamespace(Name=n) for n in self.names)

    def close(self):
        self.closed = True


def prepare_rekordbox(monkeypatch, db, running=False):
    import rekordbox_playlist_creator as rpc

    monkeypatch.setattr(rpc, "open_database", lambda: db)
    monkeypatch.setattr(rpc, "rekordbox_is_running", lambda: running)
    monkeypatch.setattr(
        rpc, "load_playlists_from_source",
        lambda _: [
            {"name": "New", "tracks": [{"title": "Alpha", "artist": ""}, {"title": "Zzz", "artist": ""}]},
            {"name": "Old", "tracks": [{"title": "Alpha", "artist": ""}]},
        ],
    )
    monkeypatch.setattr(rpc, "create_playlists", lambda db, results: len([r for r in results if not r["exists"]]))


def test_rekordbox_analyze_no_playlists(api, monkeypatch):
    import rekordbox_playlist_creator as rpc

    monkeypatch.setattr(rpc, "load_playlists_from_source", lambda _: [])

    assert api.rekordbox_analyze("/x") == {"error": "No playlists found in the selected source."}


def test_rekordbox_analyze_and_create(api, project_dir, monkeypatch):
    first_db = FakeDB([FakeContent("Alpha")], names=["Old"])
    prepare_rekordbox(monkeypatch, first_db)

    result = api.rekordbox_analyze("/source")

    assert result["collection"] == 1
    assert result["running"] is False
    assert result["playlists"][0]["name"] == "New"
    assert result["playlists"][0]["matched"] == [{"title": "Alpha", "artist": ""}]
    assert result["playlists"][0]["unmatched"] == [{"title": "Zzz", "artist": ""}]
    assert result["playlists"][1]["exists"] is True

    second_db = FakeDB([FakeContent("Alpha")], names=["Old"])
    prepare_rekordbox(monkeypatch, second_db)
    api.rekordbox_analyze("/source")
    assert first_db.closed is True

    created = api.rekordbox_create(["New", "Old"])

    assert created == {"created": 1}
    detail = history.get_run(history.list_runs()[0]["id"])
    statuses = {item["title"]: item["status"] for item in detail["items"]}
    assert statuses == {"New": "ok", "Old": "skipped"}


def test_rekordbox_analyze_close_failure_is_ignored(api, monkeypatch):
    class Exploding(FakeDB):
        def close(self):
            raise RuntimeError("boom")

    prepare_rekordbox(monkeypatch, Exploding([FakeContent("Alpha")]))
    api.rekordbox_analyze("/source")
    api.rekordbox_analyze("/source")


def test_rekordbox_create_skips_existing_and_empty(api, project_dir, monkeypatch):
    import rekordbox_playlist_creator as rpc

    prepare_rekordbox(monkeypatch, FakeDB([], names=["Old"]))
    api.rekordbox_analyze("/source")
    monkeypatch.setattr(rpc, "create_playlists", lambda db, results: 0)

    api.rekordbox_create(["New", "Old"])

    detail = history.get_run(history.list_runs()[0]["id"])
    assert all(item["status"] == "skipped" for item in detail["items"])


def test_rekordbox_create_guards(api, monkeypatch):
    assert api.rekordbox_create(["x"]) == {"error": "Nothing analyzed yet."}

    prepare_rekordbox(monkeypatch, FakeDB([FakeContent("Alpha")]), running=True)
    api.rekordbox_analyze("/source")

    assert "RekordBox is running" in api.rekordbox_create(["New"])["error"]


def test_history_passthrough(api, project_dir):
    run_id = history.start_run("youtube_download", target="x")

    assert api.history_list()[0]["id"] == run_id
    assert api.history_get(run_id)["run"]["id"] == run_id


def local_file(name, spotify_id=None, youtube_id=None):
    return {"path": f"/music/{name}.mp3", "filename": name, "title": "", "artist": "", "spotify_id": spotify_id, "youtube_id": youtube_id}


def prepare_sync(monkeypatch, tracks, local_files, searcher):
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: "spotify")
    monkeypatch.setattr(spotify_converter, "fetch_playlist", lambda *_: {"name": "Mix", "tracks": tracks})
    monkeypatch.setattr(spotify_converter, "open_ytmusic", lambda: "yt")
    monkeypatch.setattr(spotify_converter, "search_youtube_equivalent", searcher)
    monkeypatch.setattr(sync_playlists, "build_local_index", lambda _: local_files)
    monkeypatch.setattr(sync_playlists, "heal_spotify_ids", lambda pairs: 1)
    monkeypatch.setattr(sync_playlists, "embed_spotify_id", lambda *_: (_ for _ in ()).throw(OSError("ro")))


def test_sync_worker_full_flow(api, project_dir, monkeypatch):
    tracks = [spotify_track("s1", "In Sync"), spotify_track("s2", "Xylophone Dream"),
              spotify_track("s3", "Quantum Echo"), spotify_track("s4", "Nowhere Found")]
    local_files = [local_file("insync", spotify_id="s1"), local_file("oldname", youtube_id="ytQ"), local_file("orphan")]
    videos = {"s2": {"id": "ytX", "title": "X", "url": "ux"}, "s3": {"id": "ytQ", "title": "Q", "url": "uq"}, "s4": None}
    prepare_sync(monkeypatch, tracks, local_files, lambda _, t: videos[t["spotify_id"]])

    api.start_sync_analysis("url", "/music")
    status = api.get_sync_status()

    assert status["error"] is None
    assert status["playlist"] == "Mix"
    assert status["folder"] == "/music"
    assert status["in_sync"] == 2
    assert status["processed"] == 3
    assert [m["spotify_id"] for m in status["missing"]] == ["s2", "s4"]
    assert status["missing"][1]["video"] is None
    assert [o["filename"] for o in status["orphans"]] == ["orphan"]
    detail = history.get_run(history.list_runs()[0]["id"])
    statuses = [item["status"] for item in detail["items"]]
    assert statuses == ["ok", "ok", "missing", "not_found", "orphan"]


def test_sync_worker_search_failure_abort(api, project_dir, monkeypatch):
    def searcher(*_):
        raise ConnectionError("down")

    prepare_sync(monkeypatch, [spotify_track("s1", "Aaa"), spotify_track("s2", "Bbb")], [], searcher)
    monkeypatch.setattr(spotify_converter, "MAX_CONSECUTIVE_FAILURES", 2)

    api.start_sync_analysis("url", "/music")

    assert "Network failed 2 times" in api.get_sync_status()["error"]
    assert history.list_runs()[0]["status"] == "failed"


def test_sync_worker_single_failure_continues(api, project_dir, monkeypatch):
    calls = []

    def searcher(_, track):
        calls.append(track["spotify_id"])

        if len(calls) == 1:
            raise ConnectionError("blip")

        return None

    prepare_sync(monkeypatch, [spotify_track("s1", "Aaa"), spotify_track("s2", "Bbb")], [], searcher)

    api.start_sync_analysis("url", "/music")
    status = api.get_sync_status()

    assert status["error"] is None
    assert len(status["missing"]) == 2


def test_sync_worker_credentials_missing(api, project_dir, monkeypatch):
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: (_ for _ in ()).throw(SystemExit(1)))

    api.start_sync_analysis("url", "/music")

    assert api.get_sync_status()["error"] == "Spotify credentials not found or invalid."


def test_sync_worker_credentials_missing_after_run(api, project_dir, monkeypatch):
    prepare_sync(monkeypatch, [spotify_track("s1", "Aaa")], [], lambda *_: None)
    monkeypatch.setattr(spotify_converter, "open_ytmusic", lambda: (_ for _ in ()).throw(SystemExit(1)))

    api.start_sync_analysis("url", "/music")

    assert history.list_runs()[0]["status"] == "failed"


def test_sync_worker_generic_error(api, project_dir, monkeypatch):
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: (_ for _ in ()).throw(RuntimeError("oops")))

    api.start_sync_analysis("url", "/music")

    assert api.get_sync_status()["error"] == "oops"
    assert history.list_runs()[0]["target"] == "url"


def test_sync_delete(api, project_dir, tmp_path):
    folder = tmp_path / "synced"
    folder.mkdir()
    existing = folder / "a.mp3"
    existing.write_bytes(b"")
    outside = tmp_path / "outside.mp3"
    outside.write_bytes(b"")
    api._sync_status["folder"] = str(folder)

    results = api.sync_delete([str(existing), str(folder / "missing.mp3"), str(outside)])

    assert [r["ok"] for r in results] == [True, False, False]
    assert outside.exists()
    run = history.list_runs()[0]
    assert run["operation"] == "sync_delete"
    assert run["status"] == "completed_with_errors"
    assert run["target"] == str(folder)


def test_sync_delete_without_analyzed_folder_refuses(api, project_dir, tmp_path):
    target = tmp_path / "a.mp3"
    target.write_bytes(b"")

    results = api.sync_delete([str(target)])

    assert results[0]["ok"] is False
    assert target.exists()


def test_main_yt_dlp_mode(monkeypatch):
    received = []
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(main=lambda args: received.append(args)))
    monkeypatch.setattr(sys, "argv", ["app", "--yt-dlp", "-v", "url"])

    app.main()

    assert received == [["-v", "url"]]


def test_main_fix_artwork_mode(monkeypatch):
    import fix_artwork

    received = []
    monkeypatch.setattr(fix_artwork, "fix_audio_artwork", lambda *args: received.append(args))
    monkeypatch.setattr(sys, "argv", ["app", "--fix-artwork", "f.mp3", "yt", "sp"])

    app.main()

    assert received == [("f.mp3", "yt", "sp")]


def fake_webview_module(monkeypatch):
    calls = {}
    module = SimpleNamespace(
        create_window=lambda *args, **kwargs: calls.update({"args": args, "kwargs": kwargs}),
        start=lambda **kwargs: calls.update({"start": kwargs}),
    )
    monkeypatch.setitem(sys.modules, "webview", module)
    return calls


def test_main_dev_mode(monkeypatch):
    calls = fake_webview_module(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["app", "--dev"])

    app.main()

    assert calls["args"][1] == "http://localhost:5173"
    assert calls["start"] == {"debug": True}
    assert isinstance(calls["kwargs"]["js_api"], UmupyApi)


def test_main_frozen_entry(monkeypatch, tmp_path):
    calls = fake_webview_module(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["app"])
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    app.main()

    assert calls["args"][1] == os.path.join(str(tmp_path), "UI", "dist", "index.html")


def test_main_missing_ui_build(monkeypatch, tmp_path, capsys):
    fake_webview_module(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["app"])
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(app, "PROJECT_DIR", str(tmp_path))

    with pytest.raises(SystemExit):
        app.main()

    assert "UI build not found" in capsys.readouterr().out


def test_main_with_ui_build(monkeypatch, tmp_path):
    calls = fake_webview_module(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["app"])
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(app, "PROJECT_DIR", str(tmp_path))
    entry = tmp_path / "UI" / "dist"
    entry.mkdir(parents=True)
    (entry / "index.html").write_text("<html/>")

    app.main()

    assert calls["args"][1] == str(entry / "index.html")
    assert calls["start"] == {"debug": False}
