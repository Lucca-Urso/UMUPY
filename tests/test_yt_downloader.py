import json
import os
import platform
import shutil
import sys

import pytest

import yt_downloader


def test_directories(project_dir):
    assert yt_downloader.get_dependencies_directory() == str(project_dir / "Dependencies")
    assert yt_downloader.get_downloads_directory() == str(project_dir / "Downloads")
    assert os.path.isdir(project_dir / "Downloads")
    assert yt_downloader.get_fix_artwork_script().endswith("fix_artwork.py")
    assert len(yt_downloader.get_today().split("_")) == 2


def test_project_directory_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))

    assert yt_downloader.get_project_directory() == str(tmp_path / "UMUPY")
    assert yt_downloader.yt_dlp_command() == [sys.executable, "--yt-dlp"]


def test_project_directory_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert yt_downloader.get_project_directory().endswith("UMUPY")
    assert yt_downloader.yt_dlp_command() == [sys.executable, "-m", "yt_dlp"]


def test_find_ffmpeg_prefers_path(monkeypatch, project_dir):
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/ffmpeg")

    assert yt_downloader.find_ffmpeg() == "/usr/bin/ffmpeg"


def test_find_ffmpeg_falls_back_to_dependencies(monkeypatch, project_dir):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    dependencies = project_dir / "Dependencies"
    dependencies.mkdir()
    (dependencies / "ffmpeg.exe").write_bytes(b"")

    assert yt_downloader.find_ffmpeg() == str(dependencies / "ffmpeg.exe")


def test_find_ffmpeg_missing(monkeypatch, project_dir):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")

    assert yt_downloader.find_ffmpeg() is None


def test_find_cookies(project_dir):
    assert yt_downloader.find_cookies() is None
    assert yt_downloader.cookies_arguments() == []

    dependencies = project_dir / "Dependencies"
    dependencies.mkdir()
    (dependencies / "readme.txt").write_text("x")
    assert yt_downloader.find_cookies() is None

    (dependencies / "youtube_cookies.txt").write_text("x")
    assert yt_downloader.find_cookies() == str(dependencies / "youtube_cookies.txt")
    assert yt_downloader.cookies_arguments() == ["--cookies", str(dependencies / "youtube_cookies.txt")]

    if os.name == "posix":
        assert oct(os.stat(dependencies / "youtube_cookies.txt").st_mode & 0o777) == "0o600"


def test_find_cookies_ignores_chmod_failure(project_dir, monkeypatch):
    dependencies = project_dir / "Dependencies"
    dependencies.mkdir()
    (dependencies / "cookies.txt").write_text("x")
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "chmod", lambda *_: (_ for _ in ()).throw(OSError("ro")))

    assert yt_downloader.find_cookies() == str(dependencies / "cookies.txt")


def test_ask_yes_no(monkeypatch):
    answers = iter(["maybe", "Y", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert yt_downloader.ask_yes_no("?") is True
    assert yt_downloader.ask_yes_no("?") is False


def test_select_duplicate_scan_folders_without_folders(project_dir):
    assert yt_downloader.select_duplicate_scan_folders() == [str(project_dir / "Downloads")]


def test_select_duplicate_scan_folders_all(project_dir, monkeypatch):
    (project_dir / "Downloads" / "A").mkdir(parents=True)
    monkeypatch.setattr("builtins.input", lambda _: "1")

    assert yt_downloader.select_duplicate_scan_folders() == [str(project_dir / "Downloads")]


def test_select_duplicate_scan_folders_specific(project_dir, monkeypatch):
    downloads = project_dir / "Downloads"
    (downloads / "A").mkdir(parents=True)
    (downloads / "B").mkdir()
    monkeypatch.setattr("builtins.input", lambda _: "3, x, 9")

    assert yt_downloader.select_duplicate_scan_folders() == [str(downloads / "B")]


def test_build_library_index(make_mp3, tmp_path, sample_mp3_bytes, capsys):
    make_mp3("tagged", youtube_id="yt1")
    make_mp3("untagged")
    (tmp_path / "raw.mp3").write_bytes(sample_mp3_bytes)
    (tmp_path / "broken.mp3").write_bytes(b"garbage")
    (tmp_path / "ignore.txt").write_text("x")

    index = yt_downloader.build_library_index([str(tmp_path)])

    assert index == {"yt1": str(tmp_path / "tagged.mp3")}
    assert "Could not index" in capsys.readouterr().out


def test_detect_playlist(fake_run):
    fake_run.queue(type("R", (), {"stdout": "My List\n", "returncode": 0})())
    assert yt_downloader.detect_playlist("url", "/dir") == "My List"

    fake_run.queue(type("R", (), {"stdout": "NA\n", "returncode": 0})())
    assert yt_downloader.detect_playlist("url", "/dir") == ""

    fake_run.queue(type("R", (), {"stdout": "", "returncode": 0})())
    assert yt_downloader.detect_playlist("url", "/dir") == ""
    assert "--flat-playlist" in fake_run.last()


def test_resolve_output_directory_video(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(yt_downloader, "detect_playlist", lambda *_: "")

    directory, template = yt_downloader.resolve_output_directory("url", "/dir")

    assert directory == str(project_dir / "Downloads")
    assert template == "%(title)s.%(ext)s"
    assert "Content: Video" in capsys.readouterr().out


def test_resolve_output_directory_playlist(project_dir, monkeypatch):
    monkeypatch.setattr(yt_downloader, "detect_playlist", lambda *_: "Mix")
    monkeypatch.setattr(yt_downloader, "get_today", lambda: "01_01")

    directory, _ = yt_downloader.resolve_output_directory("url", "/dir")

    assert directory == str(project_dir / "Downloads" / "Mix_01_01")
    assert os.path.isdir(directory)


def video_json(video_id, title="T"):
    return json.dumps({"id": video_id, "title": title})


def test_extract_videos_chunk_parses_json_lines(fake_run):
    fake_run.queue(type("R", (), {"stdout": video_json("a") + "\nnot json\n" + video_json("b"), "returncode": 0})())

    videos = yt_downloader.extract_videos_chunk("url", "/dir", 1, 100)

    assert [v["id"] for v in videos] == ["a", "b"]
    assert videos[0]["url"] == "https://www.youtube.com/watch?v=a"
    assert "--playlist-start" in fake_run.last()


def test_extract_videos_paginates_until_short_chunk(monkeypatch, capsys):
    chunks = [
        [{"id": str(i), "title": "t", "url": "u"} for i in range(100)],
        [{"id": "100", "title": "t", "url": "u"}, {"id": "5", "title": "dup", "url": "u"}],
    ]
    monkeypatch.setattr(yt_downloader, "extract_videos_chunk", lambda *_: chunks.pop(0))

    videos = yt_downloader.extract_videos("url", "/dir")

    assert len(videos) == 101


def test_extract_videos_stops_when_only_duplicates(monkeypatch):
    chunks = [
        [{"id": str(i), "title": "t", "url": "u"} for i in range(100)],
        [{"id": "1", "title": "t", "url": "u"}],
    ]
    monkeypatch.setattr(yt_downloader, "extract_videos_chunk", lambda *_: chunks.pop(0))

    assert len(yt_downloader.extract_videos("url", "/dir")) == 100


def test_probe_url_error(fake_run):
    fake_run.queue(type("R", (), {"stdout": "abc\n", "stderr": "", "returncode": 0})())
    assert yt_downloader.probe_url_error("url", "/dir") is None

    fake_run.queue(type("R", (), {"stdout": "", "stderr": "WARNING: x\nERROR: bad url\n", "returncode": 1})())
    assert yt_downloader.probe_url_error("url", "/dir") == "ERROR: bad url"

    fake_run.queue(type("R", (), {"stdout": "", "stderr": "line1\nline2\nline3\nline4", "returncode": 1})())
    assert yt_downloader.probe_url_error("url", "/dir") == "line2 | line3 | line4"

    fake_run.queue(type("R", (), {"stdout": "", "stderr": "", "returncode": 1})())
    assert "no results" in yt_downloader.probe_url_error("url", "/dir")


def test_filter_pending_videos(capsys):
    videos = [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]

    pending = yt_downloader.filter_pending_videos(videos, {"a": "path"})

    assert pending == [{"id": "b", "title": "B"}]
    assert "[SKIPPED] A" in capsys.readouterr().out


def test_list_image_files_and_cleanup(tmp_path, capsys):
    assert yt_downloader.list_image_files(str(tmp_path / "missing")) == set()

    (tmp_path / "keep.jpg").write_bytes(b"")
    before = yt_downloader.list_image_files(str(tmp_path))
    (tmp_path / "new.webp").write_bytes(b"")
    (tmp_path / "song.mp3").write_bytes(b"")

    yt_downloader.remove_residual_thumbnails(str(tmp_path), before)

    assert sorted(os.listdir(tmp_path)) == ["keep.jpg", "song.mp3"]
    assert "Removed residual thumbnail" in capsys.readouterr().out


def test_remove_residual_thumbnails_handles_os_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "new.jpg").write_bytes(b"")
    monkeypatch.setattr(os, "remove", lambda _: (_ for _ in ()).throw(OSError("locked")))

    yt_downloader.remove_residual_thumbnails(str(tmp_path), set())

    assert "Could not remove residual thumbnail" in capsys.readouterr().out


VIDEO = {"id": "vid1", "title": "Song", "url": "https://www.youtube.com/watch?v=vid1"}


def test_download_video_success_with_capture(fake_run, tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    result = yt_downloader.download_video(
        VIDEO, str(tmp_path), "%(title)s.%(ext)s", "/dir", "/bin/ffmpeg", capture=True
    )

    command = fake_run.last()
    assert result == (0, None)
    assert "--extract-audio" in command
    assert command[command.index("--ffmpeg-location") + 1] == "/bin/ffmpeg"
    assert "youtube:player_client=default,web_embedded" in command
    assert "fix_artwork.py" in command[command.index("--exec") + 1]
    assert command[-1] == VIDEO["url"]


def test_download_video_passes_spotify_id_and_frozen_exec(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    yt_downloader.download_video(
        {**VIDEO, "spotify_id": "sp9"}, str(tmp_path), "%(title)s.%(ext)s", "/dir", "/bin/ffmpeg"
    )

    exec_argument = fake_run.last()[fake_run.last().index("--exec") + 1]
    assert "--fix-artwork" in exec_argument
    assert exec_argument.endswith(" sp9")


def test_download_video_drops_unsafe_spotify_id(fake_run, tmp_path):
    yt_downloader.download_video(
        {**VIDEO, "spotify_id": "abc; rm -rf /"}, str(tmp_path), "%(title)s.%(ext)s", "/dir", "/bin/ffmpeg"
    )

    exec_argument = fake_run.last()[fake_run.last().index("--exec") + 1]
    assert "rm -rf" not in exec_argument
    assert exec_argument.endswith("%(id)q")


def test_is_safe_track_id():
    assert yt_downloader.is_safe_track_id("3n3Ppam7vgaVa1iaRUc9Lp") is True
    assert yt_downloader.is_safe_track_id("dQw4w9WgXcQ") is True
    assert yt_downloader.is_safe_track_id("") is False
    assert yt_downloader.is_safe_track_id(None) is False
    assert yt_downloader.is_safe_track_id(123) is False
    assert yt_downloader.is_safe_track_id("a b") is False
    assert yt_downloader.is_safe_track_id("x" * 65) is False


def test_download_video_failure_reports_error_and_cleans(fake_run, tmp_path, monkeypatch):
    def fail(command):
        (tmp_path / "Song.jpg").write_bytes(b"")
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "WARNING: x\nERROR: 403 Forbidden"})()

    fake_run.queue(fail)

    code, error = yt_downloader.download_video(
        VIDEO, str(tmp_path), "%(title)s.%(ext)s", "/dir", "/bin/ffmpeg", capture=True
    )

    assert code == 1
    assert error == "ERROR: 403 Forbidden"
    assert not (tmp_path / "Song.jpg").exists()


def test_download_video_failure_without_error_lines(fake_run, tmp_path):
    fake_run.queue(type("R", (), {"returncode": 2, "stdout": "", "stderr": ""})())

    code, error = yt_downloader.download_video(
        VIDEO, str(tmp_path), "%(title)s.%(ext)s", "/dir", "/bin/ffmpeg", capture=True
    )

    assert code == 2
    assert error == "yt-dlp exited with code 2"


def test_download_video_without_capture_returns_code(fake_run, tmp_path):
    fake_run.queue(type("R", (), {"returncode": 1})())

    assert yt_downloader.download_video(VIDEO, str(tmp_path), "%(title)s.%(ext)s", "/dir", "/bin/ffmpeg") == 1


def test_process_download_exits_without_ffmpeg(monkeypatch, capsys):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: "")

    with pytest.raises(SystemExit):
        yt_downloader.process_download()

    assert "FFmpeg not found" in capsys.readouterr().out


def test_process_download_full_flow(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(yt_downloader, "select_duplicate_scan_folders", lambda: ["/scan"])
    monkeypatch.setattr(yt_downloader, "build_library_index", lambda _: {"dup": "x"})
    monkeypatch.setattr(yt_downloader, "resolve_output_directory", lambda *_: (str(project_dir), "%(title)s.%(ext)s"))
    monkeypatch.setattr(
        yt_downloader,
        "extract_videos",
        lambda *_: [
            {"id": "dup", "title": "Dup", "url": "u"},
            {"id": "ok", "title": "Good", "url": "u1"},
            {"id": "bad", "title": "Bad", "url": "u2"},
        ],
    )
    monkeypatch.setattr(yt_downloader, "download_video", lambda video, *_: 0 if video["id"] == "ok" else 1)

    answers = iter(["y", "", "https://yt", "n", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    yt_downloader.process_download()

    out = capsys.readouterr().out
    assert "[ERROR] URL not provided." in out
    assert "[OK] 1/2 musics downloaded." in out
    assert "1 download(s) failed" in out


def test_process_download_nothing_to_download(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(yt_downloader, "resolve_output_directory", lambda *_: (str(project_dir), "t"))
    monkeypatch.setattr(yt_downloader, "extract_videos", lambda *_: [])
    answers = iter(["n", "https://yt", "n", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    yt_downloader.process_download()

    assert "Nothing to download" in capsys.readouterr().out


def test_process_download_scan_with_no_folders(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(yt_downloader, "find_ffmpeg", lambda: "/bin/ffmpeg")
    monkeypatch.setattr(yt_downloader, "select_duplicate_scan_folders", lambda: [])
    monkeypatch.setattr(yt_downloader, "resolve_output_directory", lambda *_: (str(project_dir), "t"))
    monkeypatch.setattr(yt_downloader, "extract_videos", lambda *_: [])
    answers = iter(["y", "https://yt", "n", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    yt_downloader.process_download()

    assert "Nothing to download" in capsys.readouterr().out


def test_main_calls_process_download(monkeypatch):
    called = []
    monkeypatch.setattr(yt_downloader, "process_download", lambda: called.append(True))

    yt_downloader.main()

    assert called == [True]
