import json
import os
import sys

import pytest

import spotify_converter
import yt_downloader


class FakeSpotify:
    def __init__(self, pages):
        self.pages = pages

    def playlist(self, url):
        return {"name": "Mix", "tracks": self.pages[0]}

    def next(self, page):
        return self.pages[self.pages.index(page) + 1]


def make_track(track_id, title="Song", artists=("Artist",), duration_ms=200000):
    return {
        "track": {
            "id": track_id,
            "name": title,
            "artists": [{"name": name} for name in artists],
            "duration_ms": duration_ms,
        }
    }


class FakeYTMusic:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.queries = []

    def search(self, query, filter=None, limit=10):
        self.queries.append(query)

        if self.error:
            raise self.error

        return self.results


def test_retry_call_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    attempts = []

    def operation():
        attempts.append(1)

        if len(attempts) < 3:
            raise ValueError("flaky")

        return "ok"

    assert spotify_converter.retry_call(operation, attempts=4, delay=0) == "ok"
    assert len(attempts) == 3


def test_retry_call_gives_up(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(ValueError):
        spotify_converter.retry_call(lambda: (_ for _ in ()).throw(ValueError("x")), attempts=2, delay=0)


def test_credential_paths(project_dir):
    assert spotify_converter.get_credentials_path() == str(project_dir / "Dependencies" / "spotify_credentials.json")
    assert spotify_converter.get_token_cache_path() == str(project_dir / "Dependencies" / ".spotify_token_cache")


def write_credentials(project_dir, payload):
    dependencies = project_dir / "Dependencies"
    dependencies.mkdir(exist_ok=True)
    (dependencies / "spotify_credentials.json").write_text(json.dumps(payload))


def test_load_credentials_missing_file(project_dir, capsys):
    with pytest.raises(SystemExit):
        spotify_converter.load_credentials()

    assert "Spotify credentials not found" in capsys.readouterr().out


def test_load_credentials_accepts_aliases(project_dir):
    write_credentials(project_dir, {"clientId": "id", "secret": "s"})

    credentials = spotify_converter.load_credentials()

    assert credentials["client_id"] == "id"
    assert credentials["client_secret"] == "s"

    if os.name == "posix":
        mode = os.stat(project_dir / "Dependencies" / "spotify_credentials.json").st_mode & 0o777
        assert oct(mode) == "0o600"


def test_restrict_permissions_edge_cases(tmp_path, monkeypatch):
    assert spotify_converter.restrict_permissions(str(tmp_path / "missing")) is False

    target = tmp_path / "f"
    target.write_text("x")
    monkeypatch.setattr(os, "name", "nt")
    assert spotify_converter.restrict_permissions(str(target)) is False

    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "chmod", lambda *_: (_ for _ in ()).throw(OSError("ro")))
    assert spotify_converter.restrict_permissions(str(target)) is False


def test_load_credentials_missing_key(project_dir, capsys):
    write_credentials(project_dir, {"client_id": "id"})

    with pytest.raises(SystemExit):
        spotify_converter.load_credentials()

    assert "Missing 'client_secret'" in capsys.readouterr().out


def test_open_spotify_builds_client(project_dir, monkeypatch):
    write_credentials(project_dir, {"client_id": "id", "client_secret": "s"})
    captured = {}

    class FakeOAuth:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeClient:
        def __init__(self, auth_manager, **kwargs):
            captured["client"] = auth_manager

    monkeypatch.setitem(sys.modules, "spotipy", type("M", (), {"Spotify": FakeClient})())
    monkeypatch.setitem(sys.modules, "spotipy.oauth2", type("M", (), {"SpotifyOAuth": FakeOAuth})())

    spotify_converter.open_spotify()

    assert captured["client_id"] == "id"
    assert captured["redirect_uri"] == "http://127.0.0.1:8888/callback"
    assert captured["cache_path"].endswith(".spotify_token_cache")
    assert isinstance(captured["client"], FakeOAuth)


def test_open_ytmusic(monkeypatch):
    monkeypatch.setitem(sys.modules, "ytmusicapi", type("M", (), {"YTMusic": FakeYTMusic})())

    assert isinstance(spotify_converter.open_ytmusic(), FakeYTMusic)


def test_fetch_playlist_paginates_and_skips_invalid():
    page_two = {"items": [make_track("b")], "next": None}
    page_one = {"items": [make_track("a"), {"track": None}, {"track": {"id": None}}], "next": "more"}

    playlist = spotify_converter.fetch_playlist(FakeSpotify([page_one, page_two]), "url")

    assert playlist["name"] == "Mix"
    assert [t["spotify_id"] for t in playlist["tracks"]] == ["a", "b"]
    assert playlist["tracks"][0]["duration"] == 200


def test_fetch_playlist_supports_items_key():
    class Spotify:
        def playlist(self, url):
            return {"name": "N", "items": {"items": [{"item": make_track("z")["track"]}], "next": None}}

    playlist = spotify_converter.fetch_playlist(Spotify(), "url")

    assert playlist["tracks"][0]["spotify_id"] == "z"


TRACK = {"spotify_id": "sp1", "title": "One More Time", "artists": ["Daft Punk"], "duration": 320}


def test_search_youtube_equivalent_picks_best_match():
    ytmusic = FakeYTMusic([
        {"videoId": None, "title": "One More Time"},
        {"videoId": "far", "title": "Something Else", "artists": [{"name": "Nobody"}], "duration_seconds": 100},
        {"videoId": "best", "title": "One More Time", "artists": [{"name": "Daft Punk"}], "duration_seconds": 322},
    ])

    video = spotify_converter.search_youtube_equivalent(ytmusic, TRACK)

    assert video["id"] == "best"
    assert video["spotify_id"] == "sp1"
    assert video["url"].endswith("best")
    assert video["score"] >= spotify_converter.MATCH_THRESHOLD
    assert ytmusic.queries == ["Daft Punk One More Time"]


def test_search_youtube_equivalent_below_threshold():
    ytmusic = FakeYTMusic([{"videoId": "x", "title": "Totally Unrelated", "artists": [{"name": "Other"}]}])

    assert spotify_converter.search_youtube_equivalent(ytmusic, TRACK) is None


def test_search_youtube_equivalent_no_results():
    assert spotify_converter.search_youtube_equivalent(FakeYTMusic(None), TRACK) is None


def test_build_spotify_index(make_mp3, tmp_path, sample_mp3_bytes):
    make_mp3("a", spotify_id="sp1")
    make_mp3("b", youtube_id="yt")
    (tmp_path / "raw.mp3").write_bytes(sample_mp3_bytes)
    (tmp_path / "bad.mp3").write_bytes(b"x")
    (tmp_path / "note.txt").write_text("x")

    assert spotify_converter.build_spotify_index([str(tmp_path)]) == {"sp1": str(tmp_path / "a.mp3")}


def test_convert_tracks_mixed_results(monkeypatch, capsys):
    outcomes = {"a": {"id": "v", "title": "V", "url": "u", "score": 90}, "b": None}
    monkeypatch.setattr(spotify_converter, "search_youtube_equivalent", lambda _, track: outcomes[track["spotify_id"]])
    tracks = [{**TRACK, "spotify_id": "a"}, {**TRACK, "spotify_id": "b"}]

    matched, unmatched = spotify_converter.convert_tracks(None, tracks)

    assert len(matched) == 1
    assert len(unmatched) == 1
    out = capsys.readouterr().out
    assert "[OK 90]" in out
    assert "[NOT FOUND]" in out


def test_convert_tracks_aborts_after_consecutive_failures(monkeypatch, capsys):
    def boom(*_):
        raise ConnectionError("down")

    monkeypatch.setattr(spotify_converter, "search_youtube_equivalent", boom)
    monkeypatch.setattr(spotify_converter, "MAX_CONSECUTIVE_FAILURES", 2)
    tracks = [{**TRACK, "spotify_id": str(i)} for i in range(5)]

    matched, unmatched = spotify_converter.convert_tracks(None, tracks)

    assert matched == []
    assert len(unmatched) == 2
    assert "consecutive network failures" in capsys.readouterr().out


def test_download_videos_without_ffmpeg(monkeypatch):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: None)

    with pytest.raises(SystemExit):
        spotify_converter.download_videos([], "Mix")


def test_download_videos_reports(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(yt_downloader, "get_today", lambda: "01_01")
    monkeypatch.setattr(yt_downloader, "download_video", lambda video, *_: 0 if video["id"] == "ok" else 1)
    videos = [{"id": "ok", "title": "Good", "url": "u"}, {"id": "bad", "title": "Bad", "url": "u"}]

    output = spotify_converter.download_videos(videos, "Mix")

    assert output == str(project_dir / "Downloads" / "Mix_01_01")
    out = capsys.readouterr().out
    assert "[OK] 1/2 musics downloaded." in out
    assert "1 download(s) failed" in out


def prepare_main(monkeypatch, matched, argv=("prog", "https://open.spotify.com/playlist/x")):
    monkeypatch.setattr(sys, "argv", list(argv))
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: "spotify")
    monkeypatch.setattr(spotify_converter, "fetch_playlist", lambda *_: {"name": "Mix", "tracks": [TRACK]})
    monkeypatch.setattr(spotify_converter, "open_ytmusic", lambda: "yt")
    monkeypatch.setattr(spotify_converter, "convert_tracks", lambda *_: (list(matched), []))


def test_main_without_url_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("builtins.input", lambda _: "")

    with pytest.raises(SystemExit):
        spotify_converter.main()

    assert "URL not provided" in capsys.readouterr().out


def test_main_nothing_matched(monkeypatch, capsys):
    prepare_main(monkeypatch, [])

    spotify_converter.main()

    assert "Nothing to download" in capsys.readouterr().out


def test_main_full_flow_with_duplicate_scan(monkeypatch, capsys):
    matched = [
        {"id": "yt-dup", "title": "Dup", "url": "u", "spotify_id": "s1"},
        {"id": "yt-new", "title": "New", "url": "u", "spotify_id": "s2"},
        {"id": "yt-spdup", "title": "SpDup", "url": "u", "spotify_id": "s3"},
    ]
    prepare_main(monkeypatch, matched)
    monkeypatch.setattr(yt_downloader, "select_duplicate_scan_folders", lambda: ["/scan"])
    monkeypatch.setattr(spotify_converter, "build_spotify_index", lambda _: {"s3": "p"})
    downloaded = []
    monkeypatch.setattr(spotify_converter, "download_videos", lambda videos, _: downloaded.extend(videos) or "/out")
    answers = iter(["y", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    spotify_converter.main()

    assert [v["id"] for v in downloaded] == ["yt-dup", "yt-new"]
    assert "/out" in capsys.readouterr().out


def test_main_scan_removes_everything(monkeypatch, capsys):
    prepare_main(monkeypatch, [{"id": "yt-dup", "title": "Dup", "url": "u", "spotify_id": "s1"}])
    monkeypatch.setattr(yt_downloader, "select_duplicate_scan_folders", lambda: ["/scan"])
    monkeypatch.setattr(spotify_converter, "build_spotify_index", lambda _: {"s1": "p"})
    monkeypatch.setattr("builtins.input", lambda _: "y")

    spotify_converter.main()

    assert "Nothing to download" in capsys.readouterr().out


def test_main_user_cancels(monkeypatch, capsys):
    prepare_main(monkeypatch, [{"id": "v", "title": "T", "url": "u", "spotify_id": "s"}])
    answers = iter(["n", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    spotify_converter.main()

    assert "Operation cancelled" in capsys.readouterr().out
