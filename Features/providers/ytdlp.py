import json
import subprocess

import yt_downloader


def run(arguments, url):
    result = subprocess.run(
        [*yt_downloader.yt_dlp_command(), "--no-warnings", *yt_downloader.cookies_arguments(), *arguments, url],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=yt_downloader.get_script_directory(),
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def json_lines(stdout):
    entries = []

    for line in stdout.splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return entries


def dump_json(arguments, url):
    return_code, stdout, stderr = run(["--dump-json", *arguments], url)
    return json_lines(stdout), stderr, return_code


def error_summary(stderr, fallback="yt-dlp returned no results"):
    lines = stderr.strip().splitlines()
    errors = [line for line in lines if "ERROR" in line] or lines[-3:]
    return " | ".join(errors[-3:]) if errors else fallback
