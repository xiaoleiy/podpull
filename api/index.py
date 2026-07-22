"""Vercel Python entrypoint — metadata API for the hosted podpull site.

Uses Vercel's BaseHTTPRequestHandler style (no FastAPI) and reuses
podpull.serve.server.handle_api so CLI `podpull serve` and
https://podpull.xiaolei.work share one contract. Does not proxy audio.
"""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Import stdlib-only podpull package from src/ (rich UI deps not required).
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from podpull.serve import server as serve_api  # noqa: E402

_TRENDING_CACHE_CONTROL = "public, s-maxage=1800, stale-while-revalidate=3600"


def _normalize_api_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if path in ("/", ""):
        return "/api/health"
    if path.startswith("/api/"):
        return path
    return "/api" + path


class handler(BaseHTTPRequestHandler):  # noqa: N801 — Vercel entrypoint name
    def log_message(self, fmt: str, *args) -> None:
        pass

    def _send(self, status: int, body: bytes, content_type: str,
              cache_control: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch(b"")

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self._dispatch(body)

    def _dispatch(self, body: bytes) -> None:
        parsed = urlparse(self.path)
        path = _normalize_api_path(parsed.path or "/")
        query = parse_qs(parsed.query, keep_blank_values=True)
        status, payload, ctype = serve_api.handle_api(
            self.command, path, query, body)
        cache = (
            _TRENDING_CACHE_CONTROL
            if path == "/api/trending" and status == 200
            else "no-store"
        )
        self._send(status, payload, ctype, cache_control=cache)
