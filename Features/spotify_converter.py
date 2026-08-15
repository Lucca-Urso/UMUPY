import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yt_downloader

MATCH_THRESHOLD = 75


def get_credentials_path():
    return os.path.join(yt_downloader.get_dependencies_directory(), "spotify_credentials.json")


def get_token_cache_path():
    return os.path.join(yt_downloader.get_dependencies_directory(), ".spotify_token_cache")


def load_credentials():
    credentials_path = get_credentials_path()

    if not os.path.isfile(credentials_path):
        print("[ERROR] Spotify credentials not found.")
        print("\nCreate a free app at https://developer.spotify.com/dashboard")
        print(f"then save the credentials as {credentials_path} with the format:")
        print('{"client_id": "...", "client_secret": "...", "redirect_uri": "http://127.0.0.1:8888/callback"}')
        sys.exit(1)

    with open(credentials_path) as credentials_file:
        credentials = json.load(credentials_file)

    aliases = {
        "client_id": ["client_id", "clientId", "clientID", "id"],
        "client_secret": ["client_secret", "clientSecret", "secret"],
    }

    for key, candidates in aliases.items():
        for candidate in candidates:
            if candidate in credentials:
                credentials[key] = credentials[candidate]
                break
        else:
            print(f"[ERROR] Missing '{key}' in {credentials_path}")
            sys.exit(1)

    return credentials


def open_spotify():
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    credentials = load_credentials()

    auth_manager = SpotifyOAuth(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        redirect_uri=credentials.get("redirect_uri", "http://127.0.0.1:8888/callback"),
        scope="playlist-read-private playlist-read-collaborative user-library-read",
        cache_path=get_token_cache_path(),
    )

    return spotipy.Spotify(auth_manager=auth_manager)


def open_ytmusic():
    from ytmusicapi import YTMusic

    return YTMusic()


def fetch_playlist(spotify, playlist_url):
    playlist = spotify.playlist(playlist_url)
    tracks = []
    page = playlist.get("tracks") or playlist.get("items")

    while page:
        for entry in page["items"]:
            track = entry.get("track") or entry.get("item")

            if not track or not track.get("id"):
                continue

            tracks.append({
                "spotify_id": track["id"],
                "title": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "duration": round(track["duration_ms"] / 1000),
            })

        page = spotify.next(page) if page.get("next") else None

    return {"name": playlist["name"], "tracks": tracks}


def search_youtube_equivalent(ytmusic, track):
    from thefuzz import fuzz

    artist_names = " ".join(track["artists"])
    query = f"{artist_names} {track['title']}".strip()
    results = ytmusic.search(query, filter="songs", limit=10) or []

    best = None
    best_score = 0.0

    for result in results:
        if not result.get("videoId"):
            continue

        title_score = fuzz.token_set_ratio(track["title"], result.get("title", ""))
        result_artists = " ".join(artist["name"] for artist in result.get("artists", []))
        artist_score = fuzz.token_set_ratio(artist_names, result_artists)
        score = title_score * 0.6 + artist_score * 0.4

        duration = result.get("duration_seconds")

        if duration and abs(duration - track["duration"]) <= 5:
            score += 10

        if score > best_score:
            best_score = score
            best = result

    if best is None or best_score < MATCH_THRESHOLD:
        return None

    return {
        "id": best["videoId"],
        "title": best.get("title", track["title"]),
        "url": f"https://www.youtube.com/watch?v={best['videoId']}",
        "spotify_id": track["spotify_id"],
        "score": round(best_score),
    }


def convert_tracks(ytmusic, tracks):
    matched = []
    unmatched = []

    print(f"\n[Convert] Searching YouTube equivalents for {len(tracks)} tracks...\n")

    for track in tracks:
        label = f"{', '.join(track['artists'])} - {track['title']}"
        video = search_youtube_equivalent(ytmusic, track)

        if video:
            matched.append(video)
            print(f"  [OK {video['score']}] {label}")
            print(f"          -> {video['title']} ({video['url']})")
        else:
            unmatched.append(track)
            print(f"  [NOT FOUND] {label}")

    print(f"\n[Convert] {len(matched)} matched, {len(unmatched)} unmatched.")

    return matched, unmatched


def download_videos(videos, playlist_name):
    ffmpeg_path = yt_downloader.find_ffmpeg()

    if not ffmpeg_path:
        print("[ERROR] FFmpeg not found.")
        sys.exit(1)

    script_directory = yt_downloader.get_script_directory()
    downloads_directory = yt_downloader.get_downloads_directory()
    directory_name = f"{playlist_name}_{yt_downloader.get_today()}"
    output_directory = os.path.join(downloads_directory, directory_name)

    os.makedirs(output_directory, exist_ok=True)
    print(f"\nDestination: {output_directory}\n")

    failed_videos = []

    for video in videos:
        print(f"[DOWNLOAD] {video['title']}\n")

        return_code = yt_downloader.download_video(
            video, output_directory, "%(title)s.%(ext)s", script_directory, ffmpeg_path
        )

        if return_code != 0:
            failed_videos.append(video)

        print()

    downloaded_count = len(videos) - len(failed_videos)
    print(f"[OK] {downloaded_count}/{len(videos)} musics downloaded.")

    if failed_videos:
        print(f"\n[WARNING] {len(failed_videos)} download(s) failed:")

        for video in failed_videos:
            print(f"  - {video['title']}")
            print(f"    {video['url']}")

    return output_directory


def main():
    if len(sys.argv) > 1:
        playlist_url = sys.argv[1]
    else:
        playlist_url = input("Enter Spotify playlist URL: ").strip()

    if not playlist_url:
        print("[ERROR] URL not provided.")
        sys.exit(1)

    spotify = open_spotify()
    playlist = fetch_playlist(spotify, playlist_url)

    print(f"\nPlaylist: {playlist['name']} ({len(playlist['tracks'])} tracks)")

    ytmusic = open_ytmusic()
    matched, unmatched = convert_tracks(ytmusic, playlist["tracks"])

    if not matched:
        print("[INFO] Nothing to download.")
        return

    scan_duplicates = yt_downloader.ask_yes_no("\nScan Downloads for duplicates? (y/n): ")

    if scan_duplicates:
        selected_folders = yt_downloader.select_duplicate_scan_folders()
        downloaded_videos = yt_downloader.build_library_index(selected_folders) if selected_folders else {}
        matched = yt_downloader.filter_pending_videos(matched, downloaded_videos)

        if not matched:
            print("[INFO] Nothing to download.")
            return

    if not yt_downloader.ask_yes_no(f"Download {len(matched)} musics? (y/n): "):
        print("Operation cancelled.")
        return

    output_directory = download_videos(matched, playlist["name"])
    print(f"\nDownload files saved in: {output_directory}")


if __name__ == "__main__":
    main()
