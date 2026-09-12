import os

import history
import rekordbox_playlist_creator as rpc
import rekordbox_sync
from api import base


class PlaylistBuilderApi:
    def __init__(self):
        self._rekordbox = None

    def rekordbox_select_source(self, mode):
        return base.pick_path(mode)

    def rekordbox_xml_example(self):
        return {
            "example": rpc.XML_MINIMUM_EXAMPLE,
            "rules": [
                "COLLECTION lists the tracks: each TRACK needs a TrackID and a Name (or a Location pointing to the file).",
                "Artist is optional; other attributes are ignored.",
                "PLAYLISTS holds NODE elements with Type=\"1\" and a Name; each TRACK inside references a TrackID through Key.",
                "Files exported by RekordBox already follow this format.",
            ],
        }

    def _open_rekordbox(self):
        if self._rekordbox is not None:
            try:
                self._rekordbox["db"].close()
            except Exception:
                pass

            self._rekordbox = None

        return rpc.open_database()

    def rekordbox_analyze(self, source_path):
        try:
            playlists = rpc.load_playlists_from_source(source_path)
        except ValueError as error:
            return {"error": str(error)}

        if not playlists:
            return {"error": "No playlists found in the selected source."}

        try:
            db = self._open_rekordbox()
        except Exception as error:
            return {"error": f"Could not open the RekordBox database: {error}"}

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
        if self._rekordbox is None or "results" not in self._rekordbox:
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

    def rekordbox_sync_plan(self, folder, playlist_name=None):
        if not folder or not os.path.isdir(folder):
            return {"error": "Choose an existing folder first."}

        try:
            db = self._open_rekordbox()
        except Exception as error:
            return {"error": f"Could not open the RekordBox database: {error}"}

        plan = rekordbox_sync.plan_sync(db, folder, playlist_name or None)
        self._rekordbox = {"db": db, "plan": plan, "source": folder}

        return {
            "playlist": plan["playlist"],
            "exists": plan["exists"],
            "folder": folder,
            "running": rpc.rekordbox_is_running(),
            "add": [{"path": t["path"], "title": t["title"], "artist": t["artist"], "in_collection": t["in_collection"]} for t in plan["add"]],
            "keep": len(plan["keep"]),
            "remove": [{"song_id": s["song_id"], "path": s["path"], "title": s["title"], "artist": s["artist"]} for s in plan["remove"]],
        }

    def rekordbox_sync_apply(self, add_paths, remove_song_ids):
        if self._rekordbox is None or "plan" not in self._rekordbox:
            return {"error": "Nothing planned yet."}

        if rpc.rekordbox_is_running():
            return {"error": "RekordBox is running. Close it before writing to the database."}

        plan = self._rekordbox["plan"]
        run_id = history.start_run("rekordbox_sync", target=plan["playlist"], total=len(add_paths) + len(remove_song_ids))
        backup_root = os.path.join(history.get_history_directory(), "rekordbox_backups")
        result = rekordbox_sync.apply_sync(self._rekordbox["db"], plan, add_paths, remove_song_ids, backup_root)

        if result["backup"]:
            history.log_item(run_id, "Database backup", "ok", detail=result["backup"])

        if result["created"]:
            history.log_item(run_id, plan["playlist"], "ok", detail="playlist created")

        for path in result["added"]:
            history.log_item(run_id, os.path.basename(path), "ok", detail=f"added to {plan['playlist']}")

        for path in result["removed"]:
            history.log_item(run_id, os.path.basename(path or ""), "ok", detail=f"removed from {plan['playlist']}")

        for item in result["errors"]:
            history.log_item(run_id, os.path.basename(item["path"] or ""), "failed", detail=item["path"], error=item["error"])

        history.finish_run(run_id, "completed_with_errors" if result["errors"] else "completed")

        return {
            "backup": result["backup"],
            "created": result["created"],
            "added": len(result["added"]),
            "removed": len(result["removed"]),
            "errors": result["errors"],
        }
