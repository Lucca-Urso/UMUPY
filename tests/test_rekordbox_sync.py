import os
from types import SimpleNamespace

import pytest

import rekordbox_sync


class FakeContent:
    def __init__(self, content_id, path, title="", artist=None):
        self.ID = content_id
        self.FolderPath = path
        self.Title = title
        self.Artist = SimpleNamespace(Name=artist) if artist else None


class FakeSong:
    def __init__(self, song_id, playlist_id, content):
        self.ID = song_id
        self.PlaylistID = playlist_id
        self.Content = content


class FakePlaylist:
    def __init__(self, playlist_id, name, smart=None):
        self.ID = playlist_id
        self.Name = name
        self.SmartList = smart


class FakeDB:
    def __init__(self, db_directory, contents=(), playlists=(), songs=()):
        self.db_directory = db_directory
        self.contents = list(contents)
        self.playlists = list(playlists)
        self.songs = list(songs)
        self.commits = 0
        self.fail_add_content = False
        self.fail_remove = False

    def get_content(self):
        return iter(self.contents)

    def get_playlist(self):
        return iter(self.playlists)

    def get_playlist_songs(self, PlaylistID=None):
        return [song for song in self.songs if song.PlaylistID == PlaylistID]

    def create_playlist(self, name):
        playlist = FakePlaylist(len(self.playlists) + 100, name)
        self.playlists.append(playlist)
        return playlist

    def add_content(self, path, **kwargs):
        if self.fail_add_content:
            raise ValueError("unsupported file")

        content = FakeContent(len(self.contents) + 500, str(path), kwargs.get("Title", ""))
        self.contents.append(content)
        return content

    def add_to_playlist(self, playlist, content):
        self.songs.append(FakeSong(len(self.songs) + 900, playlist.ID, content))

    def remove_from_playlist(self, playlist, song_id):
        if self.fail_remove:
            raise RuntimeError("locked")

        self.songs = [song for song in self.songs if song.ID != song_id]

    def commit(self):
        self.commits += 1


@pytest.fixture
def music(tmp_path, make_mp3):
    folder = tmp_path / "My_Mix_01_01"
    make_mp3("a", title="Alpha", artist="Artist A", directory=str(folder))
    make_mp3("b", directory=str(folder))
    (folder / "c.wav").write_bytes(b"RIFF")
    (folder / "notes.txt").write_text("x")
    return folder


def test_list_local_tracks_reads_tags_and_falls_back_to_filename(music):
    tracks = rekordbox_sync.list_local_tracks(str(music))

    assert [(t["title"], t["artist"]) for t in tracks] == [("Alpha", "Artist A"), ("b", ""), ("c", "")]
    assert rekordbox_sync.playlist_name_for(str(music)) == "My Mix"


def test_plan_sync_for_new_playlist(music, tmp_path):
    db = FakeDB(str(tmp_path), contents=[FakeContent(1, str(music / "a.mp3"), "Alpha")])

    plan = rekordbox_sync.plan_sync(db, str(music))

    assert plan["playlist"] == "My Mix"
    assert plan["exists"] is False
    assert [(t["title"], t["in_collection"]) for t in plan["add"]] == [("Alpha", True), ("b", False), ("c", False)]
    assert plan["keep"] == []
    assert plan["remove"] == []


def test_plan_sync_diffs_existing_playlist(music, tmp_path):
    kept = FakeContent(1, str(music / "a.mp3"), "Alpha", "Artist A")
    gone = FakeContent(2, str(tmp_path / "elsewhere.mp3"), "Gone")
    broken = FakeContent(3, None, "No path")
    playlist = FakePlaylist(10, "Custom")
    smart = FakePlaylist(11, "Custom", smart="<x/>")
    db = FakeDB(
        str(tmp_path), contents=[kept, gone, broken], playlists=[smart, playlist],
        songs=[FakeSong(1, 10, kept), FakeSong(2, 10, gone), FakeSong(3, 10, None), FakeSong(4, 99, gone)],
    )

    plan = rekordbox_sync.plan_sync(db, str(music), "Custom")

    assert plan["exists"] is True
    assert [t["title"] for t in plan["keep"]] == ["Alpha"]
    assert [t["title"] for t in plan["add"]] == ["b", "c"]
    assert [(s["song_id"], s["title"], s["artist"]) for s in plan["remove"]] == [(2, "Gone", "")]


def test_backup_database(tmp_path):
    db_dir = tmp_path / "rb"
    db_dir.mkdir()
    (db_dir / "master.db").write_bytes(b"data")
    db = FakeDB(str(db_dir))

    backup = rekordbox_sync.backup_database(db, str(tmp_path / "backups"))

    assert backup.startswith(str(tmp_path / "backups" / "master_"))
    assert open(backup, "rb").read() == b"data"
    assert rekordbox_sync.backup_database(FakeDB(str(tmp_path / "missing")), str(tmp_path / "b2")) is None


def test_apply_sync_creates_playlist_adds_and_removes(music, tmp_path):
    db_dir = tmp_path / "rb"
    db_dir.mkdir()
    (db_dir / "master.db").write_bytes(b"data")
    existing = FakeContent(1, str(music / "a.mp3"), "Alpha")
    db = FakeDB(str(db_dir), contents=[existing])
    plan = rekordbox_sync.plan_sync(db, str(music))

    result = rekordbox_sync.apply_sync(db, plan, [str(music / "a.mp3"), str(music / "b.mp3")], [], str(tmp_path / "backups"))

    assert result["created"] is True
    assert result["backup"] is not None
    assert [os.path.basename(p) for p in result["added"]] == ["a.mp3", "b.mp3"]
    assert result["removed"] == []
    assert result["errors"] == []
    assert db.commits == 1
    assert len(db.contents) == 2
    assert [s.Content.FolderPath for s in db.songs] == [str(music / "a.mp3"), str(music / "b.mp3")]

    (music / "b.mp3").unlink()
    plan = rekordbox_sync.plan_sync(db, str(music))
    assert [s["path"] for s in plan["remove"]] == [str(music / "b.mp3")]

    result = rekordbox_sync.apply_sync(db, plan, [], [plan["remove"][0]["song_id"], 12345])

    assert result["removed"] == [str(music / "b.mp3")]
    assert result["backup"] is None
    assert db.commits == 2
    assert len(db.songs) == 1


def test_apply_sync_collects_errors_and_skips_commit_when_nothing_changes(music, tmp_path):
    playlist = FakePlaylist(10, "My Mix")
    gone = FakeContent(2, str(tmp_path / "gone.mp3"), "Gone")
    db = FakeDB(str(tmp_path), playlists=[playlist], songs=[FakeSong(7, 10, gone)])
    db.fail_add_content = True
    db.fail_remove = True
    plan = rekordbox_sync.plan_sync(db, str(music))

    result = rekordbox_sync.apply_sync(db, plan, [str(music / "b.mp3")], [7])

    assert result["created"] is False
    assert result["added"] == []
    assert [e["error"] for e in result["errors"]] == ["unsupported file", "locked"]
    assert db.commits == 0

    untouched = rekordbox_sync.apply_sync(db, plan, [], [])
    assert untouched["errors"] == []
    assert db.commits == 0


def test_apply_sync_without_playlist_and_no_additions_removes_nothing(music, tmp_path):
    db = FakeDB(str(tmp_path))
    plan = rekordbox_sync.plan_sync(db, str(music))
    plan["remove"] = [{"song_id": 1, "path": "/x.mp3", "title": "", "artist": ""}]

    result = rekordbox_sync.apply_sync(db, plan, [], [1])

    assert result == {"backup": None, "created": False, "added": [], "removed": [], "errors": []}
