import os
import sys

import pytest

import spotify_converter
import sync_playlists
import yt_downloader


def track(spotify_id, title, artists=("Artist",)):
    return {"spotify_id": spotify_id, "title": title, "artists": list(artists), "duration": 200}


def test_build_local_index_reads_tags(make_mp3, tmp_path, sample_mp3_bytes):
    make_mp3("full", youtube_id="yt1", spotify_id="sp1", title="Song", artist="Artist")
    make_mp3("bare")
    (tmp_path / "broken.mp3").write_bytes(b"x")
    (tmp_path / "skip.txt").write_text("x")

    files = sorted(sync_playlists.build_local_index(str(tmp_path)), key=lambda f: f["filename"])

    assert [f["filename"] for f in files] == ["bare", "broken", "full"]
    full = files[2]
    assert full["youtube_id"] == "yt1"
    assert full["spotify_id"] == "sp1"
    assert full["title"] == "Song"
    assert full["artist"] == "Artist"
    assert files[1]["title"] == ""


def local(filename, spotify_id=None, youtube_id=None, title="", artist=""):
    return {
        "path": f"/music/{filename}.mp3",
        "filename": filename,
        "title": title,
        "artist": artist,
        "spotify_id": spotify_id,
        "youtube_id": youtube_id,
    }


def test_compare_playlist_with_folder():
    tracks = [
        track("s1", "Exact By Id"),
        track("s2", "Fuzzy Title Match", artists=("Cool Artist",)),
        track("s3", "Missing Track"),
    ]
    files = [
        local("whatever", spotify_id="s1"),
        local("Cool Artist - Fuzzy Title Match"),
        local("Orphan Song", title="Nothing Alike", artist="Nobody"),
    ]

    matched, missing, orphans = sync_playlists.compare_playlist_with_folder(tracks, files)

    assert [(t["spotify_id"], f["filename"]) for t, f in matched] == [
        ("s1", "whatever"),
        ("s2", "Cool Artist - Fuzzy Title Match"),
    ]
    assert [t["spotify_id"] for t in missing] == ["s3"]
    assert [f["filename"] for f in orphans] == ["Orphan Song"]


def test_compare_skips_id_match_already_consumed():
    tracks = [track("s1", "Song"), track("s1", "Song")]
    files = [local("song", spotify_id="s1")]

    matched, missing, orphans = sync_playlists.compare_playlist_with_folder(tracks, files)

    assert len(matched) == 1
    assert len(missing) == 1
    assert orphans == []


def test_reconcile_missing_by_provider_id():
    orphans = [local("a", youtube_id="yt1"), local("b", youtube_id="yt2"), {**local("c"), "soundcloud_id": "sc1"}]
    entries = [
        {"spotify_id": "s1", "video": {"id": "yt1"}},
        {"spotify_id": "s2", "video": {"id": "nope"}},
        {"spotify_id": "s3", "video": None},
        {"spotify_id": "s4", "video": {"id": "sc1", "source": "soundcloud"}},
        {"spotify_id": "s5", "video": {"id": "yt2", "source": "soundcloud"}},
    ]

    still_missing, reconciled = sync_playlists.reconcile_missing(entries, orphans)

    assert [e["spotify_id"] for e in still_missing] == ["s2", "s3", "s5"]
    assert [(e["spotify_id"], f["filename"]) for e, f in reconciled] == [("s1", "a"), ("s4", "c")]
    assert [f["filename"] for f in orphans] == ["b"]


def test_embed_and_heal_spotify_ids(make_mp3, tmp_path, sample_mp3_bytes):
    tagged = make_mp3("tagged", spotify_id="old")
    untagged = make_mp3("untagged")
    raw = tmp_path / "raw.mp3"
    raw.write_bytes(sample_mp3_bytes)
    broken = tmp_path / "broken.mp3"
    broken.write_bytes(b"x")

    pairs = [
        (track("s1", "A"), {"path": tagged, "spotify_id": "old"}),
        (track("s2", "B"), {"path": untagged, "spotify_id": None}),
        (track("s3", "C"), {"path": str(raw), "spotify_id": None}),
        (track("s4", "D"), {"path": str(broken), "spotify_id": None}),
    ]

    healed = sync_playlists.heal_spotify_ids(pairs)

    assert healed == 2
    assert pairs[1][1]["spotify_id"] == "s2"
    index = {f["filename"]: f["spotify_id"] for f in sync_playlists.build_local_index(str(tmp_path))}
    assert index["tagged"] == "old"
    assert index["untagged"] == "s2"
    assert index["raw"] == "s3"


def test_delete_files(tmp_path):
    existing = tmp_path / "a.mp3"
    existing.write_bytes(b"")

    results = sync_playlists.delete_files([str(existing), str(tmp_path / "missing.mp3")])

    assert results[0]["ok"] is True
    assert results[1]["ok"] is False
    assert "missing" in results[1]["error"]
    assert not existing.exists()


def test_delete_files_refuses_paths_outside_folder(tmp_path):
    folder = tmp_path / "synced"
    folder.mkdir()
    inside = folder / "a.mp3"
    inside.write_bytes(b"")
    outside = tmp_path / "outside.mp3"
    outside.write_bytes(b"")
    traversal = folder / ".." / "outside.mp3"

    results = sync_playlists.delete_files([str(inside), str(outside), str(traversal), str(folder)], str(folder))

    assert [r["ok"] for r in results] == [True, False, False, False]
    assert all("outside the synced folder" in r["error"] for r in results[1:])
    assert not inside.exists()
    assert outside.exists()


def test_delete_files_with_empty_folder_refuses_everything(tmp_path):
    target = tmp_path / "a.mp3"
    target.write_bytes(b"")

    results = sync_playlists.delete_files([str(target)], "")

    assert results[0]["ok"] is False
    assert target.exists()


def test_is_inside_folder_handles_invalid_paths(monkeypatch):
    monkeypatch.setattr(os.path, "commonpath", lambda _: (_ for _ in ()).throw(ValueError("mixed drives")))

    assert sync_playlists.is_inside_folder("C:/a", "D:/b") is False


def prepare_main(monkeypatch, tmp_path, tracks, local_files, argv=None):
    monkeypatch.setattr(sys, "argv", argv or ["prog", "https://open.spotify.com/playlist/x", str(tmp_path)])
    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: "spotify")
    monkeypatch.setattr(spotify_converter, "fetch_playlist", lambda *_: {"name": "Mix", "tracks": tracks})
    monkeypatch.setattr(spotify_converter, "open_ytmusic", lambda: "yt")
    monkeypatch.setattr(sync_playlists, "build_local_index", lambda _: local_files)
    monkeypatch.setattr(sync_playlists, "heal_spotify_ids", lambda _: 1)


def test_main_folder_not_found(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["prog"])
    answers = iter(["https://open.spotify.com/playlist/x", str(tmp_path / "nope")])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    with pytest.raises(SystemExit):
        sync_playlists.main()

    assert "Folder not found" in capsys.readouterr().out


def test_main_everything_in_sync(project_dir, monkeypatch, tmp_path, capsys):
    prepare_main(monkeypatch, tmp_path, [track("s1", "A")], [local("a", spotify_id="s1")])

    sync_playlists.main()

    out = capsys.readouterr().out
    assert "Tagged 1 file(s)" in out
    assert "1 in sync, 0 missing locally, 0 local orphans" in out
    assert "[OK] Sync finished." in out


def test_main_full_flow_with_deletes_and_downloads(project_dir, monkeypatch, tmp_path, capsys):
    orphan_path = tmp_path / "orphan.mp3"
    orphan_path.write_bytes(b"")
    reconciled_path = tmp_path / "reconciled.mp3"
    reconciled_path.write_bytes(b"x")

    tracks = [track("s1", "Missing Found"), track("s2", "Missing Not Found"), track("s3", "Zebra Quantum Echo")]
    local_files = [
        {**local("orphan"), "path": str(orphan_path)},
        {**local("oldname", youtube_id="ytR"), "path": str(reconciled_path)},
    ]
    prepare_main(monkeypatch, tmp_path, tracks, local_files)

    found = [{"id": "ytF", "title": "Found", "url": "u", "spotify_id": "s1"},
             {"id": "ytR", "title": "Rec", "url": "u", "spotify_id": "s3"}]
    monkeypatch.setattr(spotify_converter, "convert_tracks", lambda *_: (found, []))
    monkeypatch.setattr(sync_playlists, "embed_spotify_id", lambda *_: (_ for _ in ()).throw(OSError("ro")))
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    downloads = []
    monkeypatch.setattr(yt_downloader, "download_video", lambda video, *_: downloads.append(video["id"]) or 1)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    sync_playlists.main()

    out = capsys.readouterr().out
    assert "Reconciled by YOUTUBE_ID: oldname" in out
    assert "1 in sync, 2 missing locally, 1 local orphans" in out
    assert "Orphan files deleted" in out
    assert not orphan_path.exists()
    assert "1 track(s) not found on YouTube Music" in out
    assert downloads == ["ytF"]


def test_main_declines_deletion_and_download(project_dir, monkeypatch, tmp_path, capsys):
    tracks = [track("s1", "Missing Found")]
    prepare_main(monkeypatch, tmp_path, tracks, [local("orphan")])
    monkeypatch.setattr(
        spotify_converter, "convert_tracks",
        lambda *_: ([{"id": "ytF", "title": "Found", "url": "u", "spotify_id": "s1"}], []),
    )
    monkeypatch.setattr("builtins.input", lambda _: "n")

    sync_playlists.main()

    out = capsys.readouterr().out
    assert "Local files not in the playlist" in out
    assert "Tracks missing locally" in out
    assert "Orphan files deleted" not in out
