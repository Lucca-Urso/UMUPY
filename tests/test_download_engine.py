import threading

import pytest

import download_engine
import matching
import yt_downloader
from download_engine import DownloadEngine, RateLimiter


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def track(track_id, source="youtube", title=None):
    return {"id": track_id, "title": title or f"Track {track_id}", "url": f"https://{source}/{track_id}", "source": source}


@pytest.fixture
def engine_factory(tmp_path, monkeypatch):
    def make(outcomes, workers=None, clients=None):
        clock = Clock()
        events = []
        calls = []
        lock = threading.Lock()

        def fake_download(video, output_directory, template, script_directory, ffmpeg_path, capture=False, sleep_arguments=None):
            with lock:
                calls.append({"id": video["id"], "source": video["source"], "sleep": sleep_arguments})
                queue = outcomes[(video["id"], video["source"])]
                result = queue.pop(0) if isinstance(queue, list) else queue

            return result

        monkeypatch.setattr(yt_downloader, "download_video", fake_download)
        engine = DownloadEngine(
            str(tmp_path), "/bin/ffmpeg", clients=clients or {}, on_event=lambda kind, payload: events.append((kind, payload)),
            workers=workers or {"youtube": 2, "soundcloud": 1}, clock=clock, sleeper=clock.sleep, jitter=lambda a, b: 0,
        )
        return engine, events, calls, clock

    return make


def test_is_block_error():
    assert download_engine.is_block_error("ERROR: HTTP Error 429: Too Many Requests")
    assert download_engine.is_block_error("Sign in to confirm you're not a bot")
    assert not download_engine.is_block_error("ERROR: HTTP Error 403: Forbidden")
    assert not download_engine.is_block_error(None)


def test_rate_limiter_blocks_when_window_is_full():
    clock = Clock()
    limiter = RateLimiter(limits={"youtube": (2, 60)}, clock=clock, sleeper=clock.sleep)

    limiter.acquire("youtube")
    limiter.acquire("youtube")
    start = clock.now
    limiter.acquire("youtube")

    assert clock.now - start == pytest.approx(60)
    limiter.acquire("unknown")


def test_engine_downloads_all_tracks_in_parallel_pools(engine_factory):
    engine, events, calls, _ = engine_factory({
        ("a", "youtube"): (0, None),
        ("b", "youtube"): (0, None),
        ("c", "soundcloud"): (0, None),
    })

    results = engine.run([track("a"), track("b"), track("c", "soundcloud")])

    assert sorted(r["id"] for r in results) == ["a", "b", "c"]
    assert all(r["ok"] for r in results)
    assert {c["id"]: c["sleep"] for c in calls}["a"] == download_engine.SLEEP_ARGUMENTS["youtube"]
    assert {c["id"]: c["sleep"] for c in calls}["c"] == download_engine.SLEEP_ARGUMENTS["soundcloud"]
    assert [kind for kind, _ in events].count("finished") == 3
    assert engine.snapshot() == {"active": [], "paused": False, "paused_reason": None, "resume_in": 0}


def test_engine_falls_back_to_another_provider(engine_factory, monkeypatch):
    engine, events, calls, _ = engine_factory({
        ("a", "youtube"): (1, "ERROR: HTTP Error 403: Forbidden"),
        ("sc1", "soundcloud"): (0, None),
    })
    monkeypatch.setattr(
        matching, "find_download_source",
        lambda t, clients, order=None: ({"id": "sc1", "title": "SC", "url": "https://sc/1", "source": "soundcloud", "score": 80},
                                        [{"provider": "soundcloud", "status": "matched", "error": None, "score": 80}]),
    )

    results = engine.run([track("a")])

    assert results == [{"id": "a", "title": "Track a", "url": "https://sc/1", "provider": "soundcloud", "ok": True, "error": None}]
    assert [c["source"] for c in calls] == ["youtube", "soundcloud"]
    statuses = [(p["provider"], p["status"]) for k, p in events if k == "attempt"]
    assert statuses == [("youtube", "failed"), ("soundcloud", "retrying")]


def test_engine_reports_failure_when_no_fallback_found(engine_factory, monkeypatch):
    engine, events, _, _ = engine_factory({("a", "youtube"): (1, "ERROR: unavailable")})
    monkeypatch.setattr(
        matching, "find_download_source",
        lambda t, clients, order=None: (None, [{"provider": "soundcloud", "status": "not_found", "error": None, "score": None}]),
    )

    results = engine.run([track("a")])

    assert results[0]["ok"] is False
    assert results[0]["error"] == "ERROR: unavailable"
    statuses = [(p["provider"], p["status"]) for k, p in events if k == "attempt"]
    assert statuses == [("youtube", "failed"), ("soundcloud", "not_found")]


def test_engine_handles_search_errors_during_fallback(engine_factory, monkeypatch):
    engine, events, _, _ = engine_factory({("a", "soundcloud"): (1, "ERROR: gone")})
    monkeypatch.setattr(matching, "find_download_source", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down")))

    results = engine.run([track("a", "soundcloud")])

    assert results[0]["ok"] is False
    statuses = [(p["provider"], p["status"], p["error"]) for k, p in events if k == "attempt"]
    assert statuses == [("soundcloud", "failed", "ERROR: gone"), ("youtube", "error", "down")]


def test_engine_stops_when_every_provider_was_tried(engine_factory, monkeypatch):
    engine, _, _, _ = engine_factory({
        ("a", "youtube"): (1, "ERROR: x"),
        ("sc", "soundcloud"): (1, "ERROR: y"),
    })
    monkeypatch.setattr(
        matching, "find_download_source",
        lambda t, clients, order=None: ({"id": "sc", "title": "SC", "url": "u", "source": "soundcloud", "score": 80}, []),
    )

    results = engine.run([track("a")])

    assert results[0]["ok"] is False
    assert results[0]["provider"] == "soundcloud"
    assert results[0]["error"] == "ERROR: y"


def test_engine_pauses_on_block_and_retries_same_provider(engine_factory):
    engine, events, calls, clock = engine_factory({
        ("a", "youtube"): [(1, "ERROR: HTTP Error 429: Too Many Requests"), (0, None)],
    })

    start = clock.now
    results = engine.run([track("a")])

    assert results[0]["ok"] is True
    assert [c["source"] for c in calls] == ["youtube", "youtube"]
    paused = [p for k, p in events if k == "paused"]
    assert paused == [{"reason": "ERROR: HTTP Error 429: Too Many Requests", "seconds": 30}]
    assert clock.now - start >= 30
    assert [p["status"] for k, p in events if k == "attempt"] == ["blocked"]


def test_engine_gives_up_after_repeated_blocks(engine_factory, monkeypatch):
    engine, events, calls, _ = engine_factory({
        ("a", "youtube"): [(1, "429"), (1, "429"), (1, "429")],
    })
    monkeypatch.setattr(matching, "find_download_source", lambda *a, **k: (None, []))

    results = engine.run([track("a")])

    assert results[0]["ok"] is False
    assert len(calls) == 3
    assert [p["seconds"] for k, p in events if k == "paused"] == [30, 60]


def test_pause_backoff_grows_and_snapshot_reports_it(engine_factory):
    engine, _, _, clock = engine_factory({})

    for expected in (30, 60, 120, 300, 900, 900):
        assert engine.pause("blocked") == expected
        clock.now = engine.resume_at + 1

    engine.pause("again")
    snapshot = engine.snapshot()
    assert snapshot["paused"] is True
    assert snapshot["paused_reason"] == "again"
    assert snapshot["resume_in"] == 900


def test_active_tracking_and_wait_if_paused(engine_factory):
    engine, _, _, clock = engine_factory({})
    engine.set_active(track("a"), "youtube", True)

    assert engine.snapshot()["active"] == [{"id": "a", "title": "Track a", "provider": "youtube", "retrying": True}]

    engine.clear_active(track("a"))
    assert engine.snapshot()["active"] == []

    engine.resume_at = clock.now + 2.5
    engine.wait_if_paused()
    assert clock.now >= engine.resume_at


def test_next_candidate_without_remaining_providers(engine_factory):
    engine, _, _, _ = engine_factory({})

    assert engine.next_candidate(track("a"), ["youtube", "soundcloud"]) == (None, [])


def test_engine_skips_download_of_unavailable_track(engine_factory, monkeypatch):
    engine, events, calls, _ = engine_factory({("y1", "youtube"): (0, None)})
    monkeypatch.setattr(
        matching, "find_download_source",
        lambda t, clients, order=None: ({"id": "y1", "title": "YT", "url": "u", "source": "youtube", "score": 90}, []),
    )
    unavailable = {**track("a", "soundcloud"), "unavailable": "DRM protected"}

    results = engine.run([unavailable])

    assert results[0]["ok"] is True
    assert [c["source"] for c in calls] == ["youtube"]
    assert [(p["provider"], p["status"], p["error"]) for k, p in events if k == "attempt"][0] == ("soundcloud", "failed", "DRM protected")


def test_engine_defaults(tmp_path):
    engine = DownloadEngine(str(tmp_path), "/bin/ffmpeg")

    assert engine.workers is download_engine.WORKERS
    engine.emit("noop", {})
