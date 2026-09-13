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
    extra = {}

    if "formats" in entry and not entry.get("formats"):
        extra["unavailable"] = "Not downloadable from SoundCloud (protected track)"

    return base.make_track(
        NAME,
        entry.get("id"),
        entry.get("title"),
        artists=artists,
        duration=round(duration) if duration else None,
        url=entry.get("webpage_url") or entry.get("url"),
        **extra,
    )


def list_entries(url):
    entries, stderr, _ = ytdlp.dump_json(["--flat-playlist", "--ignore-no-formats-error"], url)
    children = [entry for entry in entries if entry.get("_type") == "url" or entry.get("playlist_title")]
    name = next((entry.get("playlist_title") for entry in children if entry.get("playlist_title")), None)
    urls = [entry.get("url") for entry in children if entry.get("url")]
    singles = [entry for entry in entries if entry not in children and entry.get("id")]
    return name, urls, singles, stderr


def list_playlist_urls(url):
    name, urls, _, stderr = list_entries(url)
    return name, urls, stderr


def fetch_metadata(url, start, end):
    entries, stderr, _ = ytdlp.dump_json(
        ["--simulate", "--ignore-no-formats-error", "--playlist-items", f"{start}-{end}"], url
    )
    return entries, stderr


def slug_to_title(url):
    slug = url.rstrip("/").rsplit("/", 1)[-1]

    if slug.isdigit():
        return ""

    return re.sub(r"[-_]+", " ", slug).strip().title()


def unavailable_reason(stderr, track_id):
    for line in stderr.splitlines():
        if track_id and f"] {track_id}:" in line and "ERROR" in line:
            return line.split(":", 2)[-1].strip()

    if "geo restriction" in stderr:
        return "Not available in your location"

    return "Unavailable on SoundCloud"


def placeholder_track(url, stderr):
    track_id = url.rstrip("/").rsplit("/", 1)[-1]
    track_id = track_id if track_id.isdigit() else None
    title = slug_to_title(url)
    return base.make_track(
        NAME, track_id or url, title or f"Unknown track {track_id}", url=url,
        unavailable=unavailable_reason(stderr, track_id), searchable=bool(title),
    )


def resolve(url):
    name, urls, singles, stderr = list_entries(url)

    if not urls:
        tracks = [entry_to_track(entry) for entry in singles]
        error = None if tracks else ytdlp.error_summary(stderr)
        return {"name": None, "tracks": tracks, "error": error}

    ranges = [(start, min(start + METADATA_BATCH - 1, len(urls))) for start in range(1, len(urls) + 1, METADATA_BATCH)]

    with ThreadPoolExecutor(max_workers=METADATA_WORKERS) as pool:
        batches = list(pool.map(lambda r: fetch_metadata(url, *r), ranges))

    resolved = {}
    errors = ""

    for entries, batch_stderr in batches:
        errors += batch_stderr

        for entry in entries:
            if entry.get("id"):
                resolved[str(entry["id"])] = entry_to_track(entry)

    tracks = []
    seen = set()

    for track_url in urls:
        track_id = track_url.rstrip("/").rsplit("/", 1)[-1]
        track = resolved.get(track_id)

        if track is None:
            track = next((t for t in resolved.values() if t["url"] == track_url and t["id"] not in seen), None)

        if track is None:
            track = placeholder_track(track_url, errors)

        if track["id"] not in seen:
            seen.add(track["id"])
            tracks.append(track)

    return {"name": name, "tracks": tracks, "error": None if tracks else "Could not read tracks from this set"}


def search(client, track, limit=5):
    entries, _, _ = ytdlp.dump_json(["--flat-playlist"], f"scsearch{limit}:{base.search_query(track)}")
    candidates = [entry_to_track(entry) for entry in entries if entry.get("id") and entry.get("title")]
    return base.pick_best(track, candidates)


def open_client():
    return None
