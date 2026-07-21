"""Offline tests for serve trending helpers."""
from podpull.serve import trending


def test_normalize_xyzrank_item():
    item = {
        "rank": 1,
        "name": "岩中花述",
        "authorsText": "GIADA",
        "logoURL": "https://img/x.jpg",
        "links": [
            {"name": "apple", "url": "https://podcasts.apple.com/us/podcast/x/id1582119137"},
            {"name": "rss", "url": "https://feed.xyzfm.space/abc"},
            {"name": "xyz", "url": "https://www.xiaoyuzhoufm.com/podcast/abc"},
        ],
    }
    n = trending.normalize_xyzrank_item(item)
    assert n["title"] == "岩中花述"
    assert n["apple_id"] == "1582119137"
    assert n["feed"] == "https://feed.xyzfm.space/abc"
    assert n["source"] == "xyzrank"


def test_normalize_apple_entry():
    entry = {
        "im:name": {"label": "The Daily"},
        "im:artist": {"label": "NYT"},
        "im:image": [{"label": "https://img/small.jpg"}, {"label": "https://img/big.jpg"}],
        "id": {
            "label": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
            "attributes": {"im:id": "1200361736"},
        },
    }
    n = trending.normalize_apple_entry(entry, 1)
    assert n["title"] == "The Daily"
    assert n["apple_id"] == "1200361736"
    assert n["artwork"] == "https://img/big.jpg"
    assert n["rank"] == 1


def test_fetch_xyzrank_podcasts(monkeypatch):
    monkeypatch.setattr(trending.core, "fetch_json", lambda url: {
        "items": [{
            "rank": 2, "name": "A", "authorsText": "x", "logoURL": "",
            "links": [{"name": "rss", "url": "https://f/a"}],
        }]
    })
    rows = trending.fetch_xyzrank_podcasts(limit=10)
    assert len(rows) == 1
    assert rows[0]["title"] == "A"
    assert rows[0]["feed"] == "https://f/a"


def test_fetch_apple_charts(monkeypatch):
    monkeypatch.setattr(trending.core, "fetch_json", lambda url: {
        "feed": {"entry": [{
            "im:name": {"label": "Show"},
            "im:artist": {"label": "Auth"},
            "im:image": [],
            "id": {"label": "https://x", "attributes": {"im:id": "99"}},
        }]}
    })
    rows = trending.fetch_apple_charts(country="us", limit=5)
    assert rows[0]["apple_id"] == "99"


def test_fetch_trending_dispatch(monkeypatch):
    monkeypatch.setattr(trending, "fetch_apple_charts",
                        lambda **k: [{"title": "US"}])
    monkeypatch.setattr(trending, "fetch_xyzrank_podcasts",
                        lambda **k: [{"title": "CN"}])
    assert trending.fetch_trending(source="apple")["shows"][0]["title"] == "US"
    assert trending.fetch_trending(source="xyzrank")["shows"][0]["title"] == "CN"
