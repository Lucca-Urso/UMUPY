import os
import shutil
import subprocess
import sys

import pytest

import project


@pytest.fixture
def commands(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, cwd=None: calls.append((command, cwd)) or type("R", (), {"returncode": 0})())
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    return calls


def test_run_exits_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 3})())

    with pytest.raises(SystemExit) as exit_info:
        project.run(["false"])

    assert exit_info.value.code == 3
    assert "Command failed" in capsys.readouterr().out


def test_npm_command_on_windows(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(shutil, "which", lambda name: "/npm.cmd" if name == "npm.cmd" else None)

    assert project.npm_command() == "/npm.cmd"


def test_setup_runs_every_step(commands, capsys):
    project.main(["--setup"])

    npm = project.npm_command()
    assert npm.startswith("/bin/npm")
    assert commands[0][0][-2:] == ["-r", "requirements-dev.txt"]
    assert commands[1] == ([npm, "install"], project.UI_DIR)
    assert commands[2] == ([npm, "run", "build"], project.UI_DIR)
    assert commands[3][0][-1] == "pytest"
    assert "Setup complete" in capsys.readouterr().out


def test_install_ui_without_npm(monkeypatch, capsys):
    monkeypatch.setattr(shutil, "which", lambda _: None)

    with pytest.raises(SystemExit):
        project.main(["--ui"])

    assert "npm not found" in capsys.readouterr().out


def test_individual_tasks(commands):
    project.main(["--test"])
    project.main(["--run"])
    project.main(["--dev"])

    assert commands[0][0][-1] == "pytest"
    assert commands[1][0][-1].endswith("app.py")
    assert commands[2][0][-1] == "--dev"


def test_requires_one_task():
    with pytest.raises(SystemExit):
        project.main([])
