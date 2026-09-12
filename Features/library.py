import os

from providers import TAGS

TAG_FIELDS = {tag: f"{name}_id" for name, tag in TAGS.items()}


def read_file(path):
    from mutagen.mp3 import MP3

    entry = {
        "path": path,
        "filename": os.path.splitext(os.path.basename(path))[0],
        "title": "",
        "artist": "",
        "youtube_id": None,
        "spotify_id": None,
        "soundcloud_id": None,
    }

    try:
        audio = MP3(path)
    except Exception:
        return entry, False

    tags = audio.tags

    if not tags:
        return entry, True

    for frame in tags.getall("TXXX"):
        field = TAG_FIELDS.get(frame.desc)

        if field and frame.text:
            entry[field] = frame.text[0]

    title = tags.get("TIT2")
    artist = tags.get("TPE1")
    entry["title"] = str(title.text[0]) if title and title.text else ""
    entry["artist"] = str(artist.text[0]) if artist and artist.text else ""

    return entry, True


def iter_mp3_files(folders):
    for folder in folders:
        for root, _, files in os.walk(folder):
            for name in sorted(files):
                if name.lower().endswith(".mp3"):
                    yield os.path.join(root, name)


class LibraryIndex:
    def __init__(self, files=()):
        self.files = list(files)
        self.by_source = {name: {} for name in TAGS}

        for entry in self.files:
            for name in TAGS:
                value = entry.get(f"{name}_id")

                if value:
                    self.by_source[name].setdefault(value, entry["path"])

    def contains(self, source, track_id):
        return bool(track_id) and track_id in self.by_source.get(source, {})

    def path_for(self, source, track_id):
        return self.by_source.get(source, {}).get(track_id)

    def is_duplicate(self, track):
        return self.contains(track.get("source"), track.get("id"))

    def __len__(self):
        return len(self.files)


def build_index(folders, on_error=None):
    files = []

    for path in iter_mp3_files(folders):
        entry, ok = read_file(path)

        if not ok and on_error:
            on_error(path)

        files.append(entry)

    return LibraryIndex(files)
