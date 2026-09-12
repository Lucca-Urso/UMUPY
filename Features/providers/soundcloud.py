import re
from concurrent.futures import ThreadPoolExecutor

from providers import base, ytdlp

NAME = "soundcloud"
TAG = "SOUNDCLOUD_ID"
DOWNLOADABLE = True
URL_PATTERN = re.compile(r"^(https?://)?([\w-]+\.)*soundcloud\.com/", re.IGNORECASE)
METADATA_BATCH = 5
METADATA_WORKERS = 4


def matches(url):
    return URL_PATTERN.match(url.strip()) is not None


def is_playlist(url):
    return "/sets/" in url


def entry_to_track(entry):
    artists = [entry.get("artist") or entry.get("uploader") or ""]
    duration = entry.get("duration")

    return base.make_track(
        NAME,
        entry.get("id"),
        entry.get("title"),
        artists=artists,
        duration=round(duration) if duration else None,
        url=entry.get("webpage_url") or entry.get("url"),
    )


def list_playlist_urls(url):
    entries, stderr, _ = ytdlp.dump_json(["--flat-playlist"], url)
    name = next((entry.get("playlist_title") for entry in entries if entry.get("playlist_title")), None)
    urls = [entry.get("url") for entry in entries if entry.get("url")]
    return name, urls, stderr


def fetch_metadata(url, start, end):
    entries, stderr, _ = ytdlp.dump_json(["--simulate", "--playlist-items", f"{start}-{end}"], url)
    return entries, stderr


def resolve(url):
    if not is_playlist(url):
        entries, stderr, _ = ytdlp.dump_json(["--simulate", "--no-playlist"], url)
        tracks = [entry_to_track(entry) for entry in entries if entry.get("id")]
        error = None if tracks else ytdlp.error_summary(stderr)
        return {"name": None, "tracks": tracks, "error": error}

    name, urls, stderr = list_playlist_urls(url)

    if not urls:
        return {"name": name, "tracks": [], "error": ytdlp.error_summary(stderr)}

    ranges = [(start, min(start + METADATA_BATCH - 1, len(urls))) for start in range(1, len(urls) + 1, METADATA_BATCH)]

    with ThreadPoolExecutor(max_workers=METADATA_WORKERS) as pool:
        batches = list(pool.map(lambda r: fetch_metadata(url, *r), ranges))

    tracks = []
    seen = set()

    for entries, _ in batches:
        for entry in entries:
            track = entry_to_track(entry)

            if entry.get("id") and track["id"] not in seen:
                seen.add(track["id"])
                tracks.append(track)

    return {"name": name, "tracks": tracks, "error": None if tracks else "Could not read tracks from this set"}


def search(client, track, limit=5):
    entries, _, _ = ytdlp.dump_json(["--flat-playlist"], f"scsearch{limit}:{base.search_query(track)}")
    candidates = [entry_to_track(entry) for entry in entries if entry.get("id") and entry.get("title")]
    return base.pick_best(track, candidates)


def open_client():
    return None
