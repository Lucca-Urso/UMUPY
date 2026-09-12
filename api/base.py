import copy
import os
import platform
import subprocess
import threading

import history
import library
import yt_downloader

CREDENTIALS_ERROR = "Spotify credentials not found or invalid."


class JobStatus:
    def __init__(self, **defaults):
        self._defaults = defaults
        self._lock = threading.Lock()
        self._data = {}
        self.reset()

    def reset(self, **overrides):
        with self._lock:
            self._data = copy.deepcopy(self._defaults)
            self._data.update(overrides)

    def update(self, **fields):
        with self._lock:
            self._data.update(fields)

    def increment(self, key, amount=1):
        with self._lock:
            self._data[key] += amount

    def append(self, key, value):
        with self._lock:
            self._data[key].append(value)

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.update(**{key: value})

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._data)


def run_job(status, work, operation, target):
    context = {"run_id": None}

    try:
        work(context)
    except SystemExit:
        status.update(error=CREDENTIALS_ERROR)

        if context["run_id"]:
            history.finish_run(context["run_id"], "failed")
    except Exception as error:
        status.update(error=str(error))
        run_id = context["run_id"] or history.start_run(operation, target=target)
        history.log_item(run_id, "Analysis", "failed", error=str(error))
        history.finish_run(run_id, "failed")
    finally:
        status.update(running=False, phase=None)


def start_thread(target, *args):
    worker = threading.Thread(target=target, args=args, daemon=True)
    worker.start()
    return worker


def scan_paths(scan_folders):
    downloads_directory = yt_downloader.get_downloads_directory()

    if not scan_folders or "__all__" in scan_folders:
        return [downloads_directory]

    return [os.path.join(downloads_directory, name) for name in scan_folders]


def build_scan_index(scan_folders):
    if scan_folders is None:
        return library.LibraryIndex()

    return library.build_index(scan_paths(scan_folders))


def pick_path(mode="folder"):
    import webview

    window = webview.windows[0]

    if mode == "folder":
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
    else:
        result = window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Playlist files (*.txt;*.xml)",))

    if not result:
        return None

    return result[0] if isinstance(result, (list, tuple)) else result


def open_in_file_manager(directory):
    system = platform.system()

    if system == "Darwin":
        subprocess.run(["open", directory])
    elif system == "Windows":
        os.startfile(directory)
    else:
        subprocess.run(["xdg-open", directory])

    return directory
