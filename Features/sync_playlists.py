import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yt_downloader
import spotify_converter

SYNC_MATCH_THRESHOLD = 78


def build_local_index(folder):
    from mutagen import File as read_audio
    from mutagen.mp3 import MP3

    files = []

    for root, _, names in os.walk(folder):
        for name in names:
            if not name.lower().endswith(".mp3"):
                continue

            path = os.path.join(root, name)
            entry = {
                "path": path,
                "filename": os.path.splitext(name)[0],
                "title": "",
                "artist": "",
                "spotify_id": None,
                "youtube_id": None,
            }

            try:
                audio = MP3(path)

                if audio.tags:
                    for frame in audio.tags.getall("TXXX"):
                        if frame.desc == "SPOTIFY_ID":
                            entry["spotify_id"] = frame.text[0]
                        elif frame.desc == "YOUTUBE_ID":
                            entry["youtube_id"] = frame.text[0]

                easy_file = read_audio(path, easy=True)

                if easy_file and easy_file.tags:
                    entry["title"] = (easy_file.tags.get("title") or [""])[0]
                    entry["artist"] = (easy_file.tags.get("artist") or [""])[0]
            except Exception:
                pass

            files.append(entry)

    return files


def compare_playlist_with_folder(tracks, local_files):
    from thefuzz import fuzz

    remaining = list(local_files)
    by_spotify_id = {f["spotify_id"]: f for f in remaining if f["spotify_id"]}

    matched = []
    missing = []

    for track in tracks:
        file = by_spotify_id.get(track["spotify_id"])

        if file and file in remaining:
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


def delete_files(paths):
    results = []

    for path in paths:
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

    print(f"\n[Sync] {len(matched)} in sync, {len(missing)} missing locally, {len(orphans)} local orphans.")

    run_id = history.start_run("sync_check", target=playlist["name"], total=len(playlist["tracks"]))

    for track in missing:
        history.log_item(run_id, f"{', '.join(track['artists'])} - {track['title']}", "missing")

    for f in orphans:
        history.log_item(run_id, f["filename"], "orphan", detail=f["path"])

    history.finish_run(run_id, "completed")

    if orphans:
        print("\nLocal files not in the playlist:")

        for f in orphans:
            print(f"  - {f['filename']}")

        if yt_downloader.ask_yes_no(f"\nDelete {len(orphans)} orphan file(s)? (y/n): "):
            delete_run = history.start_run("sync_delete", target=folder, total=len(orphans))

            for result in delete_files([f["path"] for f in orphans]):
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

        for track in missing:
            print(f"  - {', '.join(track['artists'])} - {track['title']}")

        if yt_downloader.ask_yes_no(f"\nConvert and download {len(missing)} missing track(s)? (y/n): "):
            ytmusic = spotify_converter.open_ytmusic()
            videos, unmatched = spotify_converter.convert_tracks(ytmusic, missing)

            if unmatched:
                print(f"[WARNING] {len(unmatched)} track(s) not found on YouTube Music.")

            if videos:
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
