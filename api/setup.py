import json
import os
import platform
import subprocess

import settings
import spotify_converter
import yt_downloader

BROWSERS = ["safari", "firefox", "chrome", "edge", "brave", "opera", "vivaldi", "chromium"]
CHROME_FAMILY = {"chrome", "edge", "brave", "opera", "vivaldi", "chromium"}
LABELS = {"chrome": "Google Chrome", "edge": "Microsoft Edge", "brave": "Brave", "opera": "Opera", "vivaldi": "Vivaldi", "chromium": "Chromium", "firefox": "Firefox", "safari": "Safari"}
COOKIE_TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def available_browsers():
    system = platform.system()
    browsers = []

    for name in BROWSERS:
        if name == "safari" and system != "Darwin":
            continue

        note = None
        recommended = name in ("safari", "firefox")

        if name in CHROME_FAMILY and system == "Darwin":
            note = "Asks for your Mac password to unlock the browser cookies."
        elif name == "chrome" and system == "Windows":
            note = "Recent Chrome versions block cookie access on Windows."
            recommended = False
        elif name == "edge" and system == "Windows":
            recommended = True

        browsers.append({"id": name, "label": LABELS[name], "recommended": recommended, "note": note})

    return sorted(browsers, key=lambda b: not b["recommended"])


def describe_cookie_test(browser, return_code, output):
    lines = output.strip().splitlines()
    extracted = next((line for line in lines if line.startswith("Extracted") and "cookies" in line), "")
    error = next((line for line in lines if line.startswith("ERROR")), "")
    signed_in = any("Found YouTube account cookies" in line for line in lines)

    if return_code != 0 or error or "Extracted 0 cookies" in extracted:
        hint = ""
        lowered = output.lower()

        if browser == "chrome" and platform.system() == "Windows":
            hint = " Chrome on Windows blocks cookie access; try Firefox or Edge."
        elif "could not find" in lowered or "not found" in lowered:
            hint = " Is that browser installed on this computer?"

        return {"ok": False, "error": (error or "Cookie extraction failed") + hint}

    if not signed_in:
        return {"ok": False, "error": f"{extracted or 'Cookies read'}, but no YouTube login was found. Sign in to YouTube in {browser} first."}

    return {"ok": True, "detail": f"{extracted}. YouTube login found."}


class SetupApi:
    def spotify_ready(self):
        path = spotify_converter.get_credentials_path()
        return {"ready": os.path.isfile(path), "path": path}

    def setup_status(self):
        ffmpeg = yt_downloader.find_ffmpeg()
        deno = yt_downloader.find_deno()
        current = settings.load()

        return {
            "spotify": self.spotify_ready(),
            "cookies": {
                "browser": current.get("cookies_browser"),
                "file": yt_downloader.find_cookies(),
                "browsers": available_browsers(),
                "system": platform.system(),
            },
            "ffmpeg": {"ok": bool(ffmpeg), "path": ffmpeg},
            "deno": {"ok": bool(deno), "path": deno},
            "data_directory": yt_downloader.get_project_directory(),
        }

    def save_spotify_credentials(self, client_id, client_secret):
        client_id = (client_id or "").strip()
        client_secret = (client_secret or "").strip()

        if not client_id or not client_secret:
            return {"error": "Both Client ID and Client Secret are required."}

        path = spotify_converter.get_credentials_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {"client_id": client_id, "client_secret": client_secret, "redirect_uri": "http://127.0.0.1:8888/callback"},
                handle, indent=2,
            )

        spotify_converter.restrict_permissions(path)
        token_cache = spotify_converter.get_token_cache_path()

        if os.path.isfile(token_cache):
            os.remove(token_cache)

        return {"ok": True, "path": path}

    def test_spotify_credentials(self):
        try:
            client = spotify_converter.open_spotify()
            client.current_user()
        except SystemExit:
            return {"ok": False, "error": "Credentials file missing or incomplete."}
        except Exception as error:
            return {"ok": False, "error": str(error)}

        return {"ok": True}

    def set_cookies_browser(self, browser):
        browser = (browser or "").strip().lower() or None

        if browser and browser not in BROWSERS:
            return {"error": f"Unknown browser: {browser}"}

        settings.save(cookies_browser=browser)
        return {"ok": True, "browser": browser}

    def test_cookies(self, browser=None):
        browser = (browser or settings.load().get("cookies_browser") or "").strip().lower()

        if not browser:
            return {"ok": False, "error": "Choose a browser first."}

        result = subprocess.run(
            [
                *yt_downloader.yt_dlp_command(), "--cookies-from-browser", browser, "--simulate", "-v",
                "--print", "%(id)s", COOKIE_TEST_URL,
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=yt_downloader.get_script_directory(),
        )
        return describe_cookie_test(browser, result.returncode, (result.stdout or "") + "\n" + (result.stderr or ""))

    def open_data_directory(self):
        from api import base

        return base.open_in_file_manager(yt_downloader.get_project_directory())
