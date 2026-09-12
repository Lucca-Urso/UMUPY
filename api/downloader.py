import os

import download_engine
import history
import yt_downloader
from api import base, sources

OPERATION_LABEL = {
    "youtube": "youtube_download",
    "spotify": "spotify_download",
    "sync": "sync_download",
}

ANALYSIS_DEFAULTS = {
    "running": False,
    "phase": None,
    "processed": 0,
    "total": 0,
    "playlist": None,
    "matched": [],
    "unmatched": [],
    "sources": [],
    "current": None,
    "error": None,
}

DOWNLOAD_DEFAULTS = {
    "running": False,
    "total": 0,
    "current": None,
    "items": [],
    "output_directory": None,
}


class DownloaderApi:
    def __init__(self):
        self._analysis = base.JobStatus(**ANALYSIS_DEFAULTS)
        self._download = base.JobStatus(**DOWNLOAD_DEFAULTS)
        self._engine = None

    def list_download_folders(self):
        downloads_directory = yt_downloader.get_downloads_directory()
        return sorted(d.name for d in os.scandir(downloads_directory) if d.is_dir())

    def analyze_url(self, url, scan_folders=None):
        script_directory = yt_downloader.get_script_directory()
        index = base.build_scan_index(scan_folders)

        playlist_name = yt_downloader.detect_playlist(url, script_directory)
        videos = yt_downloader.extract_videos(url, script_directory)
        error = None if videos else yt_downloader.probe_url_error(url, script_directory)

        for video in videos:
            video["duplicate"] = index.contains("youtube", video["id"])
            video["source"] = "youtube"

        return {
            "playlist": playlist_name or None,
            "videos": videos,
            "error": error,
            "ffmpeg": bool(yt_downloader.find_ffmpeg()),
        }

    def start_analysis(self, urls, scan_folders=None):
        urls = [urls] if isinstance(urls, str) else list(urls)
        self._analysis.reset(running=True, phase="fetching")
        base.start_thread(self._analysis_worker, urls, scan_folders)
        return True

    def start_spotify_analysis(self, url, scan_folders=None):
        return self.start_analysis([url], scan_folders)

    def _analysis_worker(self, urls, scan_folders):
        status = self._analysis

        def work(context):
            if not yt_downloader.find_ffmpeg():
                raise Exception("FFmpeg not found. Install it or place it in the Dependencies folder.")

            index = base.build_scan_index(scan_folders)
            found, tracks = sources.resolve_sources(urls, status)
            name = sources.describe_sources(found)
            run_id = history.start_run("playlist_analysis", target=name, total=len(tracks))
            context["run_id"] = run_id
            sources.log_source_errors(run_id, found)

            if not tracks:
                raise Exception(sources.first_source_error(found))

            status.update(playlist=name, total=len(tracks), phase="matching")
            matcher = sources.FallbackMatcher(run_id, status)

            for track in tracks:
                origin = {"title": track["title"], "artists": track["artists"]}

                try:
                    video, _ = matcher.match(track)
                except Exception:
                    status.increment("processed")
                    status.append("unmatched", origin)
                    raise

                status.increment("processed")

                if video:
                    video["duplicate"] = index.contains(track["source"], track["id"])
                    video["origin"] = origin
                    status.append("matched", video)
                else:
                    status.append("unmatched", origin)

            history.finish_run(run_id, "completed")

        base.run_job(status, work, "playlist_analysis", " + ".join(urls))

    def get_analysis_status(self):
        return self._analysis.snapshot()

    def get_spotify_status(self):
        return self.get_analysis_status()

    def start_download(self, videos, playlist_name=None, operation="youtube", output_directory=None):
        downloads_directory = yt_downloader.get_downloads_directory()

        if output_directory:
            os.makedirs(output_directory, exist_ok=True)
        elif playlist_name:
            from api.chain import safe_folder_name

            output_directory = os.path.join(downloads_directory, f"{safe_folder_name(playlist_name)}_{yt_downloader.get_today()}")
            os.makedirs(output_directory, exist_ok=True)
        else:
            output_directory = downloads_directory

        self._download.reset(running=True, total=len(videos), output_directory=output_directory)
        base.start_thread(self._download_worker, videos, output_directory, playlist_name, operation)
        return output_directory

    def _download_worker(self, videos, output_directory, playlist_name, operation):
        run_id = history.start_run(
            OPERATION_LABEL.get(operation, "youtube_download"),
            target=playlist_name or "Single videos",
            total=len(videos),
        )
        self._run_engine(videos, output_directory, run_id)
        self._download.update(running=False, current=None)

    def _run_engine(self, videos, output_directory, run_id, on_finished=None):
        status = self._download

        def on_event(kind, payload):
            if kind == "finished":
                history.log_item(
                    run_id, payload["title"], "ok" if payload["ok"] else "failed",
                    detail=f"{payload['url']} via {payload['provider']}", error=payload["error"],
                )
                status.append("items", dict(payload))

                if on_finished:
                    on_finished(payload)
            elif kind == "attempt":
                label = {"error": "failed"}.get(payload["status"], payload["status"])
                history.log_item(
                    run_id, payload["track"]["title"], label,
                    detail=f"{payload['status']} on {payload['provider']}", error=payload.get("error"),
                )
            elif kind == "paused":
                history.log_item(
                    run_id, "Downloads paused", "paused",
                    detail=f"waiting {payload['seconds']}s after a rate limit or bot check", error=payload["reason"],
                )

        engine = download_engine.DownloadEngine(output_directory, yt_downloader.find_ffmpeg(), on_event=on_event)
        self._engine = engine
        results = engine.run(videos)
        self._engine = None
        failed = sum(1 for result in results if not result["ok"])
        history.finish_run(run_id, "completed_with_errors" if failed else "completed")
        return results

    def get_status(self):
        status = self._download.snapshot()
        engine = self._engine
        snapshot = engine.snapshot() if engine else {"active": [], "paused": False, "paused_reason": None, "resume_in": 0}
        status.update(snapshot)

        if status["running"] and snapshot["active"]:
            status["current"] = snapshot["active"][0]["title"]

        return status

    def open_output_directory(self):
        directory = self._download.get("output_directory") or yt_downloader.get_downloads_directory()
        return base.open_in_file_manager(directory)
