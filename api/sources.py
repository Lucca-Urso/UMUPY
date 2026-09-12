import history
import matching
import providers
import spotify_converter

UNSUPPORTED_URL = "Unsupported URL. Paste a YouTube, Spotify or SoundCloud link."
NO_TRACKS = "No tracks found in the given links."


def network_failure_message(count):
    return f"Network failed {count} times in a row while matching. Check your connection and try again."


def resolve_sources(urls, status):
    sources = []
    tracks = []
    seen = set()
    clients = {}

    for url in urls:
        name = providers.detect(url)
        entry = {"url": url, "provider": name, "name": None, "total": 0, "error": None}

        if not name:
            entry["error"] = UNSUPPORTED_URL
        else:
            provider = providers.get(name)

            if name == "spotify":
                if "spotify" not in clients:
                    clients["spotify"] = provider.open_client()

                result = provider.resolve(url, clients["spotify"])
            else:
                result = provider.resolve(url)

            entry["name"] = result["name"]
            entry["total"] = len(result["tracks"])
            entry["error"] = result["error"]

            for track in result["tracks"]:
                key = (track["source"], track["id"])

                if key not in seen:
                    seen.add(key)
                    tracks.append(track)

        sources.append(entry)
        status.update(sources=[dict(source) for source in sources])

    return sources, tracks


def describe_sources(sources):
    return " + ".join(source["name"] or source["provider"] or source["url"] for source in sources)


def first_source_error(sources):
    return next((source["error"] for source in sources if source["error"]), NO_TRACKS)


def log_source_errors(run_id, sources):
    for source in sources:
        if source["error"]:
            history.log_item(run_id, source["url"], "failed", detail=source["provider"], error=source["error"])


def match_with_fallback(track, clients, run_id, status):
    label = matching.track_label(track)

    def on_attempt(provider, retrying):
        status.update(current={"track": label, "provider": provider, "retrying": retrying})

    try:
        match, attempts = matching.find_download_source(track, clients, on_attempt=on_attempt)
    except Exception as error:
        history.log_item(run_id, label, "failed", error=str(error))
        raise

    for attempt in attempts:
        if attempt["status"] == "matched":
            history.log_item(
                run_id, label, "ok",
                detail=f"-> {match['title']} ({match['url']}) {matching.describe_attempt(attempt)}",
            )
        elif attempt["status"] == "error":
            history.log_item(run_id, label, "failed", detail=attempt["provider"], error=attempt["error"])
        else:
            history.log_item(run_id, label, "not_found", detail=matching.describe_attempt(attempt))

    status.update(current=None)
    return match


class FallbackMatcher:
    def __init__(self, run_id, status):
        self.run_id = run_id
        self.status = status
        self.clients = {"youtube": spotify_converter.open_ytmusic()}
        self.consecutive_failures = 0

    def match(self, track):
        try:
            video = match_with_fallback(track, self.clients, self.run_id, self.status)
            self.consecutive_failures = 0
            return video, True
        except Exception:
            self.consecutive_failures += 1

            if self.consecutive_failures >= spotify_converter.MAX_CONSECUTIVE_FAILURES:
                raise Exception(network_failure_message(self.consecutive_failures))

            return None, False
