import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import date


def get_script_directory():
    return os.path.dirname(os.path.abspath(__file__))


def get_project_directory():
    return os.path.dirname(get_script_directory())


def get_dependencies_directory():
    return os.path.join(get_project_directory(), "Dependencies")


def get_downloads_directory():
    downloads_directory = os.path.join(get_project_directory(), "Downloads")
    os.makedirs(downloads_directory, exist_ok=True)
    return downloads_directory


def get_fix_artwork_script():
    return os.path.join(get_script_directory(), "fix_artwork.py")


def get_today():
    return date.today().strftime("%d_%m")


def find_ffmpeg():
    ffmpeg_binary = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    ffmpeg_path = shutil.which(ffmpeg_binary)

    if ffmpeg_path:
        return ffmpeg_path

    local_ffmpeg_path = os.path.join(get_dependencies_directory(), ffmpeg_binary)

    if os.path.isfile(local_ffmpeg_path):
        return local_ffmpeg_path

    return None


def find_cookies():
    dependencies_directory = get_dependencies_directory()

    if not os.path.isdir(dependencies_directory):
        return None

    for file_name in sorted(os.listdir(dependencies_directory)):
        if "cookies" in file_name.lower() and file_name.lower().endswith(".txt"):
            return os.path.join(dependencies_directory, file_name)

    return None


def cookies_arguments():
    cookies_path = find_cookies()
    return ["--cookies", cookies_path] if cookies_path else []


def build_library_index(selected_folders):
    from mutagen.mp3 import MP3

    downloaded_videos = {}

    print("\n[Library] Building in-memory index...\n")

    for folder_path in selected_folders:
        print(f"  Scanning: {os.path.basename(folder_path)}")

        for root, _, files in os.walk(folder_path):
            for file_name in files:
                if not file_name.lower().endswith(".mp3"):
                    continue

                audio_path = os.path.join(root, file_name)

                try:
                    audio_file = MP3(audio_path)

                    if not audio_file.tags:
                        continue

                    youtube_video_id = None

                    for frame in audio_file.tags.getall("TXXX"):
                        if frame.desc == "YOUTUBE_ID":
                            youtube_video_id = frame.text[0]
                            break

                    if youtube_video_id:
                        downloaded_videos[youtube_video_id] = audio_path

                except Exception:
                    print(f"[WARNING] Could not index: {audio_path}")

    print(f"\n[Library] Indexed {len(downloaded_videos)} musics.\n")

    return downloaded_videos


def detect_playlist(url, script_directory):
    process_result = subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist",
            "--extractor-args", "youtubetab:skip=webpage",
            "--print", "%(playlist_title)s",
            "--playlist-items", "1",
            "--no-warnings",
            *cookies_arguments(),
            url,
        ],
        capture_output=True, text=True, cwd=script_directory,
    )

    playlist_name = process_result.stdout.strip().splitlines()[0] if process_result.stdout.strip() else ""

    if playlist_name.upper() in ("NA", "[NA]"):
        playlist_name = ""

    return playlist_name


def resolve_output_directory(url, script_directory):
    playlist_name = detect_playlist(url, script_directory)
    downloads_directory = get_downloads_directory()

    if not playlist_name:
        print("Content: Video")
        return downloads_directory, "%(title)s.%(ext)s"

    print(f"Content: Playlist -> {playlist_name}")

    playlist_directory_name = f"{playlist_name}_{get_today()}"
    output_directory = os.path.join(downloads_directory, playlist_directory_name)

    os.makedirs(output_directory, exist_ok=True)
    print(f"Directory created: {playlist_directory_name}")

    return output_directory, "%(title)s.%(ext)s"


def extract_videos_chunk(url, script_directory, start_index, end_index):
    process_result = subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist",
            "--extractor-args", "youtubetab:skip=webpage",
            "--playlist-start", str(start_index),
            "--playlist-end", str(end_index),
            "--dump-json",
            "--no-warnings",
            *cookies_arguments(),
            url,
        ],
        capture_output=True, text=True, cwd=script_directory,
    )

    videos = []

    for line in process_result.stdout.splitlines():
        try:
            video_data = json.loads(line)
            youtube_video_id = video_data.get("id")
            videos.append({
                "id": youtube_video_id,
                "title": video_data.get("title"),
                "url": f"https://www.youtube.com/watch?v={youtube_video_id}",
            })
        except json.JSONDecodeError:
            continue

    return videos


def extract_videos(url, script_directory):
    chunk_size = 100
    all_videos = []
    seen_ids = set()
    start_index = 1

    while True:
        end_index = start_index + chunk_size - 1

        print(f"  Fetching items {start_index}-{end_index}...")

        chunk = extract_videos_chunk(url, script_directory, start_index, end_index)

        new_videos = [v for v in chunk if v["id"] not in seen_ids]

        if not new_videos:
            break

        for video in new_videos:
            seen_ids.add(video["id"])
            all_videos.append(video)

        if len(chunk) < chunk_size:
            break

        start_index += chunk_size

    return all_videos


def filter_pending_videos(videos, downloaded_videos):
    pending_videos = []

    print("\n[Library] Checking duplicates...\n")

    for video in videos:
        if video["id"] in downloaded_videos:
            print(f"  [SKIPPED] {video['title']}")
            print("            Already exists in library.\n")
            continue
        pending_videos.append(video)

    print(f"[Library] {len(pending_videos)} new musics found.\n")

    return pending_videos


def list_image_files(directory):
    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    if not os.path.isdir(directory):
        return set()

    return {
        os.path.join(directory, file_name)
        for file_name in os.listdir(directory)
        if os.path.splitext(file_name)[1].lower() in image_extensions
    }


def remove_residual_thumbnails(output_directory, images_before):
    residual_images = list_image_files(output_directory) - images_before

    for image_path in residual_images:
        try:
            os.remove(image_path)
            print(f"[CLEANUP] Removed residual thumbnail: {os.path.basename(image_path)}")
        except OSError as error:
            print(f"[WARNING] Could not remove residual thumbnail: {error}")


def download_video(video, output_directory, output_template, script_directory, ffmpeg_path):
    output_path = os.path.join(output_directory, output_template)
    fix_artwork_script = get_fix_artwork_script()
    post_download_command = f'{sys.executable} "{fix_artwork_script}" %(filepath)q %(id)q'

    if video.get("spotify_id"):
        post_download_command += f' {video["spotify_id"]}'

    images_before = list_image_files(output_directory)

    command = [
        sys.executable, "-m", "yt_dlp",
        "--format",                  "bestaudio[ext=m4a]/bestaudio/best",
        "--extract-audio",
        "--audio-format",            "mp3",
        "--audio-quality",           "0",
        "--ffmpeg-location",         ffmpeg_path,
        "--write-thumbnail",
        "--convert-thumbnails",      "jpg",
        "--embed-metadata",
        "--no-write-playlist-metafiles",
        "--no-abort-on-error",
        "--retries",                 "10",
        "--fragment-retries",        "10",
        "--sleep-requests",          "2",
        "--sleep-interval",          "5",
        "--max-sleep-interval",      "10",
        "--output",                  output_path,
        "--exec",                    post_download_command,
        *cookies_arguments(),
        video["url"],
    ]

    return_code = subprocess.run(command, cwd=script_directory).returncode

    if return_code != 0:
        remove_residual_thumbnails(output_directory, images_before)

    return return_code


def process_download():
    script_directory = get_script_directory()
    ffmpeg_path = find_ffmpeg()

    if not ffmpeg_path:
        print("[ERROR] FFmpeg not found.")
        print("\nInstall FFmpeg globally or place it in the Dependencies directory.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    scan_duplicates = input("Scan for duplicates? (y/n): ").strip().lower() == "y"

    if scan_duplicates:
        downloaded_videos = build_library_index([get_downloads_directory()])
    else:
        downloaded_videos = {}

    while True:
        print()
        url = input("Enter Youtube video or playlist URL: ").strip()

        if not url:
            print("[ERROR] URL not provided.")
            continue

        print("\nChecking content...")

        output_directory, output_template = resolve_output_directory(url, script_directory)

        print(f"Destination: {output_directory}\n")

        videos = extract_videos(url, script_directory)
        pending_videos = filter_pending_videos(videos, downloaded_videos)

        if not pending_videos:
            print("[INFO] Nothing to download.\n")

        else:
            print("Starting download...\n")
            failed_videos = []

            for video in pending_videos:
                print(f"[DOWNLOAD] {video['title']}\n")

                return_code = download_video(video, output_directory, output_template, script_directory, ffmpeg_path)

                if return_code != 0:
                    failed_videos.append(video)
                else:
                    downloaded_videos[video["id"]] = "DOWNLOADED"

                print()

            downloaded_count = len(pending_videos) - len(failed_videos)
            print(f"[OK] {downloaded_count}/{len(pending_videos)} musics downloaded.")

            if failed_videos:
                print(f"\n[WARNING] {len(failed_videos)} download(s) failed:")

                for video in failed_videos:
                    print(f"  - {video['title']}")
                    print(f"    {video['url']}")

        print(f"\nDownload files saved in: {output_directory}")

        if input("\nDownload more URLs? (y/n): ").strip().lower() != "y":
            break

    print("\nExiting...")
    input("Press Enter to exit...")


def main():
    process_download()


if __name__ == "__main__":
    main()
