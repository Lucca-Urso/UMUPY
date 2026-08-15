import io
import os
import sys


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


def main():
    if len(sys.argv) == 3:
        fix_audio_artwork(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        fix_audio_artwork(sys.argv[1])
    else:
        print("Usage: python fix_artwork.py <audio_path> [youtube_video_id]")
        sys.exit(1)


if __name__ == "__main__":
    main()
