import json
import os

import yt_downloader

DEFAULTS = {"cookies_browser": None}


def get_settings_path():
    return os.path.join(yt_downloader.get_dependencies_directory(), "settings.json")


def load():
    path = get_settings_path()

    if not os.path.isfile(path):
        return dict(DEFAULTS)

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return dict(DEFAULTS)

    return {**DEFAULTS, **{key: data.get(key) for key in DEFAULTS}}


def save(**changes):
    settings = {**load(), **{key: value for key, value in changes.items() if key in DEFAULTS}}
    path = get_settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)

    return settings
