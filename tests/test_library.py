import library


def test_read_file_collects_tags_and_metadata(make_mp3):
    path = make_mp3("full", youtube_id="yt1", spotify_id="sp1", title="Song", artist="Artist")

    entry, ok = library.read_file(path)

    assert ok is True
    assert entry["filename"] == "full"
    assert entry["youtube_id"] == "yt1"
    assert entry["spotify_id"] == "sp1"
    assert entry["soundcloud_id"] is None
    assert entry["title"] == "Song"
    assert entry["artist"] == "Artist"


def test_read_file_handles_untagged_and_broken(tmp_path, sample_mp3_bytes):
    raw = tmp_path / "raw.mp3"
    raw.write_bytes(sample_mp3_bytes)
    broken = tmp_path / "broken.mp3"
    broken.write_bytes(b"nope")

    raw_entry, raw_ok = library.read_file(str(raw))
    broken_entry, broken_ok = library.read_file(str(broken))

    assert raw_ok is True
    assert raw_entry["title"] == ""
    assert broken_ok is False
    assert broken_entry["filename"] == "broken"


def test_read_file_without_id3_tags(monkeypatch):
    import mutagen.mp3

    monkeypatch.setattr(mutagen.mp3, "MP3", lambda path: type("Audio", (), {"tags": None})())

    entry, ok = library.read_file("/music/plain.mp3")

    assert ok is True
    assert entry["filename"] == "plain"
    assert entry["youtube_id"] is None


def test_read_file_soundcloud_tag_and_unknown_txxx(make_mp3):
    from mutagen.id3 import TXXX
    from mutagen.mp3 import MP3

    path = make_mp3("sc")
    audio = MP3(path)
    audio.tags.add(TXXX(encoding=3, desc="SOUNDCLOUD_ID", text=["sc9"]))
    audio.tags.add(TXXX(encoding=3, desc="OTHER", text=["x"]))
    audio.tags.add(TXXX(encoding=3, desc="SPOTIFY_ID", text=[]))
    audio.save(v2_version=3)

    entry, _ = library.read_file(path)

    assert entry["soundcloud_id"] == "sc9"
    assert entry["spotify_id"] is None


def test_build_index_reads_each_file_once(make_mp3, tmp_path, monkeypatch):
    make_mp3("a", youtube_id="yt1", spotify_id="sp1")
    make_mp3("b", youtube_id="yt2", directory=str(tmp_path / "sub"))
    make_mp3("c", youtube_id="yt1")
    (tmp_path / "broken.mp3").write_bytes(b"x")
    (tmp_path / "note.txt").write_text("x")
    reads = []
    original = library.read_file
    monkeypatch.setattr(library, "read_file", lambda path: reads.append(path) or original(path))
    errors = []

    index = library.build_index([str(tmp_path)], on_error=errors.append)

    assert len(index) == 4
    assert len(reads) == 4
    assert errors == [str(tmp_path / "broken.mp3")]
    assert index.contains("youtube", "yt1") is True
    assert index.path_for("youtube", "yt1") == str(tmp_path / "a.mp3")
    assert index.contains("youtube", "yt2") is True
    assert index.contains("spotify", "sp1") is True
    assert index.contains("spotify", "yt1") is False
    assert index.contains("soundcloud", "yt1") is False
    assert index.contains("unknown", "yt1") is False
    assert index.contains("youtube", None) is False


def test_is_duplicate_uses_only_the_track_source():
    index = library.LibraryIndex([
        {"path": "/a.mp3", "youtube_id": "yt1", "spotify_id": None, "soundcloud_id": None},
        {"path": "/b.mp3", "youtube_id": None, "spotify_id": "sp1", "soundcloud_id": "sc1"},
    ])

    assert index.is_duplicate({"source": "youtube", "id": "yt1"}) is True
    assert index.is_duplicate({"source": "spotify", "id": "yt1"}) is False
    assert index.is_duplicate({"source": "spotify", "id": "sp1"}) is True
    assert index.is_duplicate({"source": "soundcloud", "id": "sc1"}) is True
    assert index.is_duplicate({}) is False
    assert len(library.LibraryIndex()) == 0
