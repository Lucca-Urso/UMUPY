import os
import re

import history
import yt_downloader
from api import base

CHAIN_DEFAULTS = {
    "running": False,
    "stage": None,
    "folder": None,
    "playlist": None,
    "rekordbox": None,
    "error": None,
}


def safe_folder_name(name):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", name or "").strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] or "Playlist"


def default_sync_folder(name):
    return os.path.join(yt_downloader.get_downloads_directory(), safe_folder_name(name))


class ChainApi:
    def __init__(self):
        self._chain = base.JobStatus(**CHAIN_DEFAULTS)

    def start_chain(self, urls, folder=None, scan_folders=None):
        self._chain.reset(running=True, stage="analyzing", folder=folder)
        return self.start_sync_analysis(urls, folder or None, default_sync_folder, scan_folders)

    def start_chain_download(self, videos, rekordbox=True):
        folder = self._sync.get("folder")
        playlist = self._sync.get("playlist")

        if not folder:
            return {"error": "Run the analysis first."}

        self._chain.reset(running=True, stage="downloading", folder=folder, playlist=playlist)
        self._download.reset(running=True, total=len(videos), output_directory=folder)
        base.start_thread(self._chain_worker, videos, folder, playlist, rekordbox)
        return folder

    def _chain_worker(self, videos, folder, playlist, rekordbox):
        status = self._chain

        def work(context):
            if videos:
                run_id = history.start_run("sync_download", target=playlist or folder, total=len(videos))
                context["run_id"] = run_id
                self._run_engine(videos, folder, run_id)

            self._download.update(running=False, current=None)

            if rekordbox:
                status.update(stage="planning")
                status.update(rekordbox=self.rekordbox_sync_plan(folder, playlist))

            status.update(stage="review")

        base.run_job(status, work, "sync_download", playlist or folder)

    def get_chain_status(self):
        status = self._chain.snapshot()
        status["download"] = self.get_status()
        status["sync"] = self.get_sync_status()
        return status
