import os
import sqlite3
import threading
import uuid
from datetime import datetime

_WRITE_LOCK = threading.RLock()
_INITIALIZED = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    target TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    total INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS run_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    title TEXT NOT NULL,
    detail TEXT,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_items_run ON run_items(run_id);
"""


def get_project_directory():
    import sys

    if getattr(sys, "frozen", False):
        directory = os.path.join(os.path.expanduser("~"), "UMUPY")
        os.makedirs(directory, exist_ok=True)
        return directory

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_history_directory():
    directory = os.path.join(get_project_directory(), "History")
    os.makedirs(directory, exist_ok=True)
    return directory


def get_logs_directory():
    directory = os.path.join(get_history_directory(), "logs")
    os.makedirs(directory, exist_ok=True)
    return directory


def get_database_path():
    return os.path.join(get_history_directory(), "history.db")


def _connect():
    path = get_database_path()
    existed = os.path.isfile(path)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row

    if not existed or path not in _INITIALIZED:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(SCHEMA)
        _INITIALIZED.add(path)

    return connection


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log_file_path(run):
    stamp = run["started_at"].replace("-", "").replace(":", "").replace(" ", "_")
    file_name = f"{stamp}_{run['operation']}_{run['id'][:8]}.txt"
    return os.path.join(get_logs_directory(), file_name)


def _append_log(run_id, message):
    with _WRITE_LOCK:
        connection = _connect()

        try:
            run = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        finally:
            connection.close()

        if run is None:
            return

        with open(_log_file_path(run), "a", encoding="utf-8") as log_file:
            log_file.write(f"[{_now()}] {message}\n")


def start_run(operation, target=None, total=0):
    run_id = uuid.uuid4().hex

    with _WRITE_LOCK:
        connection = _connect()

        try:
            connection.execute(
                "INSERT INTO runs (id, operation, target, started_at, status, total) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, operation, target, _now(), "running", total),
            )
            connection.commit()
        finally:
            connection.close()

        _append_log(run_id, f"RUN START operation={operation} target={target} total={total}")

    return run_id


def log_item(run_id, title, status, detail=None, error=None):
    with _WRITE_LOCK:
        connection = _connect()

        try:
            connection.execute(
                "INSERT INTO run_items (run_id, title, detail, status, error, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, title, detail, status, error, _now()),
            )
            connection.commit()
        finally:
            connection.close()

        line = f"{status.upper()} {title}"

        if detail:
            line += f" | {detail}"

        if error:
            line += f" | {error}"

        _append_log(run_id, line)


def finish_run(run_id, status="completed"):
    with _WRITE_LOCK:
        connection = _connect()

        try:
            connection.execute(
                "UPDATE runs SET finished_at = ?, status = ? WHERE id = ?",
                (_now(), status, run_id),
            )
            connection.commit()
            counts = connection.execute(
                "SELECT status, COUNT(*) AS n FROM run_items WHERE run_id = ? GROUP BY status",
                (run_id,),
            ).fetchall()
        finally:
            connection.close()

        summary = " ".join(f"{row['status']}={row['n']}" for row in counts)
        _append_log(run_id, f"RUN END status={status} {summary}".strip())


def list_runs(limit=50):
    connection = _connect()

    try:
        rows = connection.execute(
            """
            SELECT r.*,
                SUM(CASE WHEN i.status = 'ok' THEN 1 ELSE 0 END) AS succeeded,
                SUM(CASE WHEN i.status = 'failed' THEN 1 ELSE 0 END) AS failed,
                COUNT(i.id) AS items
            FROM runs r
            LEFT JOIN run_items i ON i.run_id = r.id
            GROUP BY r.id
            ORDER BY r.started_at DESC, r.rowid DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        connection.close()

    return [dict(row) for row in rows]


def get_run(run_id):
    connection = _connect()

    try:
        run = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        items = connection.execute(
            "SELECT * FROM run_items WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    finally:
        connection.close()

    return {"run": dict(run) if run else None, "items": [dict(item) for item in items]}
