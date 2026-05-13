import io
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import date


def crop_to_square(image):
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def process_thumbnail(image):
    from PIL import Image

    if image.mode in ("RGBA", "P", "LA"):
        image = image.convert("RGB")

    image = crop_to_square(image)
    image = image.resize((800, 800), Image.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90, dpi=(300, 300))
    return output


def build_thumbnail_index(directory):
    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    thumbnails = {}

    for file_name in os.listdir(directory):
        file_base_name, extension = os.path.splitext(file_name)
        if extension.lower() in image_extensions:
            thumbnails[file_base_name.lower()] = os.path.join(directory, file_name)

    return thumbnails


def find_thumbnail(audio_base_name, thumbnail_index):
    import difflib
    import re

    normalized_name = audio_base_name.lower()

    if normalized_name in thumbnail_index:
        return thumbnail_index[normalized_name]

    stripped_name = re.sub(r"^\d+\s*[-_.]\s*", "", normalized_name)

    if stripped_name in thumbnail_index:
        return thumbnail_index[stripped_name]

    for thumbnail_name, thumbnail_path in thumbnail_index.items():
        if re.sub(r"^\d+\s*[-_.]\s*", "", thumbnail_name) == normalized_name:
            return thumbnail_path

    similar_names = difflib.get_close_matches(normalized_name, thumbnail_index.keys(), n=1, cutoff=0.7)

    if similar_names:
        return thumbnail_index[similar_names[0]]

    return None


def embed_metadata(audio_path, image_data, youtube_video_id=None):
    from mutagen.id3 import APIC, TXXX
    from mutagen.mp3 import MP3

    audio_file = MP3(audio_path)

    if audio_file.tags is None:
        audio_file.add_tags()

    audio_file.tags.delall("APIC")
    audio_file.tags.delall("TXXX:YOUTUBE_ID")
    audio_file.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=image_data))

    if youtube_video_id:
        audio_file.tags.add(TXXX(encoding=3, desc="YOUTUBE_ID", text=[youtube_video_id]))

    audio_file.save(v2_version=3)


def fix_audio_artwork(audio_path, youtube_video_id=None):
    from mutagen.mp3 import MP3
    from PIL import Image

    if not os.path.isfile(audio_path):
        print(f"[ERROR] File not found: {audio_path}")
        return

    directory = os.path.dirname(audio_path)
    file_name = os.path.basename(audio_path)
    audio_base_name = os.path.splitext(file_name)[0]

    print(f"\n[Artwork] {file_name}")

    thumbnail_index = build_thumbnail_index(directory)
    thumbnail_path = find_thumbnail(audio_base_name, thumbnail_index)

    try:
        if thumbnail_path:
            print(f"Thumbnail found: {os.path.basename(thumbnail_path)}")

            processed_image = process_thumbnail(Image.open(thumbnail_path))
            embed_metadata(audio_path, processed_image.getvalue(), youtube_video_id)

            try:
                os.remove(thumbnail_path)
            except OSError as error:
                print(f"[WARNING] Could not remove thumbnail: {error}")

            print("[OK] Artwork embedded.")

        else:
            audio_file = MP3(audio_path)
            artwork_list = audio_file.tags.getall("APIC") if audio_file.tags else []

            if not artwork_list:
                print("[WARNING] No artwork found.")
                return

            processed_image = process_thumbnail(Image.open(io.BytesIO(artwork_list[0].data)))
            embed_metadata(audio_path, processed_image.getvalue(), youtube_video_id)

            print("[OK] Artwork rebuilt from existing APIC.")

    except Exception as error:
        print(f"[ERROR] Failed to process artwork: {error}")


def get_script_directory():
    return os.path.dirname(os.path.abspath(__file__))


def get_library_directory(script_directory):
    return os.path.dirname(script_directory)


def get_today():
    return date.today().strftime("%d_%m")


def find_ffmpeg():
    ffmpeg_binary = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    ffmpeg_path = shutil.which(ffmpeg_binary)

    if ffmpeg_path:
        return ffmpeg_path

    local_ffmpeg_path = os.path.join(get_script_directory(), ffmpeg_binary)

    if os.path.isfile(local_ffmpeg_path):
        return local_ffmpeg_path

    return None


def build_library_index(script_directory):
    from mutagen.mp3 import MP3

    library_directory = get_library_directory(script_directory)
    current_directory_name = os.path.basename(script_directory)
    downloaded_videos = {}

    print("\n[Library] Building in-memory index...\n")

    for directory in os.scandir(library_directory):
        if not directory.is_dir():
            continue
        if directory.name == current_directory_name:
            continue

        print(f"  Scanning: {directory.name}")

        for root, _, files in os.walk(directory.path):
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
        [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--print", "%(playlist_title)s", "--playlist-items", "1", "--no-warnings", url],
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


def extract_videos(url, script_directory):
    process_result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--dump-json", "--no-warnings", url],
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
    script_path = os.path.abspath(__file__)
    post_download_command = f'{sys.executable} "{script_path}" --fix-file "%(filepath)s" "%(id)s"'

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
        print("\nInstall FFmpeg globally or place it in the script directory.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    downloaded_videos = build_library_index(script_directory)

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
    if len(sys.argv) == 4 and sys.argv[1] == "--fix-file":
        fix_audio_artwork(sys.argv[2], sys.argv[3])
        return

    process_download()


if __name__ == "__main__":
    main()