import os

import history
import providers
import sync_playlists
from api import base, sources

SYNC_DEFAULTS = {
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


class SynchronizerApi:
    def __init__(self):
        self._sync = base.JobStatus(**SYNC_DEFAULTS)

    def select_folder(self):
        return base.pick_path("folder")

    def start_sync_analysis(self, urls, folder=None, folder_factory=None, scan_folders=None):
        urls = [urls] if isinstance(urls, str) else list(urls)
        self._sync.reset(running=True, phase="fetching", folder=folder)
        base.start_thread(self._sync_worker, urls, folder, folder_factory, scan_folders)
        return True

    def _sync_worker(self, urls, folder, folder_factory=None, scan_folders=None):
        status = self._sync

        def work(context):
            index = base.build_scan_index(scan_folders)
            found, tracks = sources.resolve_sources(urls, status)
            name = sources.describe_sources(found)

            if not tracks:
                raise Exception(sources.first_source_error(found))

            target_folder = folder

            if not target_folder and folder_factory:
                target_folder = folder_factory(name)
                os.makedirs(target_folder, exist_ok=True)

            if not target_folder:
                raise Exception("Choose a folder to sync into.")

            status.update(playlist=name, phase="comparing", folder=target_folder)
            folder_path = target_folder

            local_files = sync_playlists.build_local_index(folder_path)
            matched, missing, orphans = sync_playlists.compare_playlist_with_folder(tracks, local_files)
            healed = sync_playlists.heal_ids(matched)

            status.update(in_sync=len(matched), total=len(missing), phase="matching")

            run_id = history.start_run("sync_check", target=name, total=len(tracks))
            context["run_id"] = run_id
            sources.log_source_errors(run_id, found)

            if healed:
                history.log_item(run_id, f"{healed} file(s) tagged with their provider id", "ok")

            matcher = sources.FallbackMatcher(run_id, status)
            missing_entries = []

            for track in missing:
                video, _ = matcher.match(track)

                if video:
                    video["duplicate"] = index.contains(track["source"], track["id"])

                missing_entries.append({
                    "title": track["title"],
                    "artists": track["artists"],
                    "source": track["source"],
                    "id": track["id"],
                    "spotify_id": track.get("spotify_id"),
                    "video": video,
                })
                status.increment("processed")

            still_missing, reconciled = sync_playlists.reconcile_missing(missing_entries, orphans)

            for entry, file in reconciled:
                try:
                    sync_playlists.embed_tag(file["path"], providers.TAGS[entry["source"]], entry["id"])
                except Exception:
                    pass

                history.log_item(
                    run_id, f"{', '.join(entry['artists'])} - {entry['title']}", "ok",
                    detail=f"reconciled by {(entry['video'].get('source') or 'youtube').upper()}_ID with {file['filename']}",
                )

            for entry in still_missing:
                history.log_item(
                    run_id, f"{', '.join(entry['artists'])} - {entry['title']}",
                    "missing" if entry["video"] else "not_found",
                    detail=entry["video"]["url"] if entry["video"] else None,
                )

            for f in orphans:
                history.log_item(run_id, f["filename"], "orphan", detail=f["path"])

            status.update(
                in_sync=len(matched) + len(reconciled),
                missing=still_missing,
                orphans=[{"filename": f["filename"], "path": f["path"]} for f in orphans],
            )
            history.finish_run(run_id, "completed")

        base.run_job(status, work, "sync_check", " + ".join(urls))

    def get_sync_status(self):
        return self._sync.snapshot()

    def sync_delete(self, paths):
        folder = self._sync.get("folder")
        playlist = self._sync.get("playlist")

        run_id = history.start_run("sync_delete", target=playlist or folder, total=len(paths))
        results = sync_playlists.delete_files(paths, folder or "")

        for result in results:
            history.log_item(
                run_id, os.path.basename(result["path"]), "ok" if result["ok"] else "failed",
                detail=result["path"], error=result["error"],
            )

        failed = [r for r in results if not r["ok"]]
        history.finish_run(run_id, "completed_with_errors" if failed else "completed")
        return results
