import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yt_downloader
from providers import base
from providers import youtube as youtube_provider

MATCH_THRESHOLD = base.MATCH_THRESHOLD
MAX_CONSECUTIVE_FAILURES = 5

retry_call = base.retry_call


def get_credentials_path():
    return os.path.join(yt_downloader.get_dependencies_directory(), "spotify_credentials.json")


def get_token_cache_path():
    return os.path.join(yt_downloader.get_dependencies_directory(), ".spotify_token_cache")


def restrict_permissions(path):
    if os.name != "posix" or not os.path.isfile(path):
        return False

    try:
        os.chmod(path, 0o600)
        return True
    except OSError:
        return False


def load_credentials():
    credentials_path = get_credentials_path()

    if not os.path.isfile(credentials_path):
        print("[ERROR] Spotify credentials not found.")
        print("\nCreate a free app at https://developer.spotify.com/dashboard")
        print(f"then save the credentials as {credentials_path} with the format:")
        print('{"client_id": "...", "client_secret": "...", "redirect_uri": "http://127.0.0.1:8888/callback"}')
        sys.exit(1)

    restrict_permissions(credentials_path)

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

    spotify = spotipy.Spotify(auth_manager=auth_manager, requests_timeout=20, retries=5)
    restrict_permissions(get_token_cache_path())
    return spotify


def open_ytmusic():
    return youtube_provider.open_client()


def fetch_playlist(spotify, playlist_url):
    playlist = retry_call(lambda: spotify.playlist(playlist_url))
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

        page = retry_call(lambda: spotify.next(page)) if page.get("next") else None

    return {"name": playlist["name"], "tracks": tracks}


def search_youtube_equivalent(ytmusic, track):
    video = youtube_provider.search(ytmusic, track)

    if video is None:
        return None

    return {
        "id": video["id"],
        "title": video["title"],
        "url": video["url"],
        "spotify_id": track["spotify_id"],
        "score": video["score"],
    }


def build_spotify_index(selected_folders):
    from mutagen.mp3 import MP3

    spotify_ids = {}

    for folder_path in selected_folders:
        for root, _, files in os.walk(folder_path):
            for file_name in files:
                if not file_name.lower().endswith(".mp3"):
                    continue

                audio_path = os.path.join(root, file_name)

                try:
                    audio_file = MP3(audio_path)

                    if not audio_file.tags:
                        continue

                    for frame in audio_file.tags.getall("TXXX"):
                        if frame.desc == "SPOTIFY_ID":
                            spotify_ids[frame.text[0]] = audio_path
                            break

                except Exception:
                    continue

    return spotify_ids


def convert_tracks(ytmusic, tracks):
    matched = []
    unmatched = []
    consecutive_failures = 0

    print(f"\n[Convert] Searching YouTube equivalents for {len(tracks)} tracks...\n")

    for track in tracks:
        label = f"{', '.join(track['artists'])} - {track['title']}"

        try:
            video = search_youtube_equivalent(ytmusic, track)
            consecutive_failures = 0
        except Exception as error:
            consecutive_failures += 1
            unmatched.append(track)
            print(f"  [ERROR] {label}")
            print(f"          {error}")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"\n[ERROR] {MAX_CONSECUTIVE_FAILURES} consecutive network failures. Aborting search.")
                break

            continue

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
    import history

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

    run_id = history.start_run("spotify_download", target=playlist_name, total=len(videos))
    failed_videos = []

    for video in videos:
        print(f"[DOWNLOAD] {video['title']}\n")

        return_code = yt_downloader.download_video(
            video, output_directory, "%(title)s.%(ext)s", script_directory, ffmpeg_path
        )

        if return_code != 0:
            failed_videos.append(video)

        history.log_item(
            run_id,
            video["title"],
            "ok" if return_code == 0 else "failed",
            detail=video.get("url"),
        )
        print()

    history.finish_run(run_id, "completed_with_errors" if failed_videos else "completed")

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

        if selected_folders:
            downloaded_videos = yt_downloader.build_library_index(selected_folders)
            spotify_index = build_spotify_index(selected_folders)
            matched = yt_downloader.filter_pending_videos(matched, downloaded_videos)
            matched = [v for v in matched if v["spotify_id"] not in spotify_index]

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
