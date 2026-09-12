import re
import sys
import unicodedata
from pathlib import Path
from xml.etree.ElementTree import parse as parse_xml


AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".aiff", ".aif"}


def normalize(text):
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similarity_score(a, b):
    a_words = set(normalize(a).split())
    b_words = set(normalize(b).split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / max(len(a_words), len(b_words))


def parse_txt_playlist(txt_path):
    txt_path = Path(txt_path)

    try:
        content = txt_path.read_text(encoding="utf-16")
    except UnicodeError:
        content = txt_path.read_text(encoding="utf-8", errors="replace")

    lines = content.splitlines()

    header_line = None
    header_idx = 0
    for i, line in enumerate(lines):
        if "Track Title" in line or "Artist" in line:
            header_line = line
            header_idx = i
            break

    if header_line is None:
        return []

    headers = [h.strip() for h in header_line.split("\t")]

    col = {}
    for keyword, candidates in {
        "title":  ["Track Title", "Title"],
        "artist": ["Artist"],
    }.items():
        for candidate in candidates:
            if candidate in headers:
                col[keyword] = headers.index(candidate)
                break

    tracks = []
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = line.split("\t")

        def get(key, default=""):
            idx = col.get(key)
            if idx is None or idx >= len(parts):
                return default
            return parts[idx].strip()

        title = get("title")
        if not title:
            continue

        tracks.append({"title": title, "artist": get("artist")})

    return tracks


XML_MINIMUM_EXAMPLE = """<DJ_PLAYLISTS>
  <COLLECTION>
    <TRACK TrackID="1" Name="Song title" Artist="Artist name"/>
    <TRACK TrackID="2" Location="file://localhost/Music/Other%20song.mp3"/>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="1" Name="My playlist">
      <TRACK Key="1"/>
      <TRACK Key="2"/>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>"""


def attribute(element, *names, default=""):
    lowered = {key.lower(): value for key, value in element.attrib.items()}

    for name in names:
        value = lowered.get(name.lower())

        if value is not None and value != "":
            return value

    return default


def title_from_location(location):
    from urllib.parse import unquote, urlparse

    path = urlparse(location).path if "://" in location else location
    return Path(unquote(path)).stem


def track_from_element(element):
    title = attribute(element, "Name", "Title")
    location = attribute(element, "Location", "Path", "File")

    if not title and location:
        title = title_from_location(location)

    if not title:
        return None

    return {"title": title, "artist": attribute(element, "Artist", "Artists")}


def parse_xml_playlists(xml_path):
    from xml.etree.ElementTree import ParseError

    try:
        root = parse_xml(xml_path).getroot()
    except ParseError as error:
        raise ValueError(f"Invalid XML file: {error}") from error

    tracks_by_id = {}
    collection_nodes = [node for node in root.iter() if node.tag.upper() == "COLLECTION"]

    for collection in collection_nodes or [root]:
        for element in collection.iter():
            if element.tag.upper() != "TRACK" or element is root:
                continue

            track = track_from_element(element)
            track_id = attribute(element, "TrackID", "ID", "Key")

            if track and track_id and track_id not in tracks_by_id:
                tracks_by_id[track_id] = track

    playlists = []
    playlist_nodes = [node for node in root.iter() if node.tag.upper() in ("NODE", "PLAYLIST")]

    for node in playlist_nodes:
        entries = [child for child in node if child.tag.upper() == "TRACK"]
        node_type = attribute(node, "Type")

        if node_type not in ("", "1") or (node_type == "" and not entries):
            continue

        tracks = []

        for entry in entries:
            key = attribute(entry, "Key", "TrackID", "ID")
            info = tracks_by_id.get(key) or track_from_element(entry)

            if info:
                tracks.append(dict(info))

        playlists.append({"name": attribute(node, "Name", "Title", default="Imported"), "tracks": tracks})

    if not playlists and tracks_by_id:
        playlists.append({"name": Path(xml_path).stem.replace("_", " "), "tracks": [dict(t) for t in tracks_by_id.values()]})

    return playlists


def parse_audio_folder(folder_path):
    from mutagen import File as read_audio

    folder_path = Path(folder_path)
    tracks = []

    for path in sorted(folder_path.rglob("*")):
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        title = ""
        artist = ""

        try:
            audio_file = read_audio(path, easy=True)

            if audio_file and audio_file.tags:
                title = (audio_file.tags.get("title") or [""])[0]
                artist = (audio_file.tags.get("artist") or [""])[0]
        except Exception:
            pass

        tracks.append({"title": title or path.stem, "artist": artist})

    return tracks


def folder_playlist_name(folder_path):
    name = Path(folder_path).name
    name = re.sub(r"_\d{2}_\d{2}$", "", name)
    return name.replace("_", " ").strip()


def load_playlists_from_source(source_path):
    source_path = Path(source_path)

    if source_path.is_dir():
        files = sorted(
            p for p in source_path.rglob("*")
            if p.suffix.lower() in (".txt", ".xml")
        )

        if not files:
            tracks = parse_audio_folder(source_path)
            return [{"name": folder_playlist_name(source_path), "tracks": tracks}] if tracks else []
    else:
        files = [source_path]

    playlists = []

    for file_path in files:
        if file_path.suffix.lower() == ".xml":
            playlists.extend(parse_xml_playlists(file_path))
        elif file_path.suffix.lower() == ".txt":
            tracks = parse_txt_playlist(file_path)
            playlists.append({"name": file_path.stem.replace("_", " "), "tracks": tracks})

    return [p for p in playlists if p["tracks"]]


def find_best_match(track, collection):
    title_norm = normalize(track["title"])
    artist_norm = normalize(track["artist"])

    best = None
    best_score = 0.0

    for content in collection:
        title_score = similarity_score(title_norm, normalize(content.Title or ""))
        artist_name = content.Artist.Name if content.Artist else ""
        artist_bonus = similarity_score(artist_norm, normalize(artist_name)) * 0.3 if artist_norm else 0.0
        score = title_score + artist_bonus

        if score > best_score:
            best_score = score
            best = content

    return best if best_score >= 0.5 else None


def open_database():
    from pyrekordbox import Rekordbox6Database

    return Rekordbox6Database()


def rekordbox_is_running():
    from pyrekordbox.utils import get_rekordbox_pid

    return get_rekordbox_pid() != 0


def match_playlists(playlists, collection, existing_names):
    results = []

    for playlist in playlists:
        result = {
            "name": playlist["name"],
            "exists": playlist["name"] in existing_names,
            "matched": [],
            "unmatched": [],
        }

        for track in playlist["tracks"]:
            content = find_best_match(track, collection)

            if content:
                result["matched"].append({
                    "title": track["title"],
                    "artist": track["artist"],
                    "content": content,
                })
            else:
                result["unmatched"].append(track)

        results.append(result)

    return results


def preview_results(results):
    for result in results:
        status = " (already exists, will be skipped)" if result["exists"] else ""
        print(f"\n[{result['name']}]{status}")
        print(f"  {len(result['matched'])} matched, {len(result['unmatched'])} unmatched")

        for item in result["matched"]:
            print(f"  + {item['title']} ({item['artist']})")

        for track in result["unmatched"]:
            print(f"  - {track['title']} ({track['artist']}) [NOT FOUND]")


def ask_yes_no(question):
    while True:
        answer = input(question).strip().lower()

        if answer in ("y", "n"):
            return answer == "y"


def create_playlists(db, results):
    created = 0

    for result in results:
        if result["exists"] or not result["matched"]:
            continue

        playlist = db.create_playlist(result["name"])

        for item in result["matched"]:
            db.add_to_playlist(playlist, item["content"])

        db.commit()
        created += 1

    return created


def main():
    if len(sys.argv) > 1:
        source_path = sys.argv[1]
    else:
        source_path = input("Enter playlist source path (.txt/.xml file or folder): ").strip()

    source = Path(source_path)

    if not source.exists():
        print(f"[ERROR] Path not found: {source}")
        sys.exit(1)

    playlists = load_playlists_from_source(source)

    if not playlists:
        print("[ERROR] No playlists found in source.")
        sys.exit(1)

    print(f"\n{len(playlists)} playlist(s) loaded from source.")

    db = open_database()
    collection = list(db.get_content())
    existing_names = {p.Name for p in db.get_playlist()}

    print(f"{len(collection)} tracks loaded from RekordBox collection.")

    results = match_playlists(playlists, collection, existing_names)
    preview_results(results)

    pending = [r for r in results if not r["exists"] and r["matched"]]

    if not pending:
        print("\n[INFO] Nothing to create.")
        return

    if not ask_yes_no(f"\nCreate {len(pending)} playlist(s) in RekordBox? (y/n): "):
        print("Operation cancelled.")
        return

    if rekordbox_is_running():
        print("\n[ERROR] RekordBox is running. Close it before writing to the database.")
        sys.exit(1)

    import history

    run_id = history.start_run("rekordbox_create", target=str(source), total=len(pending))
    created = create_playlists(db, results)

    for result in pending:
        detail = f"{len(result['matched'])} tracks"

        if result["unmatched"]:
            detail += f", {len(result['unmatched'])} not found"

        history.log_item(run_id, result["name"], "ok", detail=detail)

    history.finish_run(run_id, "completed")
    print(f"\n[OK] {created} playlist(s) created in RekordBox.")


if __name__ == "__main__":
    main()
