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

    def _reset(self):
        self._status = {
            "running": False,
            "total": 0,
            "current": None,
            "items": [],
            "output_directory": None,
        }

    def list_download_folders(self):
        downloads_directory = yt_downloader.get_downloads_directory()
        return sorted(d.name for d in os.scandir(downloads_directory) if d.is_dir())

    def analyze_url(self, url, scan_folders=None):
        script_directory = yt_downloader.get_script_directory()
        index = {}

        if scan_folders is not None:
            downloads_directory = yt_downloader.get_downloads_directory()

            if not scan_folders or "__all__" in scan_folders:
                scan_paths = [downloads_directory]
            else:
                scan_paths = [os.path.join(downloads_directory, name) for name in scan_folders]

            index = yt_downloader.build_library_index(scan_paths)

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
