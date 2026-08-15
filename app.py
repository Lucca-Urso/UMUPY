import os
import platform
import subprocess
import sys
import threading

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_DIR, "Features"))

import yt_downloader


class UmupyApi:
    def __init__(self):
        self._lock = threading.Lock()
        self._reset()
        self._spotify_reset()
        self._rekordbox = None

    def _reset(self):
        self._status = {
            "running": False,
            "total": 0,
            "current": None,
            "items": [],
            "output_directory": None,
        }

    def _spotify_reset(self):
        self._spotify_status = {
            "running": False,
            "phase": None,
            "processed": 0,
            "total": 0,
            "playlist": None,
            "matched": [],
            "unmatched": [],
            "error": None,
        }

    def _scan_paths(self, scan_folders):
        downloads_directory = yt_downloader.get_downloads_directory()

        if not scan_folders or "__all__" in scan_folders:
            return [downloads_directory]

        return [os.path.join(downloads_directory, name) for name in scan_folders]

    def _build_scan_index(self, scan_folders):
        if scan_folders is None:
            return {}

        return yt_downloader.build_library_index(self._scan_paths(scan_folders))

    def list_download_folders(self):
        downloads_directory = yt_downloader.get_downloads_directory()
        return sorted(d.name for d in os.scandir(downloads_directory) if d.is_dir())

    def analyze_url(self, url, scan_folders=None):
        script_directory = yt_downloader.get_script_directory()
        index = self._build_scan_index(scan_folders)

        playlist_name = yt_downloader.detect_playlist(url, script_directory)
        videos = yt_downloader.extract_videos(url, script_directory)

        for video in videos:
            video["duplicate"] = video["id"] in index

        return {
            "playlist": playlist_name or None,
            "videos": videos,
            "ffmpeg": bool(yt_downloader.find_ffmpeg()),
        }

    def start_download(self, videos, playlist_name=None):
        downloads_directory = yt_downloader.get_downloads_directory()

        if playlist_name:
            directory_name = f"{playlist_name}_{yt_downloader.get_today()}"
            output_directory = os.path.join(downloads_directory, directory_name)
            os.makedirs(output_directory, exist_ok=True)
        else:
            output_directory = downloads_directory

        with self._lock:
            self._reset()
            self._status.update({
                "running": True,
                "total": len(videos),
                "output_directory": output_directory,
            })

        worker = threading.Thread(target=self._download_worker, args=(videos, output_directory), daemon=True)
        worker.start()

        return output_directory

    def _download_worker(self, videos, output_directory):
        script_directory = yt_downloader.get_script_directory()
        ffmpeg_path = yt_downloader.find_ffmpeg()

        for video in videos:
            with self._lock:
                self._status["current"] = video["title"]

            return_code = yt_downloader.download_video(
                video, output_directory, "%(title)s.%(ext)s", script_directory, ffmpeg_path
            )

            with self._lock:
                self._status["items"].append({
                    "id": video["id"],
                    "title": video["title"],
                    "url": video.get("url"),
                    "ok": return_code == 0,
                })

        with self._lock:
            self._status["running"] = False
            self._status["current"] = None

    def get_status(self):
        with self._lock:
            return dict(self._status)

    def open_output_directory(self):
        with self._lock:
            directory = self._status.get("output_directory") or yt_downloader.get_downloads_directory()

        system = platform.system()

        if system == "Darwin":
            subprocess.run(["open", directory])
        elif system == "Windows":
            os.startfile(directory)
        else:
            subprocess.run(["xdg-open", directory])

        return directory

    def spotify_ready(self):
        import spotify_converter

        return {
            "ready": os.path.isfile(spotify_converter.get_credentials_path()),
            "path": spotify_converter.get_credentials_path(),
        }

    def start_spotify_analysis(self, url, scan_folders=None):
        with self._lock:
            self._spotify_reset()
            self._spotify_status["running"] = True
            self._spotify_status["phase"] = "fetching"

        worker = threading.Thread(target=self._spotify_worker, args=(url, scan_folders), daemon=True)
        worker.start()

        return True

    def _spotify_worker(self, url, scan_folders):
        import spotify_converter

        try:
            index = self._build_scan_index(scan_folders)
            spotify_index = (
                spotify_converter.build_spotify_index(self._scan_paths(scan_folders))
                if scan_folders is not None
                else {}
            )

            spotify = spotify_converter.open_spotify()
            playlist = spotify_converter.fetch_playlist(spotify, url)

            with self._lock:
                self._spotify_status["playlist"] = playlist["name"]
                self._spotify_status["total"] = len(playlist["tracks"])
                self._spotify_status["phase"] = "matching"

            ytmusic = spotify_converter.open_ytmusic()

            for track in playlist["tracks"]:
                video = spotify_converter.search_youtube_equivalent(ytmusic, track)
                source = {"title": track["title"], "artists": track["artists"]}

                with self._lock:
                    self._spotify_status["processed"] += 1

                    if video:
                        video["duplicate"] = video["id"] in index or track["spotify_id"] in spotify_index
                        video["source"] = source
                        self._spotify_status["matched"].append(video)
                    else:
                        self._spotify_status["unmatched"].append(source)

        except SystemExit:
            with self._lock:
                self._spotify_status["error"] = "Spotify credentials not found or invalid."
        except Exception as error:
            with self._lock:
                self._spotify_status["error"] = str(error)
        finally:
            with self._lock:
                self._spotify_status["running"] = False
                self._spotify_status["phase"] = None

    def get_spotify_status(self):
        with self._lock:
            return dict(self._spotify_status)

    def rekordbox_select_source(self, mode):
        import webview

        window = webview.windows[0]

        if mode == "folder":
            result = window.create_file_dialog(webview.FOLDER_DIALOG)
        else:
            result = window.create_file_dialog(
                webview.OPEN_DIALOG, file_types=("Playlist files (*.txt;*.xml)",)
            )

        if not result:
            return None

        return result[0] if isinstance(result, (list, tuple)) else result

    def rekordbox_analyze(self, source_path):
        import rekordbox_playlist_creator as rpc

        playlists = rpc.load_playlists_from_source(source_path)

        if not playlists:
            return {"error": "No playlists found in the selected source."}

        db = rpc.open_database()
        collection = list(db.get_content())
        existing_names = {p.Name for p in db.get_playlist()}
        results = rpc.match_playlists(playlists, collection, existing_names)

        self._rekordbox = {"db": db, "results": results}

        return {
            "collection": len(collection),
            "running": rpc.rekordbox_is_running(),
            "playlists": [
                {
                    "name": r["name"],
                    "exists": r["exists"],
                    "matched": [{"title": m["title"], "artist": m["artist"]} for m in r["matched"]],
                    "unmatched": r["unmatched"],
                }
                for r in results
            ],
        }

    def rekordbox_create(self, names):
        import rekordbox_playlist_creator as rpc

        if self._rekordbox is None:
            return {"error": "Nothing analyzed yet."}

        if rpc.rekordbox_is_running():
            return {"error": "RekordBox is running. Close it before writing to the database."}

        results = [r for r in self._rekordbox["results"] if r["name"] in names]
        created = rpc.create_playlists(self._rekordbox["db"], results)

        return {"created": created}


def main():
    import webview

    api = UmupyApi()
    dev_mode = "--dev" in sys.argv

    if dev_mode:
        entry = "http://localhost:5173"
    else:
        entry = os.path.join(PROJECT_DIR, "UI", "dist", "index.html")

        if not os.path.isfile(entry):
            print("[ERROR] UI build not found. Run: cd UI && npm install && npm run build")
            sys.exit(1)

    webview.create_window(
        "UMUPY",
        entry,
        js_api=api,
        width=1100,
        height=760,
        min_size=(900, 620),
        background_color="#09090b",
    )
    webview.start(debug=dev_mode)


if __name__ == "__main__":
    main()
