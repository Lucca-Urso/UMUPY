import json
import os
import platform
import re
import subprocess

import settings
import spotify_converter
import yt_downloader

BROWSERS = ["safari", "firefox", "chrome", "edge", "brave", "opera", "vivaldi", "chromium"]
CHROME_FAMILY = {"chrome", "edge", "brave", "opera", "vivaldi", "chromium"}
LABELS = {"chrome": "Google Chrome", "edge": "Microsoft Edge", "brave": "Brave", "opera": "Opera", "vivaldi": "Vivaldi", "chromium": "Chromium", "firefox": "Firefox", "safari": "Safari"}
COOKIE_TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
COOKIE_DOMAINS = (".youtube.com", ".google.com", "youtube.com", "google.com")
NETSCAPE_HEADER = "# Netscape HTTP Cookie File"


def parse_cookie_text(text):
    lines = [line.rstrip("\r") for line in (text or "").strip().splitlines()]
    rows = []

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if "\t" not in stripped:
            rows = []
            break

        parts = stripped.split("\t")

        if len(parts) == 7:
            rows.append(parts)
        elif len(parts) == 6:
            rows.append([*parts, ""])
        else:
            return None

    if rows:
        return rows

    joined = " ".join(lines)

    if "=" not in joined:
        return None

    joined = joined.split(":", 1)[1] if joined.lower().startswith("cookie:") else joined
    pairs = [pair.strip() for pair in joined.split(";") if "=" in pair]
    return [[".youtube.com", "TRUE", "/", "TRUE", "0", name.strip(), value.strip()] for name, value in (pair.split("=", 1) for pair in pairs)]


def cookies_to_netscape(rows):
    body = "\n".join("\t".join(row) for row in rows)
    return f"{NETSCAPE_HEADER}\n# Saved by UMUPY\n{body}\n"


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
        elif name in CHROME_FAMILY and system == "Windows":
            note = "Quit the browser completely before testing. Recent versions may still refuse; Firefox is the safest choice."
            recommended = False

        browsers.append({"id": name, "label": LABELS[name], "recommended": recommended, "note": note})

    return sorted(browsers, key=lambda b: not b["recommended"])


def describe_cookie_test(browser, return_code, output):
    lines = output.strip().splitlines()
    extracted = next((line for line in lines if line.startswith("Extracted") and "cookies" in line), "")
    error = next((line for line in lines if line.startswith("ERROR")), "")
    signed_in = any("Found YouTube account cookies" in line for line in lines)

    if return_code != 0 or error or "Extracted 0 cookies" in extracted:
        lowered = output.lower()
        label = LABELS.get(browser, browser)

        if "could not copy" in lowered or "permission denied" in lowered:
            hint = f" {label} is still running and locks its cookie file. Quit it completely (also from the system tray), then try again."
        elif "decrypt" in lowered or "dpapi" in lowered or "app-bound" in lowered or "app bound" in lowered:
            hint = f" Recent {label} versions on Windows encrypt cookies so only the browser can read them. Use Firefox, or paste the cookies manually below."
        elif "could not find" in lowered or "not found" in lowered:
            hint = " Is that browser installed on this computer?"
        elif browser in CHROME_FAMILY and platform.system() == "Windows":
            hint = f" Chromium-based browsers are unreliable on Windows; Firefox is the safest choice."
        else:
            hint = ""

        message = re.sub(r"\.?\s*[Ss]ee https?://\S+.*$", "", error).rstrip(" .") + "." if error else "Cookie extraction failed."
        return {"ok": False, "error": message + hint}

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

    def save_cookies_text(self, text):
        rows = parse_cookie_text(text)

        if not rows:
            return {"error": "That does not look like cookies. Paste the export of a cookies.txt extension or the Cookie header from your browser."}

        if not any(row[0].endswith(domain) for row in rows for domain in COOKIE_DOMAINS):
            return {"error": "No youtube.com cookies found in the pasted text. Export them while youtube.com is open."}

        path = os.path.join(yt_downloader.get_dependencies_directory(), "cookies.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(cookies_to_netscape(rows))

        spotify_converter.restrict_permissions(path)
        settings.save(cookies_browser=None)

        result = self.test_cookies_file(path)

        if not result["ok"]:
            os.remove(path)
            return {"error": result["error"]}

        return {"ok": True, "detail": f"{len(rows)} cookies saved. {result['detail']}", "path": path}

    def clear_cookies_file(self):
        path = yt_downloader.find_cookies()

        if path:
            os.remove(path)

        return {"ok": True}

    def test_cookies_file(self, path):
        result = subprocess.run(
            [*yt_downloader.yt_dlp_command(), "--cookies", path, "--simulate", "-v", "--print", "%(id)s", COOKIE_TEST_URL],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=yt_downloader.get_script_directory(),
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        lines = output.splitlines()
        error = next((line for line in lines if line.startswith("ERROR")), "")

        if result.returncode != 0 or error:
            return {"ok": False, "error": error or "yt-dlp could not use the pasted cookies."}

        if not any("Found YouTube account cookies" in line for line in lines):
            return {"ok": False, "error": "Cookies read, but no YouTube login was found in them. Export them while signed in."}

        return {"ok": True, "detail": "YouTube login found."}

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
