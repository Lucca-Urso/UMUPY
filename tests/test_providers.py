import json
import sys
from types import SimpleNamespace

import pytest

import providers
import spotify_converter
import yt_downloader
from providers import base, soundcloud, spotify, youtube, ytdlp

TRACK = {"id": "sp1", "title": "One More Time", "artists": ["Daft Punk"], "duration": 320, "spotify_id": "sp1"}


def test_registry_and_detection():
    assert set(providers.PROVIDERS) == {"youtube", "spotify", "soundcloud"}
    assert providers.TAGS == {"youtube": "YOUTUBE_ID", "spotify": "SPOTIFY_ID", "soundcloud": "SOUNDCLOUD_ID"}
    assert providers.get("youtube") is youtube
    assert providers.detect("https://www.youtube.com/watch?v=x") == "youtube"
    assert providers.detect("youtu.be/x") == "youtube"
    assert providers.detect("https://music.youtube.com/playlist?list=x") == "youtube"
    assert providers.detect("https://open.spotify.com/playlist/x") == "spotify"
    assert providers.detect("spotify:playlist:x") == "spotify"
    assert providers.detect(" https://soundcloud.com/a/sets/b ") == "soundcloud"
    assert providers.detect("https://example.com") is None
    assert providers.detect(None) is None
    assert providers.fallbacks_for("youtube") == ["soundcloud"]
    assert providers.fallbacks_for("spotify") == ["youtube", "soundcloud"]


def test_base_helpers():
    track = base.make_track("youtube", 123, None, artists=["A", "", None], extra=1)
    assert track == {"id": "123", "title": "", "artists": ["A"], "duration": None, "url": None, "source": "youtube", "extra": 1}
    assert base.track_label(TRACK) == "Daft Punk - One More Time"
    assert base.track_label({"title": "Solo", "artists": []}) == "Solo"
    assert base.search_query(TRACK) == "Daft Punk One More Time"
    assert base.search_query({"title": "Solo"}) == "Solo"


def test_score_match_and_pick_best():
    exact = base.make_track("youtube", "a", "One More Time", artists=["Daft Punk"], duration=322)
    far = base.make_track("youtube", "b", "Something Else", artists=["Nobody"], duration=100)

    assert base.score_match(TRACK, "One More Time", "Daft Punk", 322) == 110
    assert base.score_match({"title": "One More Time", "artists": []}, "One More Time", "Anyone") == 100
    best = base.pick_best(TRACK, [far, exact])
    assert best["id"] == "a"
    assert best["score"] == 110
    assert base.pick_best(TRACK, [far]) is None
    assert base.pick_best(TRACK, []) is None


def test_retry_call(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    attempts = []

    def flaky():
        attempts.append(1)

        if len(attempts) < 2:
            raise ValueError("x")

        return "ok"

    assert base.retry_call(flaky) == "ok"

    with pytest.raises(ValueError):
        base.retry_call(lambda: (_ for _ in ()).throw(ValueError("x")), attempts=2, delay=0)


def test_ytdlp_helpers(fake_run, project_dir):
    fake_run.queue(SimpleNamespace(returncode=0, stdout=json.dumps({"id": 1}) + "\nbad\n", stderr=""))

    entries, stderr, code = ytdlp.dump_json(["--flat-playlist"], "url")

    assert entries == [{"id": 1}]
    assert code == 0
    command = fake_run.last()
    assert command[-1] == "url"
    assert "--dump-json" in command and "--flat-playlist" in command and "--no-warnings" in command
    assert ytdlp.error_summary("WARNING: a\nERROR: b") == "ERROR: b"
    assert ytdlp.error_summary("l1\nl2\nl3\nl4") == "l2 | l3 | l4"
    assert ytdlp.error_summary("") == "yt-dlp returned no results"


def test_youtube_provider_resolve(monkeypatch):
    monkeypatch.setattr(yt_downloader, "detect_playlist", lambda *_: "Mix")
    monkeypatch.setattr(yt_downloader, "extract_videos", lambda *_: [{"id": "v", "title": "T", "url": "u"}])

    result = youtube.resolve("url")

    assert result["name"] == "Mix"
    assert result["tracks"][0]["source"] == "youtube"
    assert result["error"] is None

    monkeypatch.setattr(yt_downloader, "detect_playlist", lambda *_: "")
    monkeypatch.setattr(yt_downloader, "extract_videos", lambda *_: [])
    monkeypatch.setattr(yt_downloader, "probe_url_error", lambda *_: "bad")

    assert youtube.resolve("url") == {"name": None, "tracks": [], "error": "bad"}


def test_youtube_provider_search_and_client(monkeypatch):
    class Client:
        def search(self, query, filter=None, limit=10):
            assert query == "Daft Punk One More Time"
            return [
                {"videoId": None, "title": "skip"},
                {"videoId": "v1", "title": "One More Time", "artists": [{"name": "Daft Punk"}], "duration_seconds": 320},
            ]

    monkeypatch.setitem(sys.modules, "ytmusicapi", SimpleNamespace(YTMusic=Client))

    client = youtube.open_client()
    video = youtube.search(client, TRACK)

    assert video["id"] == "v1"
    assert video["url"] == "https://www.youtube.com/watch?v=v1"
    assert video["source"] == "youtube"
    assert youtube.search(SimpleNamespace(search=lambda *a, **k: None), TRACK) is None


def test_spotify_provider(monkeypatch):
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: "client")
    monkeypatch.setattr(
        spotify_converter, "fetch_playlist",
        lambda client, url: {"name": "Mix", "tracks": [{"spotify_id": "s", "title": "T", "artists": ["A"], "duration": 10}]},
    )

    result = spotify.resolve("url")

    assert result["name"] == "Mix"
    assert result["tracks"][0]["spotify_id"] == "s"
    assert result["tracks"][0]["source"] == "spotify"
    assert spotify.open_client() == "client"
    assert spotify.search(None, TRACK) is None
    assert spotify.DOWNLOADABLE is False


def sc_entry(track_id, title, artist="Forss", duration=142.2, url=None):
    return {"id": track_id, "title": title, "uploader": artist, "duration": duration, "webpage_url": url or f"https://soundcloud.com/forss/{track_id}"}


def test_soundcloud_entry_to_track():
    track = soundcloud.entry_to_track({"id": 1, "title": "T", "artist": "Art", "uploader": "Up", "duration": 10.6, "url": "u"})

    assert track == {"id": "1", "title": "T", "artists": ["Art"], "duration": 11, "url": "u", "source": "soundcloud"}
    assert soundcloud.entry_to_track({"id": 2, "title": "T"})["artists"] == []
    assert soundcloud.entry_to_track({"id": 2, "title": "T"})["duration"] is None


def test_soundcloud_resolve_single_track(monkeypatch):
    monkeypatch.setattr(ytdlp, "dump_json", lambda args, url: ([sc_entry(293, "Flickermood")], "", 0))

    result = soundcloud.resolve("https://soundcloud.com/forss/flickermood")

    assert result["name"] is None
    assert result["tracks"][0]["title"] == "Flickermood"
    assert result["error"] is None

    monkeypatch.setattr(ytdlp, "dump_json", lambda args, url: ([], "ERROR: 404", 1))
    assert soundcloud.resolve("https://soundcloud.com/x/y") == {"name": None, "tracks": [], "error": "ERROR: 404"}


def test_soundcloud_resolve_set(monkeypatch):
    calls = []

    def dump_json(args, url):
        calls.append(args)

        if "--flat-playlist" in args:
            return ([{"id": str(i), "url": f"https://soundcloud.com/forss/{i}", "playlist_title": "Soulhack"} for i in range(1, 13)], "", 0)

        start, end = map(int, args[args.index("--playlist-items") + 1].split("-"))
        entries = [sc_entry(i, f"Track {i}") for i in range(start, end + 1)]
        entries.append(sc_entry(start, "Duplicate"))
        entries.append({"title": "no id"})
        return (entries, "", 0)

    monkeypatch.setattr(ytdlp, "dump_json", dump_json)

    result = soundcloud.resolve("https://soundcloud.com/forss/sets/soulhack")

    assert result["name"] == "Soulhack"
    assert [t["id"] for t in result["tracks"]] == [str(i) for i in range(1, 13)]
    assert result["error"] is None
    ranges = [a[a.index("--playlist-items") + 1] for a in calls if "--playlist-items" in a]
    assert ranges == ["1-5", "6-10", "11-12"]


def test_soundcloud_resolve_set_errors(monkeypatch):
    monkeypatch.setattr(ytdlp, "dump_json", lambda args, url: ([], "ERROR: private", 1))
    assert soundcloud.resolve("https://soundcloud.com/a/sets/b") == {"name": None, "tracks": [], "error": "ERROR: private"}

    def dump_json(args, url):
        if "--flat-playlist" in args:
            return ([{"id": "1", "url": "u1", "playlist_title": "S"}], "", 0)

        return ([], "", 1)

    monkeypatch.setattr(ytdlp, "dump_json", dump_json)
    result = soundcloud.resolve("https://soundcloud.com/a/sets/b")
    assert result["name"] == "S"
    assert result["error"] is None
    assert result["tracks"][0]["unavailable"] == "Unavailable on SoundCloud"


def test_soundcloud_resolve_set_keeps_unavailable_tracks(monkeypatch):
    def dump_json(args, url):
        if "--flat-playlist" in args:
            return ([
                {"id": "1", "url": "https://soundcloud.com/a/first-song", "playlist_title": "S"},
                {"id": "2", "url": "https://api-v2.soundcloud.com/tracks/2"},
                {"id": "3", "url": "https://api-v2.soundcloud.com/tracks/3"},
                {"id": "4", "url": "https://soundcloud.com/b/bodies-ivory-it-remix"},
            ], "", 0)

        entries = [sc_entry(1, "First Song", url="https://soundcloud.com/a/first-song")]
        stderr = "ERROR: [soundcloud] 2: This video is DRM protected\nERROR: [soundcloud] This video is not available from your location due to geo restriction\n"
        return (entries, stderr, 1)

    monkeypatch.setattr(ytdlp, "dump_json", dump_json)

    result = soundcloud.resolve("https://soundcloud.com/a/sets/b")

    tracks = result["tracks"]
    assert [t["id"] for t in tracks] == ["1", "2", "3", "https://soundcloud.com/b/bodies-ivory-it-remix"]
    assert "unavailable" not in tracks[0]
    assert tracks[1]["unavailable"] == "This video is DRM protected"
    assert tracks[1]["title"] == "Unknown track 2"
    assert tracks[1]["searchable"] is False
    assert tracks[3]["searchable"] is True
    assert tracks[2]["unavailable"] == "Not available in your location"
    assert tracks[3]["title"] == "Bodies Ivory It Remix"
    assert tracks[3]["unavailable"] == "Not available in your location"


def test_soundcloud_helpers_for_unavailable_tracks():
    assert soundcloud.slug_to_title("https://soundcloud.com/x/my-great_track") == "My Great Track"
    assert soundcloud.slug_to_title("https://api-v2.soundcloud.com/tracks/99") == ""
    assert soundcloud.unavailable_reason("", None) == "Unavailable on SoundCloud"
    assert soundcloud.unavailable_reason("ERROR: [soundcloud] 5: Private track", "5") == "Private track"


def test_soundcloud_search(monkeypatch):
    seen = {}

    def dump_json(args, url):
        seen["url"] = url
        return ([sc_entry(1, "One More Time", "Daft Punk", 323), {"id": 2, "title": None}], "", 0)

    monkeypatch.setattr(ytdlp, "dump_json", dump_json)

    result = soundcloud.search(None, TRACK)

    assert seen["url"] == "scsearch5:Daft Punk One More Time"
    assert result["id"] == "1"
    assert result["source"] == "soundcloud"
    assert soundcloud.open_client() is None
    assert soundcloud.matches("https://soundcloud.com/x") is True
    assert soundcloud.is_playlist("https://soundcloud.com/x/sets/y") is True
