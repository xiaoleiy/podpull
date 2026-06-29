"""podget command-line interface (argparse, stdlib only)."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from . import __version__
from . import core

DEFAULT_OUT = os.path.expanduser("~/Downloads/Podcasts")


def _err(msg: str) -> None:
    print(f"podget: {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_search(args) -> int:
    results = core.search_shows(args.term, limit=args.limit, country=args.country)
    if not results:
        _err("no shows found")
        return 1
    for r in results:
        print(f"{r.get('collectionId'):>12}  {str(r.get('trackCount') or '?'):>4} ep  "
              f"{(r.get('collectionName') or '')[:48]:48}  {r.get('artistName') or ''}")
    return 0


def cmd_info(args) -> int:
    show = core.resolve_show(args.src)
    latest = show.episodes[0] if show.episodes else None
    print(f"Title   : {show.title}")
    print(f"Author  : {show.author}")
    if show.apple_id:
        print(f"AppleID : {show.apple_id}")
    print(f"Feed    : {show.feed}")
    print(f"Episodes: {len(show.episodes)}")
    if latest:
        print(f"Latest  : {latest.date}  {latest.title}")
    return 0


def cmd_list(args) -> int:
    show = core.resolve_show(args.src)
    eps = show.episodes
    if args.match:
        eps = core.select(eps, match=args.match)
    elif not args.all:
        eps = eps[: args.limit]
    for i, e in enumerate(eps):
        print(f"{i:>3}  {e.date}  {e.title[:80]}")
    if not eps:
        _err("no episodes matched")
        return 1
    return 0


def _ytdlp_fallback(src: str, out_dir: str) -> int:
    if not shutil.which("yt-dlp"):
        _err("episode not in recent list and yt-dlp not installed for fallback")
        return 2
    os.makedirs(out_dir, exist_ok=True)
    tmpl = os.path.join(out_dir, "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s")
    return subprocess.run(["yt-dlp", "--no-playlist", "-o", tmpl, src]).returncode


def cmd_get(args) -> int:
    kind, s = core.classify(args.src)
    out = args.out

    if kind == "xyz_episode":
        url, title = core.xyz_episode_to_audio(s)
        ep = core.Episode(title=title, pub="", url=url, mime="audio/mp4")
        print(f"[get] {title}", file=sys.stderr)
        print(core.download_episode(ep, out))
        return 0

    if kind == "apple_episode":
        url, title, rel = core.apple_episode_to_audio(s)
        if not url:
            _err("episode beyond recent catalog; trying yt-dlp")
            return _ytdlp_fallback(s, out)
        ep = core.Episode(title=title or "episode",
                          pub=("" if not rel else f"{rel}"), url=url)
        # releaseDate is ISO; Episode.date handles only RFC822, so name by ISO date
        from datetime import datetime
        try:
            d = datetime.fromisoformat((rel or "").replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            d = "0000-00-00"
        dest = os.path.join(out, core.safe_filename(f"{d} - {ep.title}") + core.ext_for(url, ""))
        print(f"[get] {ep.title}", file=sys.stderr)
        print(core.download_url(url, dest))
        return 0

    # show / rss -> need a selector
    show = core.resolve_show(s)
    sel = core.select(show.episodes, match=args.match, latest=args.latest, index=args.index)
    if not sel:
        _err("no episode selected — pass --match RE / --latest N / --index 0,2 "
             "(use `podget list` to browse)")
        return 1
    print(f"[plan] {len(sel)} episode(s) from “{show.title}” -> {out}", file=sys.stderr)
    for e in sel:
        print(f"[get] {e.date}  {e.title}", file=sys.stderr)
        print(core.download_episode(e, out))
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="podget",
        description="Download specific podcast episode audio. Accepts an Apple "
                    "Podcasts show URL/id, a raw RSS feed URL, or an episode link "
                    "(Apple ?i= or xiaoyuzhou).")
    p.add_argument("--version", action="version", version=f"podget {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search for podcast shows")
    s.add_argument("term")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--country", default="US")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("info", help="show metadata for a podcast")
    s.add_argument("src", help="Apple show URL/id or RSS feed URL")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("list", help="list episodes")
    s.add_argument("src", help="Apple show URL/id or RSS feed URL")
    s.add_argument("--match", help="case-insensitive title regex")
    s.add_argument("--all", action="store_true", help="list all (not just recent)")
    s.add_argument("--limit", type=int, default=40)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("get", help="download episode audio")
    s.add_argument("src", help="show URL/id, RSS URL, or episode link")
    s.add_argument("--match", help="case-insensitive title regex")
    s.add_argument("--latest", type=int, help="newest N episodes")
    s.add_argument("--index", help="comma-separated 0-based indices (0=newest)")
    s.add_argument("--out", default=DEFAULT_OUT, help=f"output dir (default: {DEFAULT_OUT})")
    s.set_defaults(func=cmd_get)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError) as e:
        _err(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
