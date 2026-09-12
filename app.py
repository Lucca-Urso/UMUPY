import os
import platform
import subprocess
import sys
import threading

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(sys._MEIPASS, "Features"))
else:
    sys.path.insert(0, os.path.join(PROJECT_DIR, "Features"))

if platform.system() == "Darwin":
    os.environ["PATH"] = os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin"

import yt_downloader
import history
import library
import matching
import download_engine


OPERATION_LABEL = {
    "youtube": "youtube_download",
    "spotify": "spotify_download",
    "sync": "sync_download",
}


class UmupyApi:
    def __init__(self):
        self._lock = threading.Lock()
        self._reset()
        self._spotify_reset()
        self._sync_reset()
        self._rekordbox = None
        self._engine = None

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
            "sources": [],
            "current": None,
            "error": None,
        }

    def _sync_reset(self):
        self._sync_status = {
            "running": False,
            "phase": None,
            "playlist": None,
            "folder": None,
            "total": 0,
            "processed": 0,
            "in_sync": 0,
            "orphans": [],
            "missing": [],
            "sources": [],
            "current": None,
            "error": None,
        }

    def _scan_paths(self, scan_folders):
        downloads_directory = yt_downloader.get_downloads_directory()

        if not scan_folders or "__all__" in scan_folders:
            return [downloads_directory]

        return [os.path.join(downloads_directory, name) for name in scan_folders]

    def _build_scan_index(self, scan_folders):
        if scan_folders is None:
            return library.LibraryIndex()

        return library.build_index(self._scan_paths(scan_folders))

    def list_download_folders(self):
        downloads_directory = yt_downloader.get_downloads_directory()
        return sorted(d.name for d in os.scandir(downloads_directory) if d.is_dir())

    def analyze_url(self, url, scan_folders=None):
        script_directory = yt_downloader.get_script_directory()
        index = self._build_scan_index(scan_folders)

        playlist_name = yt_downloader.detect_playlist(url, script_directory)
        videos = yt_downloader.extract_videos(url, script_directory)

        error = None

        if not videos:
            error = yt_downloader.probe_url_error(url, script_directory)

        for video in videos:
            video["duplicate"] = index.contains("youtube", video["id"])

        return {
            "playlist": playlist_name or None,
            "videos": videos,
            "error": error,
            "ffmpeg": bool(yt_downloader.find_ffmpeg()),
        }

    def start_download(self, videos, playlist_name=None, operation="youtube", output_directory=None):
        downloads_directory = yt_downloader.get_downloads_directory()

        if output_directory:
            os.makedirs(output_directory, exist_ok=True)
        elif playlist_name:
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

        worker = threading.Thread(
            target=self._download_worker, args=(videos, output_directory, playlist_name, operation), daemon=True
        )
        worker.start()

        return output_directory

    def _download_worker(self, videos, output_directory, playlist_name, operation):
        ffmpeg_path = yt_downloader.find_ffmpeg()
        run_id = history.start_run(
            OPERATION_LABEL.get(operation, "youtube_download"),
            target=playlist_name or "Single videos",
            total=len(videos),
        )

        def on_event(kind, payload):
            if kind == "finished":
                history.log_item(
                    run_id,
                    payload["title"],
                    "ok" if payload["ok"] else "failed",
                    detail=f"{payload['url']} via {payload['provider']}",
                    error=payload["error"],
                )

                with self._lock:
                    self._status["items"].append(dict(payload))

            elif kind == "attempt":
                status = {"failed": "failed", "blocked": "blocked", "retrying": "retrying", "error": "failed", "not_found": "not_found"}
                history.log_item(
                    run_id,
                    payload["track"]["title"],
                    status.get(payload["status"], payload["status"]),
                    detail=f"{payload['status']} on {payload['provider']}",
                    error=payload.get("error"),
                )

            elif kind == "paused":
                history.log_item(
                    run_id, "Downloads paused", "paused",
                    detail=f"waiting {payload['seconds']}s after a rate limit or bot check",
                    error=payload["reason"],
                )

        engine = download_engine.DownloadEngine(output_directory, ffmpeg_path, on_event=on_event)

        with self._lock:
            self._engine = engine

        results = engine.run(videos)
        failed_count = sum(1 for result in results if not result["ok"])
        history.finish_run(run_id, "completed_with_errors" if failed_count else "completed")

        with self._lock:
            self._engine = None
            self._status["running"] = False
            self._status["current"] = None

    def get_status(self):
        with self._lock:
            engine = self._engine
            status = {**self._status, "items": list(self._status["items"])}

        snapshot = engine.snapshot() if engine else {"active": [], "paused": False, "paused_reason": None, "resume_in": 0}
        status.update(snapshot)

        if status["running"] and snapshot["active"]:
            status["current"] = snapshot["active"][0]["title"]

        return status

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
        return self.start_analysis([url], scan_folders)

    def _match_with_fallback(self, track, clients, run_id, status):
        label = matching.track_label(track)

        def on_attempt(provider, retrying):
            with self._lock:
                status["current"] = {"track": label, "provider": provider, "retrying": retrying}

        try:
            match, attempts = matching.find_download_source(track, clients, on_attempt=on_attempt)
        except Exception as error:
            history.log_item(run_id, label, "failed", error=str(error))
            raise

        for attempt in attempts:
            if attempt["status"] == "matched":
                history.log_item(
                    run_id, label, "ok",
                    detail=f"-> {match['title']} ({match['url']}) {matching.describe_attempt(attempt)}",
                )
            elif attempt["status"] == "error":
                history.log_item(run_id, label, "failed", detail=attempt["provider"], error=attempt["error"])
            else:
                history.log_item(run_id, label, "not_found", detail=matching.describe_attempt(attempt))

        with self._lock:
            status["current"] = None

        return match

    def _resolve_sources(self, urls, status):
        import providers

        sources = []
        tracks = []
        seen = set()
        clients = {}

        for url in urls:
            name = providers.detect(url)
            entry = {"url": url, "provider": name, "name": None, "total": 0, "error": None}

            if not name:
                entry["error"] = "Unsupported URL. Paste a YouTube, Spotify or SoundCloud link."
            else:
                provider = providers.get(name)

                if name == "spotify":
                    if "spotify" not in clients:
                        clients["spotify"] = provider.open_client()

                    result = provider.resolve(url, clients["spotify"])
                else:
                    result = provider.resolve(url)

                entry["name"] = result["name"]
                entry["total"] = len(result["tracks"])
                entry["error"] = result["error"]

                for track in result["tracks"]:
                    key = (track["source"], track["id"])

                    if key not in seen:
                        seen.add(key)
                        tracks.append(track)

            sources.append(entry)

            with self._lock:
                status["sources"] = [dict(source) for source in sources]

        return sources, tracks

    def _describe_sources(self, sources):
        names = [source["name"] or source["provider"] or source["url"] for source in sources]
        return " + ".join(names)

    def start_analysis(self, urls, scan_folders=None):
        urls = [urls] if isinstance(urls, str) else list(urls)

        with self._lock:
            self._spotify_reset()
            self._spotify_status["running"] = True
            self._spotify_status["phase"] = "fetching"

        worker = threading.Thread(target=self._analysis_worker, args=(urls, scan_folders), daemon=True)
        worker.start()

        return True

    def _analysis_worker(self, urls, scan_folders):
        import spotify_converter

        run_id = None

        try:
            index = self._build_scan_index(scan_folders)
            sources, tracks = self._resolve_sources(urls, self._spotify_status)
            name = self._describe_sources(sources)
            run_id = history.start_run("playlist_analysis", target=name, total=len(tracks))

            for source in sources:
                if source["error"]:
                    history.log_item(run_id, source["url"], "failed", detail=source["provider"], error=source["error"])

            if not tracks:
                raise Exception(next((s["error"] for s in sources if s["error"]), "No tracks found in the given links."))

            with self._lock:
                self._spotify_status["playlist"] = name
                self._spotify_status["total"] = len(tracks)
                self._spotify_status["phase"] = "matching"

            clients = {"youtube": spotify_converter.open_ytmusic()}
            consecutive_failures = 0

            for track in tracks:
                origin = {"title": track["title"], "artists": track["artists"]}

                try:
                    video = self._match_with_fallback(track, clients, run_id, self._spotify_status)
                    consecutive_failures = 0
                except Exception:
                    consecutive_failures += 1

                    with self._lock:
                        self._spotify_status["processed"] += 1
                        self._spotify_status["unmatched"].append(origin)

                    if consecutive_failures >= spotify_converter.MAX_CONSECUTIVE_FAILURES:
                        raise Exception(
                            f"Network failed {consecutive_failures} times in a row while matching. "
                            "Check your connection and try again."
                        )

                    continue

                with self._lock:
                    self._spotify_status["processed"] += 1

                    if video:
                        video["duplicate"] = index.contains(track["source"], track["id"])
                        video["origin"] = origin
                        self._spotify_status["matched"].append(video)
                    else:
                        self._spotify_status["unmatched"].append(origin)

            history.finish_run(run_id, "completed")

        except SystemExit:
            with self._lock:
                self._spotify_status["error"] = "Spotify credentials not found or invalid."

            if run_id:
                history.finish_run(run_id, "failed")
        except Exception as error:
            with self._lock:
                self._spotify_status["error"] = str(error)

            if run_id is None:
                run_id = history.start_run("playlist_analysis", target=" + ".join(urls))

            history.log_item(run_id, "Analysis", "failed", error=str(error))
            history.finish_run(run_id, "failed")
        finally:
            with self._lock:
                self._spotify_status["running"] = False
                self._spotify_status["phase"] = None

    def get_spotify_status(self):
        with self._lock:
            return {
                **self._spotify_status,
                "matched": list(self._spotify_status["matched"]),
                "unmatched": list(self._spotify_status["unmatched"]),
            }

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

        if self._rekordbox is not None:
            try:
                self._rekordbox["db"].close()
            except Exception:
                pass

        db = rpc.open_database()
        collection = list(db.get_content())
        existing_names = {p.Name for p in db.get_playlist()}
        results = rpc.match_playlists(playlists, collection, existing_names)

        self._rekordbox = {"db": db, "results": results, "source": source_path}

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
        run_id = history.start_run("rekordbox_create", target=str(self._rekordbox["source"]), total=len(results))
        created = rpc.create_playlists(self._rekordbox["db"], results)

        for result in results:
            if result["exists"] or not result["matched"]:
                history.log_item(run_id, result["name"], "skipped", detail="already exists or no matches")
            else:
                detail = f"{len(result['matched'])} tracks"

                if result["unmatched"]:
                    detail += f", {len(result['unmatched'])} not found"

                history.log_item(run_id, result["name"], "ok", detail=detail)

        history.finish_run(run_id, "completed")

        return {"created": created}

    def history_list(self):
        return history.list_runs()

    def history_get(self, run_id):
        return history.get_run(run_id)

    def select_folder(self):
        import webview

        window = webview.windows[0]
        result = window.create_file_dialog(webview.FOLDER_DIALOG)

        if not result:
            return None

        return result[0] if isinstance(result, (list, tuple)) else result

    def start_sync_analysis(self, urls, folder):
        urls = [urls] if isinstance(urls, str) else list(urls)

        with self._lock:
            self._sync_reset()
            self._sync_status["running"] = True
            self._sync_status["phase"] = "fetching"
            self._sync_status["folder"] = folder

        worker = threading.Thread(target=self._sync_worker, args=(urls, folder), daemon=True)
        worker.start()

        return True

    def _sync_worker(self, urls, folder):
        import providers
        import spotify_converter
        import sync_playlists

        run_id = None

        try:
            sources, tracks = self._resolve_sources(urls, self._sync_status)
            name = self._describe_sources(sources)

            if not tracks:
                raise Exception(next((s["error"] for s in sources if s["error"]), "No tracks found in the given links."))

            with self._lock:
                self._sync_status["playlist"] = name
                self._sync_status["phase"] = "comparing"

            local_files = sync_playlists.build_local_index(folder)
            matched, missing, orphans = sync_playlists.compare_playlist_with_folder(tracks, local_files)
            healed = sync_playlists.heal_ids(matched)

            with self._lock:
                self._sync_status["in_sync"] = len(matched)
                self._sync_status["total"] = len(missing)
                self._sync_status["phase"] = "matching"

            run_id = history.start_run("sync_check", target=name, total=len(tracks))

            for source in sources:
                if source["error"]:
                    history.log_item(run_id, source["url"], "failed", detail=source["provider"], error=source["error"])

            if healed:
                history.log_item(run_id, f"{healed} file(s) tagged with their provider id", "ok")

            clients = {"youtube": spotify_converter.open_ytmusic()}
            consecutive_failures = 0
            missing_entries = []

            for track in missing:
                try:
                    video = self._match_with_fallback(track, clients, run_id, self._sync_status)
                    consecutive_failures = 0
                except Exception:
                    consecutive_failures += 1
                    video = None

                    if consecutive_failures >= spotify_converter.MAX_CONSECUTIVE_FAILURES:
                        raise Exception(
                            f"Network failed {consecutive_failures} times in a row while matching. "
                            "Check your connection and try again."
                        )

                missing_entries.append({
                    "title": track["title"],
                    "artists": track["artists"],
                    "source": track["source"],
                    "id": track["id"],
                    "spotify_id": track.get("spotify_id"),
                    "video": video,
                })

                with self._lock:
                    self._sync_status["processed"] += 1

            still_missing, reconciled = sync_playlists.reconcile_missing(missing_entries, orphans)

            for entry, file in reconciled:
                try:
                    sync_playlists.embed_tag(file["path"], providers.TAGS[entry["source"]], entry["id"])
                except Exception:
                    pass

                history.log_item(
                    run_id,
                    f"{', '.join(entry['artists'])} - {entry['title']}",
                    "ok",
                    detail=f"reconciled by {(entry['video'].get('source') or 'youtube').upper()}_ID with {file['filename']}",
                )

            for entry in still_missing:
                label = f"{', '.join(entry['artists'])} - {entry['title']}"
                history.log_item(
                    run_id,
                    label,
                    "missing" if entry["video"] else "not_found",
                    detail=entry["video"]["url"] if entry["video"] else None,
                )

            for f in orphans:
                history.log_item(run_id, f["filename"], "orphan", detail=f["path"])

            with self._lock:
                self._sync_status["in_sync"] = len(matched) + len(reconciled)
                self._sync_status["missing"] = still_missing
                self._sync_status["orphans"] = [
                    {"filename": f["filename"], "path": f["path"]} for f in orphans
                ]

            history.finish_run(run_id, "completed")

        except SystemExit:
            with self._lock:
                self._sync_status["error"] = "Spotify credentials not found or invalid."

            if run_id:
                history.finish_run(run_id, "failed")
        except Exception as error:
            with self._lock:
                self._sync_status["error"] = str(error)

            if run_id is None:
                run_id = history.start_run("sync_check", target=" + ".join(urls))

            history.log_item(run_id, "Analysis", "failed", error=str(error))
            history.finish_run(run_id, "failed")
        finally:
            with self._lock:
                self._sync_status["running"] = False
                self._sync_status["phase"] = None

    def get_sync_status(self):
        with self._lock:
            return {
                **self._sync_status,
                "orphans": list(self._sync_status["orphans"]),
                "missing": list(self._sync_status["missing"]),
            }

    def sync_delete(self, paths):
        import sync_playlists

        with self._lock:
            folder = self._sync_status.get("folder")
            playlist = self._sync_status.get("playlist")

        run_id = history.start_run("sync_delete", target=playlist or folder, total=len(paths))
        results = sync_playlists.delete_files(paths, folder or "")

        for result in results:
            history.log_item(
                run_id,
                os.path.basename(result["path"]),
                "ok" if result["ok"] else "failed",
                detail=result["path"],
                error=result["error"],
            )

        failed = [r for r in results if not r["ok"]]
        history.finish_run(run_id, "completed_with_errors" if failed else "completed")

        return results


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--yt-dlp":
        import yt_dlp

        yt_dlp.main(sys.argv[2:])
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--fix-artwork":
        import fix_artwork

        fix_artwork.run(sys.argv[2:])
        return

    import webview

    api = UmupyApi()
    dev_mode = "--dev" in sys.argv

    if dev_mode:
        entry = "http://localhost:5173"
    elif getattr(sys, "frozen", False):
        entry = os.path.join(sys._MEIPASS, "UI", "dist", "index.html")
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
        text_select=True,
    )
    webview.start(debug=dev_mode)


if __name__ == "__main__":
    main()
