import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yt_downloader
import spotify_converter

SYNC_MATCH_THRESHOLD = 78


def build_local_index(folder):
    import library

    return library.build_index([folder]).files


def track_key(track):
    source = track.get("source") or ("spotify" if track.get("spotify_id") else "youtube")
    track_id = track.get("id") if track.get("source") else track.get("spotify_id") or track.get("id")
    return source, track_id


def compare_playlist_with_folder(tracks, local_files):
    from thefuzz import fuzz

    remaining = list(local_files)

    matched = []
    missing = []

    for track in tracks:
        source, track_id = track_key(track)
        file = next((f for f in remaining if track_id and f.get(f"{source}_id") == track_id), None)

        if file:
            matched.append((track, file))
            remaining.remove(file)
            continue

        label = f"{' '.join(track['artists'])} {track['title']}"
        best = None
        best_score = 0

        for f in remaining:
            candidates = [c for c in (f"{f['artist']} {f['title']}".strip(), f["filename"]) if c]
            score = max(fuzz.token_set_ratio(label, candidate) for candidate in candidates)

            if score > best_score:
                best_score = score
                best = f

        if best and best_score >= SYNC_MATCH_THRESHOLD:
            matched.append((track, best))
            remaining.remove(best)
        else:
            missing.append(track)

    return matched, missing, remaining


def reconcile_missing(missing_entries, orphans):
    still_missing = []
    reconciled = []

    for entry in missing_entries:
        video = entry.get("video")
        source = (video or {}).get("source") or "youtube"
        file = next((f for f in orphans if video and f.get(f"{source}_id") == video["id"]), None)

        if file:
            reconciled.append((entry, file))
            orphans.remove(file)
        else:
            still_missing.append(entry)

    return still_missing, reconciled


def embed_tag(path, tag, value):
    from mutagen.id3 import TXXX
    from mutagen.mp3 import MP3

    audio = MP3(path)

    if audio.tags is None:
        audio.add_tags()

    audio.tags.delall(f"TXXX:{tag}")
    audio.tags.add(TXXX(encoding=3, desc=tag, text=[str(value)]))
    audio.save(v2_version=3)


def embed_spotify_id(path, spotify_id):
    embed_tag(path, "SPOTIFY_ID", spotify_id)


def heal_ids(matched_pairs):
    from providers import TAGS

    healed = 0

    for track, file in matched_pairs:
        source, track_id = track_key(track)
        field = f"{source}_id"

        if file.get(field) or not track_id:
            continue

        try:
            embed_tag(file["path"], TAGS[source], track_id)
            file[field] = track_id
            healed += 1
        except Exception:
            continue

    return healed


heal_spotify_ids = heal_ids


def is_inside_folder(path, folder):
    if not folder:
        return False

    try:
        real_folder = os.path.realpath(folder)
        real_path = os.path.realpath(path)
        return os.path.commonpath([real_folder, real_path]) == real_folder and real_path != real_folder
    except ValueError:
        return False


def delete_files(paths, folder=None):
    results = []

    for path in paths:
        if folder is not None and not is_inside_folder(path, folder):
            results.append({"path": path, "ok": False, "error": "Path is outside the synced folder"})
            continue

        try:
            os.remove(path)
            results.append({"path": path, "ok": True, "error": None})
        except OSError as error:
            results.append({"path": path, "ok": False, "error": str(error)})

    return results


def main():
    import history

    if len(sys.argv) > 2:
        playlist_url, folder = sys.argv[1], sys.argv[2]
    else:
        playlist_url = input("Enter Spotify playlist URL: ").strip()
        folder = os.path.expanduser(input("Enter local folder to sync: ").strip())

    if not os.path.isdir(folder):
        print(f"[ERROR] Folder not found: {folder}")
        sys.exit(1)

    spotify = spotify_converter.open_spotify()
    playlist = spotify_converter.fetch_playlist(spotify, playlist_url)
    local_files = build_local_index(folder)

    print(f"\nPlaylist: {playlist['name']} ({len(playlist['tracks'])} tracks)")
    print(f"Local folder: {folder} ({len(local_files)} files)")

    matched, missing, orphans = compare_playlist_with_folder(playlist["tracks"], local_files)
    healed = heal_spotify_ids(matched)

    if healed:
        print(f"[Sync] Tagged {healed} file(s) with SPOTIFY_ID.")

    videos = []
    reconciled = []

    if missing:
        ytmusic = spotify_converter.open_ytmusic()
        found_videos, unmatched = spotify_converter.convert_tracks(ytmusic, missing)
        video_by_spotify_id = {v["spotify_id"]: v for v in found_videos}
        missing_entries = [
            {
                "title": t["title"],
                "artists": t["artists"],
                "spotify_id": t["spotify_id"],
                "video": video_by_spotify_id.get(t["spotify_id"]),
            }
            for t in missing
        ]
        still_missing, reconciled = reconcile_missing(missing_entries, orphans)

        for entry, file in reconciled:
            try:
                embed_spotify_id(file["path"], entry["spotify_id"])
            except Exception:
                pass

            print(f"[Sync] Reconciled by YOUTUBE_ID: {file['filename']}")

        missing = still_missing
        videos = [e["video"] for e in missing if e["video"]]

    in_sync = len(matched) + len(reconciled)
    print(f"\n[Sync] {in_sync} in sync, {len(missing)} missing locally, {len(orphans)} local orphans.")

    run_id = history.start_run("sync_check", target=playlist["name"], total=len(playlist["tracks"]))

    for entry in missing:
        history.log_item(
            run_id,
            f"{', '.join(entry['artists'])} - {entry['title']}",
            "missing" if entry.get("video") else "not_found",
        )

    for f in orphans:
        history.log_item(run_id, f["filename"], "orphan", detail=f["path"])

    history.finish_run(run_id, "completed")

    if orphans:
        print("\nLocal files not in the playlist:")

        for f in orphans:
            print(f"  - {f['filename']}")

        if yt_downloader.ask_yes_no(f"\nDelete {len(orphans)} orphan file(s)? (y/n): "):
            delete_run = history.start_run("sync_delete", target=folder, total=len(orphans))

            for result in delete_files([f["path"] for f in orphans], folder):
                history.log_item(
                    delete_run,
                    os.path.basename(result["path"]),
                    "ok" if result["ok"] else "failed",
                    error=result["error"],
                )

            history.finish_run(delete_run, "completed")
            print("[OK] Orphan files deleted.")

    if missing:
        print("\nTracks missing locally:")

        for entry in missing:
            print(f"  - {', '.join(entry['artists'])} - {entry['title']}")

        not_found = [e for e in missing if not e.get("video")]

        if not_found:
            print(f"[WARNING] {len(not_found)} track(s) not found on YouTube Music.")

        if videos and yt_downloader.ask_yes_no(f"\nDownload {len(videos)} missing track(s)? (y/n): "):
            ffmpeg_path = yt_downloader.find_ffmpeg()
            script_directory = yt_downloader.get_script_directory()
            download_run = history.start_run("sync_download", target=playlist["name"], total=len(videos))
            failed = 0

            for video in videos:
                print(f"[DOWNLOAD] {video['title']}\n")
                return_code = yt_downloader.download_video(
                    video, folder, "%(title)s.%(ext)s", script_directory, ffmpeg_path
                )

                if return_code != 0:
                    failed += 1

                history.log_item(
                    download_run,
                    video["title"],
                    "ok" if return_code == 0 else "failed",
                    detail=video.get("url"),
                )
                print()

            history.finish_run(download_run, "completed_with_errors" if failed else "completed")

    print("\n[OK] Sync finished.")


if __name__ == "__main__":
    main()
