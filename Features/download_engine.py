import random
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import matching
import providers
import yt_downloader

WORKERS = {"youtube": 3, "soundcloud": 2}
SLEEP_ARGUMENTS = {
    "youtube": ["--sleep-requests", "2", "--sleep-interval", "6", "--max-sleep-interval", "13"],
    "soundcloud": ["--sleep-requests", "1", "--sleep-interval", "8", "--max-sleep-interval", "15"],
}
RATE_LIMITS = {"youtube": (500, 3600), "soundcloud": (300, 600)}
BACKOFF_STEPS = (30, 60, 120, 300, 900)
BLOCK_PATTERNS = ("429", "too many requests", "sign in to confirm", "not a bot", "rate limit", "rate-limit")
TRANSIENT_PATTERNS = ("403", "forbidden", "timed out", "connection reset", "temporarily")
MAX_BLOCK_RETRIES = 2
MAX_TRANSIENT_RETRIES = 1
TRANSIENT_RETRY_DELAY = 8


def is_block_error(error_text):
    text = (error_text or "").lower()
    return any(pattern in text for pattern in BLOCK_PATTERNS)


def is_transient_error(error_text):
    text = (error_text or "").lower()
    return not is_block_error(text) and any(pattern in text for pattern in TRANSIENT_PATTERNS)


class RateLimiter:
    def __init__(self, limits=RATE_LIMITS, clock=time.monotonic, sleeper=time.sleep):
        self.limits = limits
        self.clock = clock
        self.sleeper = sleeper
        self.history = {name: deque() for name in limits}
        self.lock = threading.Lock()

    def acquire(self, provider):
        if provider not in self.limits:
            return

        limit, window = self.limits[provider]

        while True:
            with self.lock:
                now = self.clock()
                stamps = self.history[provider]

                while stamps and now - stamps[0] >= window:
                    stamps.popleft()

                if len(stamps) < limit:
                    stamps.append(now)
                    return

                wait = window - (now - stamps[0])

            self.sleeper(max(wait, 0.1))


class DownloadEngine:
    def __init__(self, output_directory, ffmpeg_path, clients=None, on_event=None, template="%(title)s.%(ext)s",
                 workers=None, clock=time.monotonic, sleeper=time.sleep, jitter=random.uniform):
        self.output_directory = output_directory
        self.ffmpeg_path = ffmpeg_path
        self.template = template
        self.clients = clients if clients is not None else {}
        self.on_event = on_event or (lambda kind, payload: None)
        self.workers = workers or WORKERS
        self.clock = clock
        self.sleeper = sleeper
        self.jitter = jitter
        self.limiter = RateLimiter(clock=clock, sleeper=sleeper)
        self.lock = threading.Lock()
        self.script_directory = yt_downloader.get_script_directory()
        self.resume_at = 0.0
        self.paused_reason = None
        self.block_count = 0
        self.active = {}
        self.results = []

    def emit(self, kind, payload):
        self.on_event(kind, payload)

    def snapshot(self):
        with self.lock:
            paused = self.clock() < self.resume_at
            return {
                "active": [dict(item) for item in self.active.values()],
                "paused": paused,
                "paused_reason": self.paused_reason if paused else None,
                "resume_in": max(0, round(self.resume_at - self.clock())) if paused else 0,
            }

    def set_active(self, track, provider, retrying):
        with self.lock:
            self.active[track["id"]] = {
                "id": track["id"],
                "title": track["title"],
                "provider": provider,
                "retrying": retrying,
            }

    def clear_active(self, track):
        with self.lock:
            self.active.pop(track["id"], None)

    def wait_if_paused(self):
        while True:
            with self.lock:
                remaining = self.resume_at - self.clock()

            if remaining <= 0:
                return

            self.sleeper(min(remaining, 1.0))

    def pause(self, reason):
        with self.lock:
            step = BACKOFF_STEPS[min(self.block_count, len(BACKOFF_STEPS) - 1)]
            self.block_count += 1
            delay = step + self.jitter(0, step * 0.2)
            self.resume_at = max(self.resume_at, self.clock() + delay)
            self.paused_reason = reason

        self.emit("paused", {"reason": reason, "seconds": round(delay)})
        return delay

    def download_once(self, candidate, provider):
        video = {**candidate, "source": provider}
        return yt_downloader.download_video(
            video, self.output_directory, self.template, self.script_directory, self.ffmpeg_path,
            capture=True, sleep_arguments=SLEEP_ARGUMENTS.get(provider),
        )

    def attempt(self, track, candidate, provider, retrying):
        blocks = 0
        transient = 0

        while True:
            self.wait_if_paused()
            self.limiter.acquire(provider)
            self.set_active(track, provider, retrying)
            return_code, error_text = self.download_once(candidate, provider)

            if return_code == 0:
                return True, None

            if is_block_error(error_text) and blocks < MAX_BLOCK_RETRIES:
                blocks += 1
                self.pause(error_text)
                self.emit("attempt", {"track": track, "provider": provider, "status": "blocked", "error": error_text})
                continue

            if is_transient_error(error_text) and transient < MAX_TRANSIENT_RETRIES:
                transient += 1
                self.emit("attempt", {"track": track, "provider": provider, "status": "retrying", "error": error_text})
                self.sleeper(TRANSIENT_RETRY_DELAY + self.jitter(0, 4))
                continue

            return False, error_text

    def next_candidate(self, track, tried):
        order = [name for name in providers.DOWNLOAD_ORDER if name not in tried]

        if not order:
            return None, []

        try:
            match, attempts = matching.find_download_source(track, self.clients, order=order)
        except Exception as error:
            return None, [{"provider": order[0], "status": "error", "error": str(error), "score": None}]

        return match, attempts

    def process(self, track):
        candidate = dict(track)
        provider = candidate.get("source") or "youtube"
        tried = []
        retrying = False

        try:
            while True:
                last_candidate = candidate

                if candidate.get("unavailable"):
                    ok, error_text = False, candidate["unavailable"]
                else:
                    ok, error_text = self.attempt(track, candidate, provider, retrying)

                tried.append(provider)

                if ok:
                    self.finish(track, True, candidate, provider, None)
                    return

                self.emit("attempt", {"track": track, "provider": provider, "status": "failed", "error": error_text})
                candidate, attempts = self.next_candidate(track, tried)

                for item in attempts:
                    if item["status"] != "matched":
                        self.emit("attempt", {"track": track, "provider": item["provider"], "status": item["status"], "error": item.get("error")})

                if not candidate:
                    self.finish(track, False, last_candidate, provider, error_text)
                    return

                provider = candidate["source"]
                retrying = True
                self.emit("attempt", {"track": track, "provider": provider, "status": "retrying", "error": None})
        finally:
            self.clear_active(track)

    def finish(self, track, ok, candidate, provider, error_text):
        result = {
            "id": track["id"],
            "title": track["title"],
            "url": (candidate or track).get("url"),
            "provider": provider,
            "ok": ok,
            "error": error_text,
        }

        with self.lock:
            self.results.append(result)

        self.emit("finished", result)

    def run(self, tracks):
        groups = {}

        for track in tracks:
            groups.setdefault(track.get("source") or "youtube", []).append(track)

        pools = []

        try:
            for source, items in groups.items():
                pool = ThreadPoolExecutor(max_workers=self.workers.get(source, 1))
                pools.append(pool)

                for track in items:
                    pool.submit(self.process, track)
        finally:
            for pool in pools:
                pool.shutdown(wait=True)

        with self.lock:
            return list(self.results)
