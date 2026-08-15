import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import date

DOWNLOADED_MUSIC_FOLDER_NAME = "Downloaded Musics"


def get_script_directory():
    return os.path.dirname(os.path.abspath(__file__))


def get_project_directory():
    return os.path.dirname(get_script_directory())


def get_dependencies_directory():
    return os.path.join(get_project_directory(), "Dependencies")


def get_library_directory(script_directory):
    return os.path.dirname(script_directory)


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


def list_downloaded_music_folders(library_directory):
    downloaded_music_directory = os.path.join(library_directory, DOWNLOADED_MUSIC_FOLDER_NAME)

    if not os.path.isdir(downloaded_music_directory):
        return downloaded_music_directory, []

    folders = sorted(d.name for d in os.scandir(downloaded_music_directory) if d.is_dir())

    return downloaded_music_directory, folders


def select_duplicate_scan_folders(library_directory):
    downloaded_music_directory, folders = list_downloaded_music_folders(library_directory)

    if not folders:
        print(f"[WARNING] No folders found in {downloaded_music_directory}")
        return []

    print("\nFolders available for duplicate scan:\n")
    print("  1. all")

    for index, folder_name in enumerate(folders, start=2):
        print(f"  {index}. {folder_name}")

    selection = input("\nSelect folders (e.g. 1,3,4): ").strip().lower()

    selected_indexes = set()

    for part in selection.split(","):
        part = part.strip()

        if part.isdigit():
            selected_indexes.add(int(part))

    if 1 in selected_indexes:
        return [os.path.join(downloaded_music_directory, name) for name in folders]

    selected_paths = []

    for index in sorted(selected_indexes):
        folder_index = index - 2

        if 0 <= folder_index < len(folders):
            selected_paths.append(os.path.join(downloaded_music_directory, folders[folder_index]))

    return selected_paths


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
    library_directory = get_library_directory(script_directory)

    if not playlist_name:
        print("Content: Video")
        return library_directory, "%(title)s.%(ext)s"

    print(f"Content: Playlist -> {playlist_name}")

    playlist_directory_name = f"{playlist_name}_{get_today()}"
    output_directory = os.path.join(library_directory, playlist_directory_name)

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


def download_video(video, output_directory, output_template, script_directory, ffmpeg_path):
    output_path = os.path.join(output_directory, output_template)
    fix_artwork_script = get_fix_artwork_script()
    post_download_command = f'{sys.executable} "{fix_artwork_script}" %(filepath)q %(id)q'

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
        "--sleep-requests",          "2",
        "--sleep-interval",          "5",
        "--max-sleep-interval",      "10",
        "--output",                  output_path,
        "--exec",                    post_download_command,
        video["url"],
    ]

    return subprocess.run(command, cwd=script_directory).returncode


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
        library_directory = get_library_directory(script_directory)
        selected_folders = select_duplicate_scan_folders(library_directory)
        downloaded_videos = build_library_index(selected_folders)
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
            has_errors = False

            for video in pending_videos:
                print(f"[DOWNLOAD] {video['title']}\n")

                return_code = download_video(video, output_directory, output_template, script_directory, ffmpeg_path)

                if return_code != 0:
                    has_errors = True

                downloaded_videos[video["id"]] = "DOWNLOADED"
                print()

            if has_errors:
                print("[WARNING] Download process concluded with errors.")
            else:
                print("[OK] Download process concluded successfully.")

        print(f"\nDownload files saved in: {output_directory}")

        if input("\nDownload more URLs? (y/n): ").strip().lower() != "y":
            break

    print("\nExiting...")
    input("Press Enter to exit...")


def main():
    process_download()


if __name__ == "__main__":
    main()
