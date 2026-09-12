import re

import spotify_converter
from providers import base

NAME = "spotify"
TAG = "SPOTIFY_ID"
DOWNLOADABLE = False
URL_PATTERN = re.compile(r"^(https?://)?(open\.)?spotify\.com/|^spotify:", re.IGNORECASE)


def matches(url):
    return URL_PATTERN.match(url.strip()) is not None


def open_client():
    return spotify_converter.open_spotify()


def resolve(url, client=None):
    client = client or open_client()
    playlist = spotify_converter.fetch_playlist(client, url)
    tracks = [
        base.make_track(NAME, t["spotify_id"], t["title"], artists=t["artists"], duration=t["duration"], spotify_id=t["spotify_id"])
        for t in playlist["tracks"]
    ]
    return {"name": playlist["name"], "tracks": tracks, "error": None}


def search(client, track, limit=10):
    return None
