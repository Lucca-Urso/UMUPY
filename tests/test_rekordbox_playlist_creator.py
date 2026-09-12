import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import rekordbox_playlist_creator as rpc


class FakeArtist:
    def __init__(self, name):
        self.Name = name


class FakeContent:
    def __init__(self, title, artist=None):
        self.Title = title
        self.Artist = FakeArtist(artist) if artist else None


class FakePlaylist:
    def __init__(self, name):
        self.Name = name


class FakeDB:
    def __init__(self, collection=(), playlists=()):
        self.collection = list(collection)
        self.playlists = [FakePlaylist(n) for n in playlists]
        self.created = []
        self.added = []
        self.commits = 0

    def get_content(self):
        return iter(self.collection)

    def get_playlist(self):
        return iter(self.playlists)

    def create_playlist(self, name):
        playlist = FakePlaylist(name)
        self.created.append(name)
        return playlist

    def add_to_playlist(self, playlist, content):
        self.added.append((playlist.Name, content.Title))

    def commit(self):
        self.commits += 1


def test_normalize_and_similarity():
    assert rpc.normalize("  Héllo, Wörld!! ") == "hello world"
    assert rpc.similarity_score("hello world", "world hello") == 1.0
    assert rpc.similarity_score("a b c d", "a") == 0.25
    assert rpc.similarity_score("", "x") == 0.0


def test_parse_txt_playlist_utf16(tmp_path):
    content = "#\tTrack Title\tArtist\tBPM\n1\tSong One\tArtist A\t120\n\n2\t\tArtist B\t100\n3\tSong Three\n"
    path = tmp_path / "list.txt"
    path.write_text(content, encoding="utf-16")

    tracks = rpc.parse_txt_playlist(path)

    assert tracks == [
        {"title": "Song One", "artist": "Artist A"},
        {"title": "Song Three", "artist": ""},
    ]


def test_parse_txt_playlist_utf8_fallback_and_no_header(tmp_path):
    path = tmp_path / "list.txt"
    path.write_text("Title\tArtist\nSong\tX\n", encoding="utf-8")
    assert rpc.parse_txt_playlist(path) == [{"title": "Song", "artist": "X"}]

    path.write_text("no header here\n", encoding="utf-8")
    assert rpc.parse_txt_playlist(path) == []


XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <COLLECTION Entries="3">
    <TRACK TrackID="1" Name="Alpha" Artist="A"/>
    <TRACK TrackID="2" Name="" Artist="B"/>
    <TRACK Name="No Id"/>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT">
      <NODE Type="1" Name="Set One"><TRACK Key="1"/><TRACK Key="2"/><TRACK Key="99"/></NODE>
      <NODE Type="1" Name="Empty"/>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""


def test_parse_xml_playlists(tmp_path):
    path = tmp_path / "rb.xml"
    path.write_text(XML)

    playlists = rpc.parse_xml_playlists(path)

    assert playlists == [
        {"name": "Set One", "tracks": [{"title": "Alpha", "artist": "A"}]},
        {"name": "Empty", "tracks": []},
    ]


def test_parse_xml_without_sections(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_text("<DJ_PLAYLISTS/>")

    assert rpc.parse_xml_playlists(path) == []


def test_parse_audio_folder(make_mp3, tmp_path, sample_mp3_bytes):
    make_mp3("tagged", title="Song", artist="Artist")
    (tmp_path / "raw.mp3").write_bytes(sample_mp3_bytes)
    (tmp_path / "broken.flac").write_bytes(b"x")
    (tmp_path / "skip.txt").write_text("x")

    tracks = rpc.parse_audio_folder(tmp_path)

    assert tracks == [
        {"title": "broken", "artist": ""},
        {"title": "raw", "artist": ""},
        {"title": "Song", "artist": "Artist"},
    ]


def test_folder_playlist_name():
    assert rpc.folder_playlist_name("/x/My_Mix_04_09") == "My Mix"
    assert rpc.folder_playlist_name("/x/Plain") == "Plain"


def test_load_playlists_from_source_variants(tmp_path, make_mp3):
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "rb.xml").write_text(XML)
    (exports / "my_list.txt").write_text("Track Title\tArtist\nS\tA\n", encoding="utf-16")
    (exports / "empty.txt").write_text("nothing", encoding="utf-16")

    playlists = rpc.load_playlists_from_source(exports)
    assert [p["name"] for p in playlists] == ["my list", "Set One"]

    single = rpc.load_playlists_from_source(exports / "rb.xml")
    assert [p["name"] for p in single] == ["Set One"]

    music = tmp_path / "Music_01_01"
    make_mp3("song", directory=str(music), title="T")
    assert rpc.load_playlists_from_source(music) == [{"name": "Music", "tracks": [{"title": "T", "artist": ""}]}]

    empty = tmp_path / "empty"
    empty.mkdir()
    assert rpc.load_playlists_from_source(empty) == []


def test_find_best_match():
    collection = [FakeContent("Alpha Song", "Artist A"), FakeContent("Beta Track", None), FakeContent(None)]

    assert rpc.find_best_match({"title": "Alpha Song", "artist": "Artist A"}, collection).Title == "Alpha Song"
    assert rpc.find_best_match({"title": "Beta Track", "artist": ""}, collection).Title == "Beta Track"
    assert rpc.find_best_match({"title": "Nothing Here", "artist": "Zed"}, collection) is None


def test_open_database_and_running(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrekordbox", SimpleNamespace(Rekordbox6Database=FakeDB))
    monkeypatch.setitem(sys.modules, "pyrekordbox.utils", SimpleNamespace(get_rekordbox_pid=lambda: 0))

    assert isinstance(rpc.open_database(), FakeDB)
    assert rpc.rekordbox_is_running() is False


def test_match_playlists_and_preview(capsys):
    collection = [FakeContent("Alpha", "A")]
    playlists = [
        {"name": "Existing", "tracks": [{"title": "Alpha", "artist": "A"}]},
        {"name": "New", "tracks": [{"title": "Alpha", "artist": "A"}, {"title": "Zzz", "artist": "Q"}]},
    ]

    results = rpc.match_playlists(playlists, collection, {"Existing"})
    rpc.preview_results(results)

    assert results[0]["exists"] is True
    assert len(results[1]["matched"]) == 1
    assert results[1]["unmatched"] == [{"title": "Zzz", "artist": "Q"}]
    out = capsys.readouterr().out
    assert "already exists, will be skipped" in out
    assert "- Zzz (Q) [NOT FOUND]" in out


def test_ask_yes_no(monkeypatch):
    answers = iter(["x", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert rpc.ask_yes_no("?") is False


def test_create_playlists():
    db = FakeDB()
    results = [
        {"name": "Skip Exists", "exists": True, "matched": [{"content": FakeContent("A")}], "unmatched": []},
        {"name": "Skip Empty", "exists": False, "matched": [], "unmatched": []},
        {"name": "Create", "exists": False, "matched": [{"content": FakeContent("A")}, {"content": FakeContent("B")}], "unmatched": []},
    ]

    assert rpc.create_playlists(db, results) == 1
    assert db.created == ["Create"]
    assert db.added == [("Create", "A"), ("Create", "B")]
    assert db.commits == 1


def test_main_path_not_found(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("builtins.input", lambda _: str(tmp_path / "missing"))

    with pytest.raises(SystemExit):
        rpc.main()

    assert "Path not found" in capsys.readouterr().out


def test_main_no_playlists(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", str(tmp_path)])

    with pytest.raises(SystemExit):
        rpc.main()

    assert "No playlists found" in capsys.readouterr().out


def prepare_main(monkeypatch, tmp_path, db, running=False):
    (tmp_path / "rb.xml").write_text(XML)
    monkeypatch.setattr(sys, "argv", ["prog", str(tmp_path / "rb.xml")])
    monkeypatch.setattr(rpc, "open_database", lambda: db)
    monkeypatch.setattr(rpc, "rekordbox_is_running", lambda: running)


def test_main_nothing_to_create(monkeypatch, tmp_path, capsys):
    prepare_main(monkeypatch, tmp_path, FakeDB([FakeContent("Alpha", "A")], playlists=["Set One"]))

    rpc.main()

    assert "Nothing to create" in capsys.readouterr().out


def test_main_cancelled(monkeypatch, tmp_path, capsys):
    prepare_main(monkeypatch, tmp_path, FakeDB([FakeContent("Alpha", "A")]))
    monkeypatch.setattr("builtins.input", lambda _: "n")

    rpc.main()

    assert "Operation cancelled" in capsys.readouterr().out


def test_main_rekordbox_running(monkeypatch, tmp_path, capsys):
    prepare_main(monkeypatch, tmp_path, FakeDB([FakeContent("Alpha", "A")]), running=True)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    with pytest.raises(SystemExit):
        rpc.main()

    assert "RekordBox is running" in capsys.readouterr().out


def test_main_creates_playlists(project_dir, monkeypatch, tmp_path, capsys):
    db = FakeDB([FakeContent("Alpha", "A")])
    prepare_main(monkeypatch, tmp_path, db)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    rpc.main()

    assert db.created == ["Set One"]
    assert "[OK] 1 playlist(s) created" in capsys.readouterr().out
