import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import date


def get_script_directory():
    return os.path.dirname(os.path.abspath(__file__))


def get_project_directory():
    if getattr(sys, "frozen", False):
        directory = os.path.join(os.path.expanduser("~"), "UMUPY")
        os.makedirs(directory, exist_ok=True)
        return directory

    return os.path.dirname(get_script_directory())


def yt_dlp_command():
    if getattr(sys, "frozen", False):
        return [sys.executable, "--yt-dlp"]

    return [sys.executable, "-m", "yt_dlp"]


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


def bundled_binary_directories():
    directories = [get_dependencies_directory()]

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        directories.insert(0, os.path.join(sys._MEIPASS, "bin"))
    else:
        directories.append(os.path.join(os.path.dirname(get_script_directory()), "bin"))

    return directories


def find_ffmpeg():
    ffmpeg_binary = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"

    for directory in bundled_binary_directories():
        local_ffmpeg_path = os.path.join(directory, ffmpeg_binary)

        if os.path.isfile(local_ffmpeg_path):
            return local_ffmpeg_path

    return shutil.which(ffmpeg_binary)


def find_deno():
    deno_binary = "deno.exe" if platform.system() == "Windows" else "deno"

    for directory in bundled_binary_directories():
        local_path = os.path.join(directory, deno_binary)

        if os.path.isfile(local_path):
            return local_path

    return shutil.which(deno_binary)


def find_cookies():
    dependencies_directory = get_dependencies_directory()

    if not os.path.isdir(dependencies_directory):
        return None

    for file_name in sorted(os.listdir(dependencies_directory)):
        if "cookies" in file_name.lower() and file_name.lower().endswith(".txt"):
            cookies_path = os.path.join(dependencies_directory, file_name)

            if os.name == "posix":
                try:
                    os.chmod(cookies_path, 0o600)
                except OSError:
                    pass

            return cookies_path

    return None


def cookies_browser():
    import settings

    return settings.load().get("cookies_browser")


def cookies_arguments():
    browser = cookies_browser()

    if browser:
        return ["--cookies-from-browser", browser]

    cookies_path = find_cookies()
    return ["--cookies", cookies_path] if cookies_path else []


def deno_arguments():
    deno_path = find_deno()

    if deno_path and not shutil.which(os.path.basename(deno_path)):
        return ["--js-runtimes", f"deno:{deno_path}"]

    return []


def common_arguments():
    return [*cookies_arguments(), *deno_arguments()]


def ask_yes_no(question):
    while True:
        answer = input(question).strip().lower()

        if answer in ("y", "n"):
            return answer == "y"


def select_duplicate_scan_folders():
    downloads_directory = get_downloads_directory()
    folders = sorted(d.name for d in os.scandir(downloads_directory) if d.is_dir())

    if not folders:
        return [downloads_directory]

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
        return [downloads_directory]

    selected_paths = []

    for index in sorted(selected_indexes):
        folder_index = index - 2

        if 0 <= folder_index < len(folders):
            selected_paths.append(os.path.join(downloads_directory, folders[folder_index]))

    return selected_paths


def build_library_index(selected_folders):
    import library

    print("\n[Library] Building in-memory index...\n")

    for folder_path in selected_folders:
        print(f"  Scanning: {os.path.basename(folder_path)}")

    index = library.build_index(selected_folders, on_error=lambda path: print(f"[WARNING] Could not index: {path}"))
    downloaded_videos = dict(index.by_source["youtube"])

    print(f"\n[Library] Indexed {len(downloaded_videos)} musics.\n")

    return downloaded_videos


def detect_playlist(url, script_directory):
    process_result = subprocess.run(
        [
            *yt_dlp_command(),
            "--flat-playlist",
            "--extractor-args", "youtubetab:skip=webpage,authcheck",
            "--print", "%(playlist_title)s",
            "--playlist-items", "1",
            "--no-warnings",
            *common_arguments(),
            url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=script_directory,
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
            *yt_dlp_command(),
            "--flat-playlist",
            "--extractor-args", "youtubetab:skip=webpage,authcheck",
            "--playlist-start", str(start_index),
            "--playlist-end", str(end_index),
            "--dump-json",
            "--no-warnings",
            *common_arguments(),
            url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=script_directory,
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


def probe_url_error(url, script_directory):
    process_result = subprocess.run(
        [
            *yt_dlp_command(),
            "--flat-playlist",
            "--extractor-args", "youtubetab:skip=webpage,authcheck",
            "--playlist-items", "1",
            "--simulate",
            "--print", "%(id)s",
            *common_arguments(),
            url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=script_directory,
    )

    if process_result.returncode == 0 and process_result.stdout.strip():
        return None

    stderr_lines = (process_result.stderr or "").strip().splitlines()
    error_lines = [line for line in stderr_lines if "ERROR" in line] or stderr_lines[-3:]

    return " | ".join(error_lines[-3:]) if error_lines else "yt-dlp returned no results for this URL"


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


def remove_residual_thumbnails(output_directory, images_before, title=None):
    import fix_artwork

    residual_images = list_image_files(output_directory) - images_before

    if title:
        index = {os.path.splitext(os.path.basename(path))[0].lower(): path for path in residual_images}
        own = fix_artwork.find_thumbnail(title, index)
        residual_images = {own} if own else set()

    for image_path in residual_images:
        try:
            os.remove(image_path)
            print(f"[CLEANUP] Removed residual thumbnail: {os.path.basename(image_path)}")
        except OSError as error:
            print(f"[WARNING] Could not remove residual thumbnail: {error}")


def is_safe_track_id(value):
    return bool(value) and isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is not None


def post_download_arguments(video):
    from providers import TAGS

    source_tag = TAGS.get(video.get("source") or "youtube", "YOUTUBE_ID")
    arguments = f"%(filepath)q {source_tag} %(id)q"

    if is_safe_track_id(video.get("spotify_id")) and source_tag != "SPOTIFY_ID":
        arguments += f' SPOTIFY_ID {video["spotify_id"]}'

    return arguments


DEFAULT_SLEEP_ARGUMENTS = ["--sleep-requests", "2", "--sleep-interval", "5", "--max-sleep-interval", "10"]


def download_video(video, output_directory, output_template, script_directory, ffmpeg_path, capture=False, sleep_arguments=None):
    output_path = os.path.join(output_directory, output_template)
    fix_artwork_script = get_fix_artwork_script()
    arguments = post_download_arguments(video)

    if getattr(sys, "frozen", False):
        post_download_command = f'"{sys.executable}" --fix-artwork {arguments}'
    else:
        post_download_command = f'{sys.executable} "{fix_artwork_script}" {arguments}'

    images_before = list_image_files(output_directory)

    command = [
        *yt_dlp_command(),
        "--extractor-args",          "youtube:player_client=default,web_embedded",
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
        "--concurrent-fragments",    "3",
        "--http-chunk-size",         "10M",
        *(sleep_arguments if sleep_arguments is not None else DEFAULT_SLEEP_ARGUMENTS),
        "--output",                  output_path,
        "--exec",                    post_download_command,
        *common_arguments(),
        video["url"],
    ]

    if capture:
        process_result = subprocess.run(
            command, cwd=script_directory, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        return_code = process_result.returncode
        error_text = None

        if return_code != 0:
            stderr_lines = (process_result.stderr or "").strip().splitlines()
            error_lines = [line for line in stderr_lines if "ERROR" in line] or stderr_lines[-3:]
            error_text = " | ".join(error_lines[-3:]) if error_lines else f"yt-dlp exited with code {return_code}"
    else:
        return_code = subprocess.run(command, cwd=script_directory).returncode
        error_text = None

    if return_code != 0:
        remove_residual_thumbnails(output_directory, images_before, video.get("title"))

    return (return_code, error_text) if capture else return_code


def process_download():
    script_directory = get_script_directory()
    ffmpeg_path = find_ffmpeg()

    if not ffmpeg_path:
        print("[ERROR] FFmpeg not found.")
        print("\nInstall FFmpeg globally or place it in the Dependencies directory.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    scan_duplicates = ask_yes_no("Scan for duplicates? (y/n): ")

    if scan_duplicates:
        selected_folders = select_duplicate_scan_folders()
        downloaded_videos = build_library_index(selected_folders) if selected_folders else {}
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
            import history

            run_id = history.start_run("youtube_download", target=url, total=len(pending_videos))
            failed_videos = []

            for video in pending_videos:
                print(f"[DOWNLOAD] {video['title']}\n")

                return_code = download_video(video, output_directory, output_template, script_directory, ffmpeg_path)

                if return_code != 0:
                    failed_videos.append(video)
                else:
                    downloaded_videos[video["id"]] = "DOWNLOADED"

                history.log_item(
                    run_id,
                    video["title"],
                    "ok" if return_code == 0 else "failed",
                    detail=video.get("url"),
                )
                print()

            history.finish_run(run_id, "completed_with_errors" if failed_videos else "completed")

            downloaded_count = len(pending_videos) - len(failed_videos)
            print(f"[OK] {downloaded_count}/{len(pending_videos)} musics downloaded.")

            if failed_videos:
                print(f"\n[WARNING] {len(failed_videos)} download(s) failed:")

                for video in failed_videos:
                    print(f"  - {video['title']}")
                    print(f"    {video['url']}")

        print(f"\nDownload files saved in: {output_directory}")

        if not ask_yes_no("\nDownload more URLs? (y/n): "):
            break

    print("\nExiting...")
    input("Press Enter to exit...")


def main():
    process_download()


if __name__ == "__main__":
    main()
