import json
import os
import platform
import subprocess
import sys
from types import SimpleNamespace

import settings
import spotify_converter
import yt_downloader
from api import setup as setup_api


def test_settings_roundtrip_and_defaults(project_dir):
    assert settings.load() == {"cookies_browser": None}

    saved = settings.save(cookies_browser="firefox", ignored="x")

    assert saved == {"cookies_browser": "firefox"}
    assert settings.load()["cookies_browser"] == "firefox"
    assert json.load(open(settings.get_settings_path()))["cookies_browser"] == "firefox"

    with open(settings.get_settings_path(), "w") as handle:
        handle.write("not json")

    assert settings.load() == {"cookies_browser": None}


def test_cookie_arguments_prefer_browser_setting(project_dir):
    dependencies = project_dir / "Dependencies"
    dependencies.mkdir()
    (dependencies / "cookies.txt").write_text("x")

    assert yt_downloader.cookies_arguments() == ["--cookies", str(dependencies / "cookies.txt")]

    settings.save(cookies_browser="firefox")

    assert yt_downloader.cookies_arguments() == ["--cookies-from-browser", "firefox"]
    assert yt_downloader.common_arguments()[:2] == ["--cookies-from-browser", "firefox"]


def test_bundled_binaries_take_precedence(project_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(yt_downloader.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "ffmpeg").write_bytes(b"")
    (tmp_path / "bin" / "deno").write_bytes(b"")

    assert yt_downloader.find_ffmpeg() == str(tmp_path / "bin" / "ffmpeg")
    assert yt_downloader.find_deno() == str(tmp_path / "bin" / "deno")
    assert yt_downloader.deno_arguments() == []

    monkeypatch.setattr(yt_downloader.shutil, "which", lambda name: None)
    assert yt_downloader.deno_arguments() == ["--js-runtimes", f"deno:{tmp_path / 'bin' / 'deno'}"]

    monkeypatch.delattr(sys, "frozen", raising=False)
    assert yt_downloader.bundled_binary_directories()[-1].endswith("bin")

    monkeypatch.setattr(yt_downloader, "bundled_binary_directories", lambda: [str(tmp_path / "empty")])
    assert yt_downloader.find_ffmpeg() is None
    assert yt_downloader.find_deno() is None
    assert yt_downloader.deno_arguments() == []


def test_available_browsers_per_platform(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    mac = setup_api.available_browsers()
    assert [b["id"] for b in mac[:2]] == ["safari", "firefox"]
    assert all(b["note"] for b in mac if b["id"] in setup_api.CHROME_FAMILY)

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    win = setup_api.available_browsers()
    assert "safari" not in [b["id"] for b in win]
    assert [b["id"] for b in win][0] == "firefox"
    chrome = next(b for b in win if b["id"] == "chrome")
    assert chrome["recommended"] is False and "Quit the browser" in chrome["note"]
    assert next(b for b in win if b["id"] == "edge")["recommended"] is False


def test_describe_cookie_test():
    ok = setup_api.describe_cookie_test("firefox", 0, "Extracted 10 cookies from firefox\n[debug] [youtube] Found YouTube account cookies\nid")
    assert ok == {"ok": True, "detail": "Extracted 10 cookies from firefox. YouTube login found."}

    no_login = setup_api.describe_cookie_test("safari", 0, "Extracted 3 cookies from safari\nid")
    assert no_login["ok"] is False and "no YouTube login" in no_login["error"]

    missing = setup_api.describe_cookie_test("opera", 1, "ERROR: could not find opera cookies database")
    assert missing["error"].endswith("Is that browser installed on this computer?")

    zero = setup_api.describe_cookie_test("firefox", 0, "Extracted 0 cookies from firefox")
    assert zero["ok"] is False

    empty = setup_api.describe_cookie_test("firefox", 1, "")
    assert empty["error"] == "Cookie extraction failed."


def test_describe_cookie_test_windows_hints(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")

    locked = setup_api.describe_cookie_test(
        "chrome", 1, "ERROR: Could not copy Chrome cookie database. See https://github.com/yt-dlp/yt-dlp/issues/7271 for more info"
    )
    assert locked["error"].startswith("ERROR: Could not copy Chrome cookie database.")
    assert "Quit it completely" in locked["error"]
    assert "github.com" not in locked["error"]

    encrypted = setup_api.describe_cookie_test("edge", 1, "ERROR: Failed to decrypt with DPAPI")
    assert "paste the cookies manually" in encrypted["error"]

    generic = setup_api.describe_cookie_test("brave", 1, "ERROR: something odd")
    assert "Firefox is the safest choice" in generic["error"]


def test_setup_status(api, project_dir, monkeypatch):
    monkeypatch.setattr(yt_downloader, "find_deno", lambda: None)

    status = api.setup_status()

    assert status["spotify"]["ready"] is False
    assert status["ffmpeg"] == {"ok": True, "path": "/bin/ffmpeg"}
    assert status["deno"] == {"ok": False, "path": None}
    assert status["cookies"]["browser"] is None
    assert status["data_directory"] == str(project_dir)


def test_save_and_test_spotify_credentials(api, project_dir, monkeypatch):
    assert api.save_spotify_credentials("", "x") == {"error": "Both Client ID and Client Secret are required."}

    token_cache = project_dir / "Dependencies" / ".spotify_token_cache"
    token_cache.parent.mkdir()
    token_cache.write_text("old")

    result = api.save_spotify_credentials(" id ", " secret ")

    assert result["ok"] is True
    saved = json.load(open(result["path"]))
    assert saved["client_id"] == "id"
    assert saved["client_secret"] == "secret"
    assert not token_cache.exists()

    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: SimpleNamespace(current_user=lambda: {"id": "me"}))
    assert api.test_spotify_credentials() == {"ok": True}

    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: (_ for _ in ()).throw(SystemExit(1)))
    assert api.test_spotify_credentials()["error"].startswith("Credentials file missing")

    monkeypatch.setattr(spotify_converter, "open_spotify", lambda: (_ for _ in ()).throw(RuntimeError("invalid client")))
    assert api.test_spotify_credentials() == {"ok": False, "error": "invalid client"}


def test_set_and_test_cookies_browser(api, project_dir, monkeypatch):
    assert api.set_cookies_browser("netscape") == {"error": "Unknown browser: netscape"}
    assert api.set_cookies_browser(" Firefox ") == {"ok": True, "browser": "firefox"}
    assert settings.load()["cookies_browser"] == "firefox"
    assert api.set_cookies_browser("") == {"ok": True, "browser": None}

    assert api.test_cookies() == {"ok": False, "error": "Choose a browser first."}

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="jNQXAC9IVRw\n", stderr="Extracted 5 cookies from firefox\n[debug] [youtube] Found YouTube account cookies\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert api.test_cookies("firefox")["ok"] is True
    assert "--cookies-from-browser" in calls[0] and "firefox" in calls[0]

    settings.save(cookies_browser="safari")
    assert api.test_cookies()["ok"] is True
    assert calls[1][calls[1].index("--cookies-from-browser") + 1] == "safari"


def test_open_data_directory(api, project_dir, monkeypatch):
    opened = []
    monkeypatch.setattr("api.base.open_in_file_manager", lambda directory: opened.append(directory) or directory)

    assert api.open_data_directory() == str(project_dir)
    assert opened == [str(project_dir)]


NETSCAPE = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n.google.com\tTRUE\t/\tTRUE\t0\tHSID\n"


def test_parse_cookie_text_formats():
    rows = setup_api.parse_cookie_text(NETSCAPE)
    assert rows == [[".youtube.com", "TRUE", "/", "TRUE", "0", "SID", "abc"], [".google.com", "TRUE", "/", "TRUE", "0", "HSID", ""]]

    header = setup_api.parse_cookie_text("Cookie: SID=abc; HSID=d=ef; junk")
    assert [(r[5], r[6]) for r in header] == [("SID", "abc"), ("HSID", "d=ef")]
    assert all(r[0] == ".youtube.com" for r in header)

    assert setup_api.parse_cookie_text("") is None
    assert setup_api.parse_cookie_text("nothing here") is None
    assert setup_api.parse_cookie_text("a\tb\tc\n") is None
    assert setup_api.cookies_to_netscape(header).startswith(setup_api.NETSCAPE_HEADER)


def test_save_cookies_text_validates_and_stores(api, project_dir, monkeypatch):
    assert "does not look like cookies" in api.save_cookies_text("oops")["error"]
    assert "No youtube.com cookies" in api.save_cookies_text(".example.com\tTRUE\t/\tTRUE\t0\tA\tb")["error"]

    outputs = iter([
        SimpleNamespace(returncode=0, stdout="id\n", stderr="[debug] [youtube] Found YouTube account cookies\n"),
        SimpleNamespace(returncode=0, stdout="id\n", stderr="nothing about login\n"),
        SimpleNamespace(returncode=1, stdout="", stderr="ERROR: bad cookie file\n"),
    ])
    commands = []
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: commands.append(command) or next(outputs))
    settings.save(cookies_browser="firefox")

    result = api.save_cookies_text(NETSCAPE)

    assert result["ok"] is True
    assert result["detail"].startswith("2 cookies saved")
    assert os.path.isfile(result["path"])
    assert "--cookies" in commands[0] and result["path"] in commands[0]
    assert settings.load()["cookies_browser"] is None
    assert yt_downloader.cookies_arguments() == ["--cookies", result["path"]]
    assert open(result["path"]).read().startswith("# Netscape HTTP Cookie File")

    no_login = api.save_cookies_text(NETSCAPE)
    assert "no YouTube login" in no_login["error"]
    assert not os.path.exists(result["path"])

    broken = api.save_cookies_text(NETSCAPE)
    assert broken["error"] == "ERROR: bad cookie file"

    assert api.clear_cookies_file() == {"ok": True}
    (project_dir / "Dependencies" / "cookies.txt").write_text("x")
    api.clear_cookies_file()
    assert not (project_dir / "Dependencies" / "cookies.txt").exists()


def test_describe_cookie_test_dpapi_points_to_manual_paste(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")

    result = setup_api.describe_cookie_test("chrome", 1, "ERROR: Failed to decrypt with DPAPI. See https://github.com/yt-dlp/yt-dlp/issues/10927 for more info")

    assert result["error"] == "ERROR: Failed to decrypt with DPAPI. Recent Google Chrome versions on Windows encrypt cookies so only the browser can read them. Use Firefox, or paste the cookies manually below."
