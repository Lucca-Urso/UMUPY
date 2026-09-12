import os
import subprocess
import sys

import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "Features"))

REAL_RUN = subprocess.run


def locate_ffmpeg():
    import yt_downloader

    return yt_downloader.find_ffmpeg()


@pytest.fixture(scope="session")
def sample_mp3_bytes():
    ffmpeg = locate_ffmpeg()

    if not ffmpeg:
        pytest.skip("ffmpeg is required to build the sample MP3 fixture (install it or place it in Dependencies/)")

    result = REAL_RUN(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", "0.2", "-codec:a", "libmp3lame", "-b:a", "32k", "-f", "mp3", "pipe:1"],
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


@pytest.fixture
def make_mp3(tmp_path, sample_mp3_bytes):
    from mutagen.id3 import TIT2, TPE1, TXXX
    from mutagen.mp3 import MP3

    def _make(name, youtube_id=None, spotify_id=None, title=None, artist=None, directory=None):
        directory = directory or tmp_path
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{name}.mp3")

        with open(path, "wb") as handle:
            handle.write(sample_mp3_bytes)

        audio = MP3(path)

        if audio.tags is None:
            audio.add_tags()

        if youtube_id:
            audio.tags.add(TXXX(encoding=3, desc="YOUTUBE_ID", text=[youtube_id]))

        if spotify_id:
            audio.tags.add(TXXX(encoding=3, desc="SPOTIFY_ID", text=[spotify_id]))

        if title:
            audio.tags.add(TIT2(encoding=3, text=[title]))

        if artist:
            audio.tags.add(TPE1(encoding=3, text=[artist]))

        audio.save(v2_version=3)
        return path

    return _make


@pytest.fixture(autouse=True)
def block_real_subprocess(request, monkeypatch):
    if "fake_run" in request.fixturenames or "commands" in request.fixturenames:
        return

    def guard(command, *args, **kwargs):
        raise AssertionError(f"Unmocked subprocess.run call: {list(command)[:3]}")

    monkeypatch.setattr(subprocess, "run", guard)


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    import history
    import yt_downloader

    monkeypatch.setattr(yt_downloader, "get_project_directory", lambda: str(tmp_path))
    monkeypatch.setattr(history, "get_project_directory", lambda: str(tmp_path))
    return tmp_path


class SyncThread:
    def __init__(self, target, args=(), daemon=None):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def api(project_dir, monkeypatch):
    import threading

    import download_engine
    from api import UmupyApi

    import yt_downloader

    monkeypatch.setattr(threading, "Thread", SyncThread)
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")

    def sequential_run(self, tracks):
        for item in tracks:
            self.process(item)

        return list(self.results)

    monkeypatch.setattr(download_engine.DownloadEngine, "run", sequential_run)
    return UmupyApi()


@pytest.fixture
def spotify_env(monkeypatch):
    import spotify_converter
    import sync_playlists
    from providers import soundcloud, youtube

    def configure(tracks, local_files=None, searcher=None, name="Mix"):
        monkeypatch.setattr(spotify_converter, "open_spotify", lambda: "spotify")
        monkeypatch.setattr(spotify_converter, "fetch_playlist", lambda *_: {"name": name, "tracks": tracks})
        monkeypatch.setattr(spotify_converter, "open_ytmusic", lambda: "yt")
        monkeypatch.setattr(youtube, "search", searcher or (lambda client, track: None))
        monkeypatch.setattr(soundcloud, "search", lambda client, track: None)

        if local_files is not None:
            monkeypatch.setattr(sync_playlists, "build_local_index", lambda _: local_files)
            monkeypatch.setattr(sync_playlists, "heal_ids", lambda pairs: 0)

    return configure


class FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def fake_run(monkeypatch):
    calls = []
    responses = []

    def _run(command, **kwargs):
        calls.append({"command": list(command), "kwargs": kwargs})

        if responses:
            response = responses.pop(0)
            return response(command) if callable(response) else response

        return FakeCompleted()

    monkeypatch.setattr(subprocess, "run", _run)

    class Handle:
        def __init__(self):
            self.calls = calls

        def queue(self, *items):
            responses.extend(items)

        def last(self):
            return calls[-1]["command"]

    return Handle()
