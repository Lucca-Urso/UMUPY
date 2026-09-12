import providers
from providers import base


def normalize(track):
    if track.get("source"):
        return track

    if track.get("spotify_id"):
        return {**track, "source": "spotify", "id": track["spotify_id"]}

    return {**track, "source": "youtube"}


def search_order(track):
    source = track["source"]

    if providers.get(source).DOWNLOADABLE:
        return [source, *providers.fallbacks_for(source)]

    return providers.fallbacks_for(source)


def get_client(clients, name):
    if name not in clients:
        clients[name] = providers.get(name).open_client()

    return clients[name]


def attach_origin(match, track, provider):
    result = dict(match)
    result.setdefault("source", provider)

    if track.get("spotify_id"):
        result["spotify_id"] = track["spotify_id"]

    return result


def find_download_source(track, clients, on_attempt=None, order=None):
    track = normalize(track)
    order = order or search_order(track)
    attempts = []
    last_error = None

    for position, name in enumerate(order):
        if on_attempt:
            on_attempt(name, position > 0)

        if name == track["source"]:
            match = attach_origin({**track, "score": 100}, track, name)
            attempts.append({"provider": name, "status": "matched", "error": None, "score": 100})
            return match, attempts

        try:
            match = providers.get(name).search(get_client(clients, name), track)
        except Exception as error:
            last_error = error
            attempts.append({"provider": name, "status": "error", "error": str(error), "score": None})
            continue

        if match:
            attempts.append({"provider": name, "status": "matched", "error": None, "score": match.get("score")})
            return attach_origin(match, track, name), attempts

        attempts.append({"provider": name, "status": "not_found", "error": None, "score": None})

    if attempts and all(attempt["status"] == "error" for attempt in attempts):
        raise last_error

    return None, attempts


def describe_attempt(attempt):
    provider = providers.get(attempt["provider"]).NAME

    if attempt["status"] == "matched":
        return f"matched on {provider} (score {attempt['score']})"

    if attempt["status"] == "error":
        return f"{provider} failed: {attempt['error']}"

    return f"not found on {provider}"


def track_label(track):
    return base.track_label(track)
