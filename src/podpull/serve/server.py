"""Stdlib HTTP server for `podpull serve` — metadata API + static UI.

Does not proxy audio. Clients download enclosure URLs in the browser.
"""
from __future__ import annotations

import json
import mimetypes
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from podpull import __version__, core
from podpull.serve import trending

STATIC_DIR = Path(__file__).resolve().parent / "static"
_TRENDING_TTL = 30 * 60  # seconds
_trending_cache: dict[str, tuple[float, dict]] = {}


def _json_bytes(obj: Any, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def _show_src(show_hint: dict) -> str:
    """Pick a core.classify-able source from a trending / search card."""
    if show_hint.get("feed"):
        return show_hint["feed"]
    if show_hint.get("apple_id"):
        return str(show_hint["apple_id"])
    if show_hint.get("page_url"):
        return show_hint["page_url"]
    raise ValueError("show has no feed, apple_id, or page_url")


def _episode_dict(ep: core.Episode, index: int) -> dict:
    return {
        "index": index,
        "date": ep.date,
        "title": ep.title,
        "url": ep.url,
        "link": ep.link or "",
    }


def _show_meta(show: core.Show) -> dict:
    return {
        "title": show.title,
        "author": show.author or "",
        "apple_id": show.apple_id or "",
        "feed": show.feed,
    }


def _resolve_show_from_src(src: str) -> core.Show:
    kind, s = core.classify(src)
    if kind == "apple_show":
        feed, name, author, pid = core.apple_show_to_feed(s)
        title, feed_author, eps = core.parse_feed(feed)
        return core.Show(title=name or title, feed=feed,
                         author=author or feed_author, apple_id=pid, episodes=eps)
    if kind == "rss":
        title, author, eps = core.parse_feed(s)
        return core.Show(title=title, feed=s, author=author, episodes=eps)
    raise ValueError("need a show URL/id or RSS feed (not an episode link); "
                     "use /api/resolve for episode URLs")


def _resolve_episode(src: str) -> dict:
    kind, s = core.classify(src)
    if kind == "xyz_episode":
        url, title = core.xyz_episode_to_audio(s)
        return {"title": title, "url": url, "link": s, "date": "0000-00-00"}
    if kind == "apple_episode":
        url, title, rel = core.apple_episode_to_audio(s)
        if not url:
            raise ValueError("could not resolve Apple episode audio URL")
        date = "0000-00-00"
        try:
            from datetime import datetime
            date = datetime.fromisoformat((rel or "").replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            pass
        return {"title": title or "episode", "url": url, "link": s, "date": date}
    raise ValueError("resolve expects an Apple ?i= or xiaoyuzhou episode link")


def get_trending_cached(*, source: str, limit: int, offset: int, country: str) -> dict:
    key = f"{source}|{limit}|{offset}|{country}"
    now = time.time()
    hit = _trending_cache.get(key)
    if hit and now - hit[0] < _TRENDING_TTL:
        return hit[1]
    payload = trending.fetch_trending(
        source=source, limit=limit, offset=offset, country=country)
    _trending_cache[key] = (now, payload)
    return payload


def handle_api(method: str, path: str, query: dict[str, list[str]],
               body: bytes) -> tuple[int, bytes, str]:
    """Pure request → response helper (easy to unit-test)."""
    def q(name: str, default: str = "") -> str:
        vals = query.get(name) or []
        return vals[0] if vals else default

    try:
        if method == "GET" and path == "/api/health":
            return _json_bytes({"ok": True, "version": __version__})

        if method == "GET" and path == "/api/trending":
            source = q("source", "xyzrank")
            limit = int(q("limit", "40") or 40)
            offset = int(q("offset", "0") or 0)
            country = q("country", "US")
            try:
                payload = get_trending_cached(
                    source=source, limit=limit, offset=offset, country=country)
                return _json_bytes(payload)
            except Exception as e:
                # soft-fail empty list with error note
                return _json_bytes({
                    "source": source, "shows": [], "warning": str(e),
                })

        if method == "GET" and path == "/api/search":
            term = q("q") or q("term")
            if not term:
                return _json_bytes({"error": "missing q"}, 400)
            limit = int(q("limit", "10") or 10)
            country = q("country", "US")
            results = core.search_shows(term, limit=limit, country=country)
            rows = []
            for r in results:
                tc = r.get("trackCount")
                try:
                    ep_count = int(tc) if tc is not None and tc != "" else None
                except (TypeError, ValueError):
                    ep_count = None
                cid = r.get("collectionId")
                rows.append({
                    "apple_id": str(cid) if cid is not None and cid != "" else "",
                    "title": r.get("collectionName") or "",
                    "author": r.get("artistName") or "",
                    "episode_count": ep_count,
                    "feed_url": r.get("feedUrl") or "",
                })
            return _json_bytes({"query": term, "results": rows})

        if method == "GET" and path == "/api/info":
            src = q("src")
            if not src:
                return _json_bytes({"error": "missing src"}, 400)
            show = _resolve_show_from_src(src)
            latest = show.episodes[0] if show.episodes else None
            return _json_bytes({
                **_show_meta(show),
                "episode_count": len(show.episodes),
                "latest": (_episode_dict(latest, 0) if latest else None),
            })

        if method == "GET" and path == "/api/list":
            src = q("src")
            if not src:
                return _json_bytes({"error": "missing src"}, 400)
            show = _resolve_show_from_src(src)
            match = q("match") or None
            all_eps = q("all", "").lower() in ("1", "true", "yes")
            limit = int(q("limit", "40") or 40)
            eps = core.select(show.episodes, match=match) if match else list(show.episodes)
            if not all_eps and not match:
                eps = eps[:limit]
            return _json_bytes({
                "show": _show_meta(show),
                "episodes": [_episode_dict(e, i) for i, e in enumerate(eps)],
            })

        if method == "POST" and path == "/api/resolve":
            data = json.loads(body.decode("utf-8") or "{}")
            src = (data.get("src") or "").strip()
            if not src:
                return _json_bytes({"error": "missing src"}, 400)
            return _json_bytes(_resolve_episode(src))

        return _json_bytes({"error": "not found"}, 404)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        return _json_bytes({"error": str(e)}, 400)
    except Exception as e:  # pragma: no cover
        return _json_bytes({"error": str(e)}, 500)


class ServeHandler(BaseHTTPRequestHandler):
    server_version = f"podpull/{__version__}"

    def log_message(self, fmt: str, *args) -> None:  # quieter default
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path or "/"
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/"):
            status, body, ctype = handle_api("GET", path, query, b"")
            self._send(status, body, ctype)
            return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path or "/"
        query = urllib.parse.parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if not path.startswith("/api/"):
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        status, body_out, ctype = handle_api("POST", path, query, body)
        self._send(status, body_out, ctype)

    def _serve_static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            rel = "index.html"
        else:
            rel = path.lstrip("/")
        # path traversal guard
        target = (STATIC_DIR / rel).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        data = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype = f"{ctype}; charset=utf-8"
        self._send(200, data, ctype)


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ServeHandler)


def serve_forever(host: str, port: int, *, on_start: Callable[[str], None] | None = None) -> None:
    httpd = make_server(host, port)
    url = f"http://{host}:{port}/"
    if on_start:
        on_start(url)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
