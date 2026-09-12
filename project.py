import argparse
import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(PROJECT_DIR, "UI")


def run(command, cwd=PROJECT_DIR):
    print(f"\n$ {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd)

    if result.returncode != 0:
        print(f"\n[ERROR] Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def npm_command():
    npm = shutil.which("npm.cmd") if os.name == "nt" else None
    return npm or shutil.which("npm")


def install_python():
    run([sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"])


def install_ui():
    npm = npm_command()

    if not npm:
        print("[ERROR] npm not found. Install Node.js 18+ from https://nodejs.org")
        sys.exit(1)

    run([npm, "install"], cwd=UI_DIR)
    run([npm, "run", "build"], cwd=UI_DIR)


def test():
    run([sys.executable, "-m", "pytest"])


def start(dev=False):
    command = [sys.executable, os.path.join(PROJECT_DIR, "app.py")]

    if dev:
        command.append("--dev")

    run(command)


def setup():
    install_python()
    install_ui()
    test()
    print("\n[OK] Setup complete. Start the app with: project --run")


def build_parser():
    parser = argparse.ArgumentParser(prog="project", description="UMUPY project tasks")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true", help="install Python and UI dependencies, build the UI and run the tests")
    group.add_argument("--test", action="store_true", help="run the unit tests")
    group.add_argument("--ui", action="store_true", help="install UI dependencies and build the frontend")
    group.add_argument("--run", action="store_true", help="start the desktop app")
    group.add_argument("--dev", action="store_true", help="start the desktop app against the Vite dev server")
    return parser


def main(argv=None):
    arguments = build_parser().parse_args(argv)

    if arguments.setup:
        setup()
    elif arguments.test:
        test()
    elif arguments.ui:
        install_ui()
    elif arguments.run:
        start()
    elif arguments.dev:
        start(dev=True)


if __name__ == "__main__":
    main()
