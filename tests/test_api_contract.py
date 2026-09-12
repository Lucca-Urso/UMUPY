import os
import re

from api import UmupyApi

UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "UI", "src")
CALL_PATTERN = re.compile(r"(?:call|usePolling)\('([a-z_]+)'")


def ui_method_names():
    names = set()

    for root, _, files in os.walk(UI_DIR):
        for name in files:
            if name.endswith((".jsx", ".js")):
                with open(os.path.join(root, name), encoding="utf-8") as handle:
                    names.update(CALL_PATTERN.findall(handle.read()))

    return names


def test_every_method_called_by_the_ui_exists_on_the_api(api):
    missing = sorted(name for name in ui_method_names() if not callable(getattr(api, name, None)))

    assert missing == []


def test_no_private_helpers_are_exposed():
    exposed = {name for name in dir(UmupyApi) if not name.startswith("_") and callable(getattr(UmupyApi, name))}

    assert "run_engine" not in exposed
    assert {"start_analysis", "start_chain", "rekordbox_sync_apply", "setup_status"} <= exposed
