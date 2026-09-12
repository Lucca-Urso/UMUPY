import pytest

import matching
import providers
from providers import soundcloud, youtube

SPOTIFY_TRACK = {"spotify_id": "sp1", "title": "Song", "artists": ["Artist"], "duration": 200}
YT_MATCH = {"id": "yt1", "title": "Song", "url": "u", "source": "youtube", "score": 90}
SC_MATCH = {"id": "sc1", "title": "Song", "url": "u", "source": "soundcloud", "score": 80}


def test_normalize_and_search_order():
    normalized = matching.normalize(SPOTIFY_TRACK)
    assert normalized["source"] == "spotify"
    assert normalized["id"] == "sp1"
    assert matching.normalize({"title": "x"})["source"] == "youtube"
    assert matching.normalize({"source": "soundcloud", "id": "1"}) == {"source": "soundcloud", "id": "1"}

    assert matching.search_order(normalized) == ["youtube", "soundcloud"]
    assert matching.search_order({"source": "soundcloud"}) == ["soundcloud", "youtube"]
    assert matching.search_order({"source": "youtube"}) == ["youtube", "soundcloud"]


def test_get_client_opens_lazily(monkeypatch):
    monkeypatch.setattr(youtube, "open_client", lambda: "yt-client")
    clients = {}

    assert matching.get_client(clients, "youtube") == "yt-client"
    assert matching.get_client(clients, "youtube") == "yt-client"
    assert matching.get_client({"soundcloud": "given"}, "soundcloud") == "given"


def test_find_download_source_first_provider_matches(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: dict(YT_MATCH))
    monkeypatch.setattr(soundcloud, "search", lambda client, track: pytest.fail("should not reach soundcloud"))
    events = []

    match, attempts = matching.find_download_source(
        SPOTIFY_TRACK, {"youtube": "c"}, on_attempt=lambda p, retrying: events.append((p, retrying))
    )

    assert match["id"] == "yt1"
    assert match["spotify_id"] == "sp1"
    assert attempts == [{"provider": "youtube", "status": "matched", "error": None, "score": 90}]
    assert events == [("youtube", False)]


def test_find_download_source_falls_back_to_soundcloud(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: None)
    monkeypatch.setattr(soundcloud, "search", lambda client, track: dict(SC_MATCH))
    events = []

    match, attempts = matching.find_download_source(
        SPOTIFY_TRACK, {"youtube": "c", "soundcloud": None}, on_attempt=lambda p, r: events.append((p, r))
    )

    assert match["source"] == "soundcloud"
    assert match["spotify_id"] == "sp1"
    assert [a["status"] for a in attempts] == ["not_found", "matched"]
    assert events == [("youtube", False), ("soundcloud", True)]


def test_find_download_source_error_then_match(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: (_ for _ in ()).throw(ConnectionError("down")))
    monkeypatch.setattr(soundcloud, "search", lambda client, track: dict(SC_MATCH))

    match, attempts = matching.find_download_source(SPOTIFY_TRACK, {"youtube": "c", "soundcloud": None})

    assert match["id"] == "sc1"
    assert attempts[0] == {"provider": "youtube", "status": "error", "error": "down", "score": None}
    assert attempts[1]["status"] == "matched"


def test_find_download_source_nothing_found(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: None)
    monkeypatch.setattr(soundcloud, "search", lambda client, track: None)

    match, attempts = matching.find_download_source(SPOTIFY_TRACK, {"youtube": "c", "soundcloud": None})

    assert match is None
    assert [a["status"] for a in attempts] == ["not_found", "not_found"]


def test_find_download_source_raises_when_every_provider_fails(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: (_ for _ in ()).throw(ConnectionError("a")))
    monkeypatch.setattr(soundcloud, "search", lambda client, track: (_ for _ in ()).throw(ConnectionError("b")))

    with pytest.raises(ConnectionError, match="b"):
        matching.find_download_source(SPOTIFY_TRACK, {"youtube": "c", "soundcloud": None})


def test_find_download_source_partial_errors_return_none(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: (_ for _ in ()).throw(ConnectionError("a")))
    monkeypatch.setattr(soundcloud, "search", lambda client, track: None)

    match, attempts = matching.find_download_source(SPOTIFY_TRACK, {"youtube": "c", "soundcloud": None})

    assert match is None
    assert [a["status"] for a in attempts] == ["error", "not_found"]


def test_downloadable_source_is_used_directly(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: pytest.fail("no search expected"))
    track = {"source": "soundcloud", "id": "sc9", "title": "T", "artists": ["A"], "url": "u"}

    match, attempts = matching.find_download_source(track, {})

    assert match["id"] == "sc9"
    assert match["score"] == 100
    assert "spotify_id" not in match
    assert attempts == [{"provider": "soundcloud", "status": "matched", "error": None, "score": 100}]


def test_custom_order_skips_own_source(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: dict(YT_MATCH))
    track = {"source": "soundcloud", "id": "sc9", "title": "T", "artists": ["A"]}

    match, attempts = matching.find_download_source(track, {"youtube": "c"}, order=providers.fallbacks_for("soundcloud"))

    assert match["source"] == "youtube"
    assert attempts[0]["provider"] == "youtube"


def test_unavailable_source_track_goes_straight_to_fallback(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: dict(YT_MATCH))
    track = {"source": "soundcloud", "id": "sc9", "title": "T", "artists": ["A"], "unavailable": "DRM protected"}
    events = []

    assert matching.search_order(track) == ["youtube"]

    match, attempts = matching.find_download_source(track, {"youtube": "c"}, on_attempt=lambda p, r: events.append((p, r)))

    assert match["source"] == "youtube"
    assert attempts[0] == {"provider": "soundcloud", "status": "error", "error": "DRM protected", "score": None}
    assert attempts[1]["status"] == "matched"
    assert events == [("youtube", True)]


def test_unavailable_track_with_no_fallback_result(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: None)
    track = {"source": "soundcloud", "id": "sc9", "title": "T", "artists": ["A"], "unavailable": "DRM protected"}

    match, attempts = matching.find_download_source(track, {"youtube": "c"})

    assert match is None
    assert [a["status"] for a in attempts] == ["error", "not_found"]


def test_unsearchable_unavailable_track_is_not_searched(monkeypatch):
    monkeypatch.setattr(youtube, "search", lambda client, track: pytest.fail("must not search"))
    track = {"source": "soundcloud", "id": "1", "title": "Unknown track 1", "artists": [], "unavailable": "DRM", "searchable": False}

    match, attempts = matching.find_download_source(track, {})

    assert match is None
    assert attempts == [{"provider": "soundcloud", "status": "error", "error": "DRM", "score": None}]


def test_describe_attempt_and_label():
    assert matching.describe_attempt({"provider": "youtube", "status": "matched", "score": 90}) == "matched on youtube (score 90)"
    assert matching.describe_attempt({"provider": "soundcloud", "status": "error", "error": "x"}) == "soundcloud failed: x"
    assert matching.describe_attempt({"provider": "soundcloud", "status": "not_found"}) == "not found on soundcloud"
    assert matching.track_label(SPOTIFY_TRACK) == "Artist - Song"
