"""Offline tests for serve HTTP API helpers."""
import json

from podpull import core
from podpull.serve import server


def _eps():
    return [
        core.Episode(title="EP0", pub="Sat, 27 Jun 2026 22:02:06 GMT",
                     url="https://cdn.example/0.mp3", link="https://show/0"),
        core.Episode(title="EP1", pub="Sat, 20 Jun 2026 22:02:06 GMT",
                     url="https://cdn.example/1.mp3", link=""),
    ]


def _show():
    return core.Show(title="Demo", feed="https://feed", author="A",
                     apple_id="123", episodes=_eps())


def test_api_health():
    status, body, ctype = server.handle_api("GET", "/api/health", {}, b"")
    assert status == 200
    assert "json" in ctype
    assert json.loads(body)["ok"] is True


def test_api_list(monkeypatch):
    monkeypatch.setattr(server, "_resolve_show_from_src", lambda src: _show())
    status, body, _ = server.handle_api(
        "GET", "/api/list", {"src": ["123"], "limit": ["1"]}, b"")
    assert status == 200
    data = json.loads(body)
    assert data["show"]["title"] == "Demo"
    assert len(data["episodes"]) == 1
    assert data["episodes"][0]["url"] == "https://cdn.example/0.mp3"
    assert data["episodes"][0]["link"] == "https://show/0"


def test_api_search(monkeypatch):
    monkeypatch.setattr(core, "search_shows", lambda term, limit, country: [
        {"collectionId": 9, "collectionName": "S", "artistName": "a",
         "feedUrl": "https://f", "trackCount": 3,
         "artworkUrl600": "https://img/a.jpg"}])
    status, body, _ = server.handle_api(
        "GET", "/api/search", {"q": ["hello"]}, b"")
    assert status == 200
    data = json.loads(body)
    assert data["results"][0]["apple_id"] == "9"
    assert data["results"][0]["artwork"] == "https://img/a.jpg"
    assert data["results"][0]["feed_url"] == "https://f"


def test_api_trending(monkeypatch):
    monkeypatch.setattr(server, "get_trending_cached", lambda **k: {
        "source": "apple", "country": "US",
        "shows": [{"title": "The Daily", "apple_id": "1"}],
    })
    status, body, _ = server.handle_api(
        "GET", "/api/trending", {"source": ["apple"]}, b"")
    assert status == 200
    assert json.loads(body)["shows"][0]["title"] == "The Daily"


def test_api_resolve_xyz(monkeypatch):
    monkeypatch.setattr(core, "classify", lambda s: ("xyz_episode", s))
    monkeypatch.setattr(core, "xyz_episode_to_audio",
                        lambda s: ("https://cdn/x.m4a", "Title"))
    status, body, _ = server.handle_api(
        "POST", "/api/resolve", {},
        json.dumps({"src": "https://www.xiaoyuzhoufm.com/episode/x"}).encode())
    assert status == 200
    data = json.loads(body)
    assert data["url"].endswith(".m4a")
    assert data["title"] == "Title"


def test_api_missing_src():
    status, body, _ = server.handle_api("GET", "/api/list", {}, b"")
    assert status == 400
    assert "missing" in json.loads(body)["error"]
