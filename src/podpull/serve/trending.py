"""Trending / chart helpers for `podpull serve` (stdlib only).

Fetches Chinese rankings from xyzrank.com and international Top Podcasts
from Apple's public RSS-JSON feeds. Returns normalized show dicts for the UI.
"""
from __future__ import annotations

import re
import urllib.parse

from podpull import core

XYZRANK_PODCASTS = "https://xyzrank.com/api/podcasts"
APPLE_TOP = "https://itunes.apple.com/{country}/rss/toppodcasts/limit={limit}/json"


def _apple_id_from_url(url: str) -> str:
    m = re.search(r"/id(\d+)", url or "")
    return m.group(1) if m else ""


def _link_map(links: list | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in links or []:
        name = (item.get("name") or "").strip().lower()
        url = (item.get("url") or "").strip()
        if name and url:
            out[name] = url
    return out


def normalize_xyzrank_item(item: dict) -> dict:
    links = _link_map(item.get("links"))
    apple_url = links.get("apple", "")
    return {
        "rank": int(item.get("rank") or 0),
        "title": item.get("name") or "",
        "author": item.get("authorsText") or "",
        "apple_id": _apple_id_from_url(apple_url),
        "feed": links.get("rss", ""),
        "artwork": item.get("logoURL") or "",
        "page_url": apple_url or links.get("xyz") or links.get("website") or "",
        "source": "xyzrank",
    }


def normalize_apple_entry(entry: dict, rank: int) -> dict:
    attrs = (entry.get("id") or {}).get("attributes") or {}
    images = entry.get("im:image") or []
    artwork = ""
    if isinstance(images, list) and images:
        last = images[-1]
        artwork = last.get("label") if isinstance(last, dict) else ""
    return {
        "rank": rank,
        "title": ((entry.get("im:name") or {}).get("label") or ""),
        "author": ((entry.get("im:artist") or {}).get("label") or ""),
        "apple_id": str(attrs.get("im:id") or ""),
        "feed": "",
        "artwork": artwork,
        "page_url": ((entry.get("id") or {}).get("label") or ""),
        "source": "apple",
    }


def fetch_xyzrank_podcasts(*, limit: int = 40, offset: int = 0) -> list[dict]:
    """Hot Chinese podcasts from xyzrank (热门播客)."""
    q = urllib.parse.urlencode({"limit": max(1, limit), "offset": max(0, offset)})
    data = core.fetch_json(f"{XYZRANK_PODCASTS}?{q}")
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [normalize_xyzrank_item(it) for it in items if isinstance(it, dict)]


def fetch_apple_charts(*, country: str = "US", limit: int = 40) -> list[dict]:
    """Apple Podcasts Top Podcasts chart (RSS JSON)."""
    cc = (country or "US").lower()
    lim = max(1, min(int(limit), 200))
    url = APPLE_TOP.format(country=cc, limit=lim)
    data = core.fetch_json(url)
    entries = ((data.get("feed") or {}).get("entry")) if isinstance(data, dict) else None
    if entries is None:
        return []
    if isinstance(entries, dict):
        entries = [entries]
    out = []
    for i, entry in enumerate(entries or []):
        if isinstance(entry, dict):
            out.append(normalize_apple_entry(entry, i + 1))
    return out


def fetch_trending(*, source: str = "xyzrank", limit: int = 40,
                   offset: int = 0, country: str = "US") -> dict:
    """Unified trending payload for `/api/trending`."""
    src = (source or "xyzrank").lower()
    if src == "apple":
        shows = fetch_apple_charts(country=country, limit=limit)
        return {"source": "apple", "country": country.upper(), "shows": shows}
    shows = fetch_xyzrank_podcasts(limit=limit, offset=offset)
    return {"source": "xyzrank", "shows": shows}
