import os
import sys

import history


def test_directories_are_created_under_project(project_dir):
    assert history.get_history_directory() == str(project_dir / "History")
    assert history.get_logs_directory() == str(project_dir / "History" / "logs")
    assert os.path.isdir(project_dir / "History" / "logs")
    assert history.get_database_path().endswith("history.db")


def test_project_directory_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))

    assert history.get_project_directory() == str(tmp_path / "UMUPY")
    assert os.path.isdir(tmp_path / "UMUPY")


def test_project_directory_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert history.get_project_directory().endswith("UMUPY")


def test_run_lifecycle_and_log_file(project_dir):
    run_id = history.start_run("youtube_download", target="Playlist", total=2)
    history.log_item(run_id, "Track A", "ok", detail="https://yt/a")
    history.log_item(run_id, "Track B", "failed", detail="https://yt/b", error="boom")
    history.finish_run(run_id, "completed_with_errors")

    runs = history.list_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["status"] == "completed_with_errors"
    assert runs[0]["succeeded"] == 1
    assert runs[0]["failed"] == 1
    assert runs[0]["items"] == 2

    detail = history.get_run(run_id)
    assert detail["run"]["operation"] == "youtube_download"
    assert [item["status"] for item in detail["items"]] == ["ok", "failed"]
    assert detail["items"][1]["error"] == "boom"

    logs = os.listdir(project_dir / "History" / "logs")
    assert len(logs) == 1
    content = (project_dir / "History" / "logs" / logs[0]).read_text(encoding="utf-8")
    assert "RUN START operation=youtube_download" in content
    assert "OK Track A | https://yt/a" in content
    assert "FAILED Track B | https://yt/b | boom" in content
    assert "RUN END status=completed_with_errors" in content


def test_get_run_for_unknown_id(project_dir):
    assert history.get_run("missing") == {"run": None, "items": []}


def test_append_log_ignores_unknown_run(project_dir):
    history._append_log("missing", "ignored")

    assert not os.path.exists(project_dir / "History" / "logs")


def test_list_runs_orders_newest_first_and_limits(project_dir, monkeypatch):
    stamps = iter(["2026-01-01 10:00:00", "2026-01-01 10:00:00", "2026-01-02 10:00:00", "2026-01-02 10:00:00"])
    monkeypatch.setattr(history, "_now", lambda: next(stamps))

    first = history.start_run("a")
    second = history.start_run("b")

    runs = history.list_runs()
    assert [run["id"] for run in runs] == [second, first]
    assert len(history.list_runs(limit=1)) == 1
