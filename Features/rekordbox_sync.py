import os
import shutil
from datetime import datetime

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".aiff", ".aif"}


def normalize_path(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def list_local_tracks(folder):
    import library

    tracks = []

    for root, _, names in os.walk(folder):
        for name in sorted(names):
            if os.path.splitext(name)[1].lower() not in AUDIO_EXTENSIONS:
                continue

            path = os.path.join(root, name)
            entry = {"path": path, "title": os.path.splitext(name)[0], "artist": ""}

            if name.lower().endswith(".mp3"):
                info, _ = library.read_file(path)
                entry["title"] = info["title"] or entry["title"]
                entry["artist"] = info["artist"]

            tracks.append(entry)

    return tracks


def playlist_name_for(folder):
    import rekordbox_playlist_creator as rpc

    return rpc.folder_playlist_name(folder)


def find_playlist(db, name):
    for playlist in db.get_playlist():
        if playlist.Name == name and not getattr(playlist, "SmartList", None):
            return playlist

    return None


def collection_by_path(db):
    index = {}

    for content in db.get_content():
        if content.FolderPath:
            index.setdefault(normalize_path(content.FolderPath), content)

    return index


def playlist_songs(db, playlist):
    songs = []

    for song in db.get_playlist_songs(PlaylistID=playlist.ID):
        content = song.Content
        songs.append({
            "song_id": song.ID,
            "path": content.FolderPath if content else None,
            "title": (content.Title if content else None) or "",
            "artist": (content.Artist.Name if content and content.Artist else "") or "",
        })

    return songs


def plan_sync(db, folder, playlist_name=None):
    playlist_name = playlist_name or playlist_name_for(folder)
    local_tracks = list_local_tracks(folder)
    collection = collection_by_path(db)
    playlist = find_playlist(db, playlist_name)
    songs = playlist_songs(db, playlist) if playlist else []
    in_playlist = {normalize_path(song["path"]): song for song in songs if song["path"]}
    local_paths = {normalize_path(track["path"]) for track in local_tracks}

    add = []
    keep = []

    for track in local_tracks:
        key = normalize_path(track["path"])
        item = {**track, "in_collection": key in collection}

        if key in in_playlist:
            keep.append(item)
        else:
            add.append(item)

    remove = [song for key, song in in_playlist.items() if key not in local_paths]

    return {
        "playlist": playlist_name,
        "exists": playlist is not None,
        "folder": folder,
        "add": add,
        "keep": keep,
        "remove": remove,
    }


def backup_database(db, backup_root):
    source = os.path.join(str(db.db_directory), "master.db")

    if not os.path.isfile(source):
        return None

    os.makedirs(backup_root, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = os.path.join(backup_root, f"master_{stamp}.db")
    shutil.copy2(source, target)
    return target


def apply_sync(db, plan, add_paths, remove_song_ids, backup_root=None):
    result = {"backup": None, "created": False, "added": [], "removed": [], "errors": []}

    if backup_root:
        result["backup"] = backup_database(db, backup_root)

    playlist = find_playlist(db, plan["playlist"])

    if playlist is None and add_paths:
        playlist = db.create_playlist(plan["playlist"])
        result["created"] = True

    collection = collection_by_path(db)
    wanted = {normalize_path(path) for path in add_paths}

    for track in plan["add"]:
        key = normalize_path(track["path"])

        if key not in wanted:
            continue

        try:
            content = collection.get(key)

            if content is None:
                content = db.add_content(track["path"], Title=track["title"])
                collection[key] = content

            db.add_to_playlist(playlist, content)
            result["added"].append(track["path"])
        except Exception as error:
            result["errors"].append({"path": track["path"], "error": str(error)})

    wanted_removals = set(remove_song_ids)

    for song in plan["remove"]:
        if song["song_id"] not in wanted_removals or playlist is None:
            continue

        try:
            db.remove_from_playlist(playlist, song["song_id"])
            result["removed"].append(song["path"])
        except Exception as error:
            result["errors"].append({"path": song["path"], "error": str(error)})

    if result["added"] or result["removed"] or result["created"]:
        db.commit()

    return result
