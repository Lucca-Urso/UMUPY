MATCH_THRESHOLD = 75
DURATION_TOLERANCE = 5


def retry_call(operation, attempts=4, delay=2):
    import time

    for attempt in range(attempts):
        try:
            return operation()
        except Exception:
            if attempt == attempts - 1:
                raise

            time.sleep(delay * (attempt + 1))


def make_track(source, track_id, title, artists=None, duration=None, url=None, **extra):
    track = {
        "id": str(track_id),
        "title": title or "",
        "artists": [artist for artist in (artists or []) if artist],
        "duration": duration,
        "url": url,
        "source": source,
    }
    track.update(extra)
    return track


def track_label(track):
    artists = ", ".join(track.get("artists") or [])
    return f"{artists} - {track['title']}" if artists else track["title"]


def search_query(track):
    return f"{' '.join(track.get('artists') or [])} {track['title']}".strip()


def score_match(track, candidate_title, candidate_artists, candidate_duration=None):
    from thefuzz import fuzz

    artist_names = " ".join(track.get("artists") or [])
    title_score = fuzz.token_set_ratio(track["title"], candidate_title or "")
    artist_score = fuzz.token_set_ratio(artist_names, candidate_artists or "") if artist_names else title_score
    score = title_score * 0.6 + artist_score * 0.4

    if candidate_duration and track.get("duration") and abs(candidate_duration - track["duration"]) <= DURATION_TOLERANCE:
        score += 10

    return score


def pick_best(track, candidates):
    best = None
    best_score = 0.0

    for candidate in candidates:
        score = score_match(track, candidate["title"], " ".join(candidate.get("artists") or []), candidate.get("duration"))

        if score > best_score:
            best_score = score
            best = candidate

    if best is None or best_score < MATCH_THRESHOLD:
        return None

    return {**best, "score": round(best_score)}
