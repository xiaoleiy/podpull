"""Offline tests for the Vercel metadata gateway (BaseHTTPRequestHandler)."""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import HTTPServer
from threading import Thread

from api.index import _normalize_api_path, handler
from podpull import core
from podpull.serve import server as serve_api


def test_normalize_api_path():
    assert _normalize_api_path("/") == "/api/health"
    assert _normalize_api_path("/health") == "/api/health"
    assert _normalize_api_path("/api/search") == "/api/search"
    assert _normalize_api_path("search") == "/api/search"


def test_handler_health():
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/health")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        assert resp.status == 200
        assert body["ok"] is True
        assert "version" in body
        conn.close()
    finally:
        httpd.shutdown()


def test_handler_trending_cache_control(monkeypatch):
    monkeypatch.setattr(
        serve_api,
        "get_trending_cached",
        lambda **k: {"source": "apple", "shows": [{"title": "X", "apple_id": "1"}]},
    )
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/trending?source=apple")
        resp = conn.getresponse()
        raw = resp.read()
        assert resp.status == 200
        assert "s-maxage=1800" in (resp.getheader("Cache-Control") or "")
        assert json.loads(raw)["shows"][0]["title"] == "X"
        conn.close()
    finally:
        httpd.shutdown()


def test_handler_search(monkeypatch):
    monkeypatch.setattr(
        core,
        "search_shows",
        lambda term, limit, country: [{
            "collectionId": 9,
            "collectionName": "S",
            "artistName": "a",
            "feedUrl": "https://f",
            "trackCount": 3,
            "artworkUrl600": "https://img/a.jpg",
        }],
    )
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/search?q=hello")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        assert resp.status == 200
        assert data["results"][0]["apple_id"] == "9"
        conn.close()
    finally:
        httpd.shutdown()
