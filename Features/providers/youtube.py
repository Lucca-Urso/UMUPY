import re

import yt_downloader
from providers import base

NAME = "youtube"
TAG = "YOUTUBE_ID"
DOWNLOADABLE = True
URL_PATTERN = re.compile(r"^(https?://)?([\w-]+\.)*(youtube\.com|youtu\.be|music\.youtube\.com)/", re.IGNORECASE)


def matches(url):
    return URL_PATTERN.match(url.strip()) is not None


def video_url(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def resolve(url):
    script_directory = yt_downloader.get_script_directory()
    playlist_name = yt_downloader.detect_playlist(url, script_directory)
    videos = yt_downloader.extract_videos(url, script_directory)
    error = None if videos else yt_downloader.probe_url_error(url, script_directory)

    tracks = [base.make_track(NAME, v["id"], v["title"], url=v["url"]) for v in videos]

    return {"name": playlist_name or None, "tracks": tracks, "error": error}


def open_client():
    from ytmusicapi import YTMusic

    return YTMusic()


def search(client, track, limit=10):
    results = base.retry_call(lambda: client.search(base.search_query(track), filter="songs", limit=limit)) or []
    candidates = [
        base.make_track(
            NAME,
            result["videoId"],
            result.get("title", track["title"]),
            artists=[artist.get("name", "") for artist in result.get("artists", [])],
            duration=result.get("duration_seconds"),
            url=video_url(result["videoId"]),
        )
        for result in results
        if result.get("videoId")
    ]

    return base.pick_best(track, candidates)
