"""Core logic: resolve a source -> feed/episodes, search, select, download.

No third-party dependencies — only the Python standard library.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

UA = "Mozilla/5.0 (compatible; podget/0.1; +https://github.com/xiaoliy/podget)"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"
ITUNES_SEARCH = "https://itunes.apple.com/search"


# --------------------------------------------------------------------------- #
# data model
# --------------------------------------------------------------------------- #
@dataclass
class Episode:
    title: str
    pub: str            # raw RFC-822 pubDate string from the feed
    url: str            # direct enclosure audio URL
    mime: str = ""
    guid: str = ""
    link: str = ""

    @property
    def date(self) -> str:
        try:
            return parsedate_to_datetime(self.pub).strftime("%Y-%m-%d")
        except Exception:
            return "0000-00-00"


@dataclass
class Show:
    title: str
    feed: str
    author: str = ""
    apple_id: str = ""
    episodes: list[Episode] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# http helpers
# --------------------------------------------------------------------------- #
def fetch(url: str, timeout: int = 45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_json(url: str):
    return json.load(fetch(url))


# --------------------------------------------------------------------------- #
# input classification
# --------------------------------------------------------------------------- #
def classify(src: str) -> tuple[str, str]:
    """Return (kind, normalized_src). kind ∈ {apple_show, apple_episode,
    xyz_episode, rss}."""
    s = src.strip()
    if re.fullmatch(r"\d+", s):
        return "apple_show", s
    if "xiaoyuzhoufm.com/episode/" in s:
        return "xyz_episode", s
    if "podcasts.apple.com" in s and re.search(r"[?&]i=\d+", s):
        return "apple_episode", s
    if "podcasts.apple.com" in s:
        return "apple_show", s
    if s.startswith("http"):
        return "rss", s
    raise ValueError(f"Cannot classify input: {src!r}")


# --------------------------------------------------------------------------- #
# search / resolve
# --------------------------------------------------------------------------- #
def search_shows(term: str, limit: int = 10, country: str = "US") -> list[dict]:
    q = urllib.parse.urlencode(
        {"term": term, "media": "podcast", "entity": "podcast",
         "limit": limit, "country": country}
    )
    return fetch_json(f"{ITUNES_SEARCH}?{q}").get("results", [])


def apple_show_to_feed(src: str) -> tuple[str, str, str, str]:
    """-> (feedUrl, name, author, apple_id)."""
    m = re.search(r"/id(\d+)", src) or re.fullmatch(r"(\d+)", src)
    if not m:
        raise ValueError(f"No Apple podcast id (idNNN) found in: {src}")
    pid = m.group(1)
    results = fetch_json(f"{ITUNES_LOOKUP}?id={pid}").get("results", [])
    if not results:
        raise ValueError(f"iTunes lookup returned nothing for id={pid}")
    r = results[0]
    feed = r.get("feedUrl")
    if not feed:
        raise ValueError(f"No feedUrl for id={pid} (not a podcast?)")
    return feed, r.get("collectionName", ""), r.get("artistName", ""), pid


def parse_feed(feed_url: str) -> tuple[str, str, list[Episode]]:
    """-> (show_title, show_author, episodes)."""
    root = ET.fromstring(fetch(feed_url).read())
    chan = root.find(".//channel")
    title = (chan.findtext("title") if chan is not None else "") or ""
    itunes = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
    author = ""
    if chan is not None:
        author = (chan.findtext(f"{itunes}author") or "").strip()
    eps: list[Episode] = []
    for it in root.findall(".//item"):
        enc = it.find("enclosure")
        if enc is None:
            continue
        enc_url = enc.get("url")
        if not enc_url:
            continue
        eps.append(Episode(
            title=(it.findtext("title") or "").strip(),
            pub=(it.findtext("pubDate") or "").strip(),
            url=enc_url,
            mime=enc.get("type") or "",
            guid=(it.findtext("guid") or "").strip(),
            link=(it.findtext("link") or "").strip(),
        ))
    return title.strip(), author, eps


def resolve_show(src: str) -> Show:
    kind, s = classify(src)
    if kind == "apple_show":
        feed, name, author, pid = apple_show_to_feed(s)
    elif kind == "rss":
        feed, name, author, pid = s, "", "", ""
    else:
        raise ValueError(f"{src!r} is an episode link, not a show; use get() directly")
    title, feed_author, eps = parse_feed(feed)
    return Show(title=name or title, feed=feed, author=author or feed_author,
                apple_id=pid, episodes=eps)


# --------------------------------------------------------------------------- #
# direct-episode resolvers (pasted links)
# --------------------------------------------------------------------------- #
def xyz_episode_to_audio(src: str) -> tuple[str, str]:
    html = fetch(src).read().decode("utf-8", "replace")
    m = re.search(r'<meta\s+property="og:audio"\s+content="([^"]+)"', html) \
        or re.search(r"(https://media\.xyzcdn\.net/[^\"'\s]+\.m4a)", html)
    if not m:
        raise ValueError("Could not find og:audio on xiaoyuzhou page")
    t = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    return m.group(1), (t.group(1).strip() if t else "episode")


def apple_episode_to_audio(src: str) -> tuple[str | None, str | None, str | None]:
    """Resolve .../id<show>?i=<trackId> via the show's episode list.
    Returns (url, title, releaseDate) or (None, None, None) to signal a
    deep-catalog miss (caller may fall back to yt-dlp)."""
    show_m = re.search(r"/id(\d+)", src)
    track_m = re.search(r"[?&]i=(\d+)", src)
    if show_m and track_m:
        q = urllib.parse.urlencode(
            {"id": show_m.group(1), "entity": "podcastEpisode", "limit": 200})
        for r in fetch_json(f"{ITUNES_LOOKUP}?{q}").get("results", []):
            if str(r.get("trackId")) == track_m.group(1) and r.get("episodeUrl"):
                return r["episodeUrl"], (r.get("trackName") or "").strip(), r.get("releaseDate")
    return None, None, None


# --------------------------------------------------------------------------- #
# selection
# --------------------------------------------------------------------------- #
def select(episodes: list[Episode], *, match: str | None = None,
           latest: int | None = None, index: str | None = None) -> list[Episode]:
    if match:
        rx = re.compile(match, re.I)
        return [e for e in episodes if rx.search(e.title)]
    if latest:
        return episodes[:latest]
    if index is not None:
        idxs = [int(x) for x in str(index).split(",") if x.strip() != ""]
        return [episodes[i] for i in idxs if -len(episodes) <= i < len(episodes)]
    return []


# --------------------------------------------------------------------------- #
# download
# --------------------------------------------------------------------------- #
def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", name)
    return re.sub(r"\s+", " ", name).strip()[:140]


def ext_for(url: str, mime: str) -> str:
    if "mp4" in mime or url.lower().split("?")[0].endswith((".m4a", ".mp4", ".aac")):
        return ".m4a"
    return ".mp3"


def download_url(url: str, dest: str, *, resume: bool = True, progress=sys.stderr) -> str:
    """Stream a URL to dest with Range-based resume. Stdlib only."""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    headers = {"User-Agent": UA}
    existing = os.path.getsize(dest) if (resume and os.path.exists(dest)) else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416:           # range not satisfiable -> already complete
            return dest
        raise
    if existing and getattr(resp, "status", 200) == 200:
        existing = 0                # server ignored Range; restart cleanly
    mode = "ab" if existing else "wb"
    remaining = resp.length or 0
    total = (remaining + existing) if remaining else 0
    done = existing
    with open(dest, mode) as f:
        while True:
            buf = resp.read(1 << 16)
            if not buf:
                break
            f.write(buf)
            done += len(buf)
            if progress and total:
                pct = done * 100 // total
                progress.write(f"\r  {pct:3d}%  {done/1e6:7.1f} / {total/1e6:.1f} MB")
                progress.flush()
    if progress and total:
        progress.write("\n")
    return dest


def download_episode(ep: Episode, out_dir: str, **kw) -> str:
    stem = safe_filename(f"{ep.date} - {ep.title}")
    dest = os.path.join(out_dir, stem + ext_for(ep.url, ep.mime))
    return download_url(ep.url, dest, **kw)
