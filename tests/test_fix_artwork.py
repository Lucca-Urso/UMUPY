import io
import os
import sys

import pytest
from mutagen.id3 import APIC
from mutagen.mp3 import MP3
from PIL import Image

import fix_artwork


def make_image(path, size=(1200, 800), mode="RGB", fmt="PNG"):
    image = Image.new(mode, size, color=(255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0))
    image.save(path, format=fmt)
    return path


def read_apic(path):
    audio = MP3(path)
    return audio.tags.getall("APIC")


def read_txxx(path, desc):
    audio = MP3(path)
    frames = [frame for frame in audio.tags.getall("TXXX") if frame.desc == desc]
    return frames[0].text[0] if frames else None


def test_crop_to_square_centers_the_crop():
    image = Image.new("RGB", (300, 100))

    cropped = fix_artwork.crop_to_square(image)

    assert cropped.size == (100, 100)


def test_process_thumbnail_produces_800px_jpeg():
    image = Image.new("RGBA", (1000, 500))

    output = fix_artwork.process_thumbnail(image)
    result = Image.open(io.BytesIO(output.getvalue()))

    assert result.format == "JPEG"
    assert result.size == (800, 800)
    assert result.info["dpi"][0] == 300


def test_build_thumbnail_index_only_lists_images(tmp_path):
    make_image(tmp_path / "Song.jpg", fmt="JPEG")
    make_image(tmp_path / "Other.webp", fmt="WEBP")
    (tmp_path / "notes.txt").write_text("x")

    index = fix_artwork.build_thumbnail_index(str(tmp_path))

    assert set(index) == {"song", "other"}


def test_find_thumbnail_strategies():
    index = {
        "song a": "/a.jpg",
        "01 - song b": "/b.jpg",
        "song c extended mix": "/c.jpg",
    }

    assert fix_artwork.find_thumbnail("Song A", index) == "/a.jpg"
    assert fix_artwork.find_thumbnail("02 - song a", index) == "/a.jpg"
    assert fix_artwork.find_thumbnail("song b", index) == "/b.jpg"
    assert fix_artwork.find_thumbnail("song c extended mi", index) == "/c.jpg"
    assert fix_artwork.find_thumbnail("completely different", index) is None


def test_embed_metadata_writes_apic_and_ids(make_mp3):
    path = make_mp3("track", youtube_id="old")

    fix_artwork.embed_metadata(path, b"jpegdata", {"YOUTUBE_ID": "yt123", "SPOTIFY_ID": "sp456", "SOUNDCLOUD_ID": None})

    assert len(read_apic(path)) == 1
    assert read_apic(path)[0].data == b"jpegdata"
    assert read_txxx(path, "YOUTUBE_ID") == "yt123"
    assert read_txxx(path, "SPOTIFY_ID") == "sp456"
    assert read_txxx(path, "SOUNDCLOUD_ID") is None


def test_embed_metadata_replaces_previous_provider_tags(make_mp3):
    path = make_mp3("track", youtube_id="old", spotify_id="oldsp")

    fix_artwork.embed_metadata(path, b"img", {"SOUNDCLOUD_ID": 123})

    assert read_txxx(path, "YOUTUBE_ID") is None
    assert read_txxx(path, "SPOTIFY_ID") is None
    assert read_txxx(path, "SOUNDCLOUD_ID") == "123"


def test_embed_metadata_on_untagged_file(tmp_path, sample_mp3_bytes):
    path = tmp_path / "raw.mp3"
    path.write_bytes(sample_mp3_bytes)

    fix_artwork.embed_metadata(str(path), b"img")

    assert len(read_apic(str(path))) == 1
    assert read_txxx(str(path), "YOUTUBE_ID") is None


def test_fix_audio_artwork_uses_thumbnail_and_removes_it(make_mp3, tmp_path, capsys):
    path = make_mp3("My Song")
    thumb = make_image(tmp_path / "My Song.png")

    fix_artwork.fix_audio_artwork(path, {"YOUTUBE_ID": "yt1", "SPOTIFY_ID": "sp1"})

    assert not os.path.exists(thumb)
    assert Image.open(io.BytesIO(read_apic(path)[0].data)).size == (800, 800)
    assert read_txxx(path, "YOUTUBE_ID") == "yt1"
    assert read_txxx(path, "SPOTIFY_ID") == "sp1"
    assert "[OK] Artwork embedded." in capsys.readouterr().out


def test_fix_audio_artwork_rebuilds_from_existing_apic(make_mp3, capsys):
    path = make_mp3("Tagged")
    buffer = io.BytesIO()
    Image.new("RGB", (500, 300)).save(buffer, format="PNG")
    audio = MP3(path)
    audio.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="", data=buffer.getvalue()))
    audio.save(v2_version=3)

    fix_artwork.fix_audio_artwork(path, {"YOUTUBE_ID": "yt2"})

    assert Image.open(io.BytesIO(read_apic(path)[0].data)).size == (800, 800)
    assert read_txxx(path, "YOUTUBE_ID") == "yt2"
    assert "rebuilt from existing APIC" in capsys.readouterr().out


def test_fix_audio_artwork_without_any_artwork_still_writes_tags(make_mp3, capsys):
    path = make_mp3("Bare")

    fix_artwork.fix_audio_artwork(path, {"YOUTUBE_ID": "yt7"})

    assert read_apic(path) == []
    assert read_txxx(path, "YOUTUBE_ID") == "yt7"
    assert "No artwork found. Tags written without artwork." in capsys.readouterr().out


def test_fix_audio_artwork_missing_file(tmp_path, capsys):
    fix_artwork.fix_audio_artwork(str(tmp_path / "nope.mp3"))

    assert "[ERROR] File not found" in capsys.readouterr().out


def test_fix_audio_artwork_handles_processing_error(make_mp3, tmp_path, capsys):
    path = make_mp3("Broken")
    (tmp_path / "Broken.jpg").write_bytes(b"not an image")

    fix_artwork.fix_audio_artwork(path)

    assert "[ERROR] Failed to process artwork" in capsys.readouterr().out


def test_fix_audio_artwork_warns_when_thumbnail_cannot_be_removed(make_mp3, tmp_path, monkeypatch, capsys):
    path = make_mp3("Locked")
    make_image(tmp_path / "Locked.png")
    monkeypatch.setattr(os, "remove", lambda _: (_ for _ in ()).throw(OSError("busy")))

    fix_artwork.fix_audio_artwork(path)

    assert "Could not remove thumbnail" in capsys.readouterr().out


def test_parse_arguments():
    assert fix_artwork.parse_arguments([]) is None
    assert fix_artwork.parse_arguments(["a.mp3"]) == ("a.mp3", {})
    assert fix_artwork.parse_arguments(["a.mp3", "yt"]) == ("a.mp3", {"YOUTUBE_ID": "yt"})
    assert fix_artwork.parse_arguments(["a.mp3", "yt", "sp"]) == ("a.mp3", {"YOUTUBE_ID": "yt", "SPOTIFY_ID": "sp"})
    assert fix_artwork.parse_arguments(["a.mp3", "yt", "sp", "extra"]) is None
    assert fix_artwork.parse_arguments(["a.mp3", "SOUNDCLOUD_ID", "123", "SPOTIFY_ID", "sp"]) == (
        "a.mp3", {"SOUNDCLOUD_ID": "123", "SPOTIFY_ID": "sp"}
    )
    assert fix_artwork.parse_arguments(["a.mp3", "SOUNDCLOUD_ID"]) is None


def test_main_dispatches_parsed_tags(monkeypatch):
    received = []
    monkeypatch.setattr(fix_artwork, "fix_audio_artwork", lambda *args: received.append(args))

    monkeypatch.setattr(sys, "argv", ["fix", "a.mp3", "yt", "sp"])
    fix_artwork.main()
    monkeypatch.setattr(sys, "argv", ["fix", "a.mp3", "SOUNDCLOUD_ID", "9"])
    fix_artwork.main()
    monkeypatch.setattr(sys, "argv", ["fix", "a.mp3"])
    fix_artwork.main()

    assert received == [
        ("a.mp3", {"YOUTUBE_ID": "yt", "SPOTIFY_ID": "sp"}),
        ("a.mp3", {"SOUNDCLOUD_ID": "9"}),
        ("a.mp3", {}),
    ]


def test_main_with_invalid_arguments_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["fix"])

    with pytest.raises(SystemExit) as exit_info:
        fix_artwork.main()

    assert exit_info.value.code == 1
    assert "Usage" in capsys.readouterr().out
