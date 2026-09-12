import os
import platform
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(sys._MEIPASS, "Features"))
else:
    sys.path.insert(0, os.path.join(PROJECT_DIR, "Features"))

if platform.system() == "Darwin":
    os.environ["PATH"] = os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin"

from api import UmupyApi


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
