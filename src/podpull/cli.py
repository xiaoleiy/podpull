"""podpull command-line interface.

UI (colors, spinners, progress bars, interactive selection) lives here; all
network/parse logic lives in `core` and stays dependency-free. File paths are
printed to stdout (scriptable); everything else goes to stderr.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime

from rich.console import Console
from rich.progress import (BarColumn, DownloadColumn, Progress, SpinnerColumn,
                           TextColumn, TimeRemainingColumn, TransferSpeedColumn)
from rich.table import Table

from . import __version__, core

try:
    from rich_argparse import RawDescriptionRichHelpFormatter as _Formatter
except Exception:                      # pragma: no cover - fallback if absent
    _Formatter = argparse.RawDescriptionHelpFormatter

DEFAULT_OUT = os.path.expanduser("~/Downloads/Podcasts")
out_console = Console()                # stdout — machine-readable (file paths)
ui = Console(stderr=True)              # stderr — humans (spinners, tables, bars)


def _err(msg: str) -> None:
    ui.print(f"[bold red]podpull:[/] {msg}")


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def _resolve_show(kind: str, s: str, args) -> core.Show:
    """Resolve a show/feed with step-by-step spinner feedback."""
    quiet = getattr(args, "quiet", False)
    if quiet:
        # quiet mode: no spinner
        if kind == "apple_show":
            feed, name, author, pid = core.apple_show_to_feed(s)
        else:
            feed, name, author, pid = s, "", "", ""
        title, feed_author, eps = core.parse_feed(feed)
    else:
        with ui.status("[cyan]Resolving show via iTunes…", spinner="dots") as status:
            if kind == "apple_show":
                feed, name, author, pid = core.apple_show_to_feed(s)
            else:                          # rss
                feed, name, author, pid = s, "", "", ""
            status.update("[cyan]Fetching RSS feed & parsing episodes…")
            title, feed_author, eps = core.parse_feed(feed)
    return core.Show(title=name or title, feed=feed,
                     author=author or feed_author, apple_id=pid, episodes=eps)


def _download_all(episodes: list[core.Episode], out_dir: str, args) -> int:
    """Download episodes with a live per-file progress bar."""
    n = 0
    if args.quiet:
        # quiet mode: no progress bar
        for ep in episodes:
            try:
                path = core.download_episode(ep, out_dir)
            except Exception as e:
                _err(f"{ep.title[:50]}: {e}")
                continue
            print(path)
            n += 1
        return n
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[label]}", justify="left"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=ui,
            transient=True,
        ) as progress:
            for ep in episodes:
                task = progress.add_task("dl", label=ep.title[:34] or "episode", total=None)

                def cb(done: int, total: int, _t=task) -> None:
                    progress.update(_t, completed=done, total=(total or None))

                try:
                    path = core.download_episode(ep, out_dir, on_progress=cb)
                except Exception as e:      # keep going on a single failure
                    progress.console.print(f"[red]✗[/] {ep.title[:50]}: {e}")
                    continue
                progress.remove_task(task)
                size = os.path.getsize(path)
                ui.print(f"[green]✓[/] {ep.date}  {ep.title[:50]}  [dim]({size/1e6:.1f} MB)[/]")
                print(path)                 # stdout: the saved file path
                n += 1

    return n


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def _render_search_table(term: str, results: list) -> None:
    table = Table(title=f"Podcasts matching “{term}”", header_style="bold", expand=False)
    table.add_column("Apple ID", style="cyan", no_wrap=True)
    table.add_column("Eps", justify="right", style="magenta")
    table.add_column("Show")
    table.add_column("Author", style="dim")
    for r in results:
        table.add_row(str(r.get("collectionId") or "—"), str(r.get("trackCount") or "?"),
                      r.get("collectionName") or "", r.get("artistName") or "")
    ui.print(table)
    ui.print("[dim]Next:[/] podpull list <Apple ID>  •  podpull get <Apple ID>")


def _merge_results(primary: list, extra: list) -> list:
    seen = {(r.get("feedUrl") or "").strip().rstrip("/") for r in primary}
    seen.discard("")
    merged = list(primary)
    for r in extra:
        key = (r.get("feedUrl") or "").strip().rstrip("/")
        if key and key in seen:
            continue
        seen.add(key)
        merged.append(r)
    return merged


def cmd_search(args) -> int:
    results, warnings = [], []
    with ui.status(f"[cyan]Searching for “{args.term}”…"):
        if core.pi_credentials() is None:
            # no PI keys -> exactly the old behavior (errors propagate to main)
            results = core.search_shows(args.term, limit=args.limit, country=args.country)
        else:
            try:
                results = core.search_shows(args.term, limit=args.limit, country=args.country)
            except Exception as e:
                warnings.append(f"iTunes search failed: {e}")
            try:
                results = _merge_results(results, core.pi_search_shows(args.term, limit=args.limit))
            except Exception as e:
                warnings.append(f"Podcast Index search failed: {e}")
    for w in warnings:
        _err(w)
    if not results:
        _err("no shows found")
        return 1
    _render_search_table(args.term, results)
    return 0


def cmd_info(args) -> int:
    kind, s = core.classify(args.src)
    if kind not in ("apple_show", "rss"):
        _err("info needs a show URL/id or RSS feed (not an episode link)")
        return 1
    show = _resolve_show(kind, s, args)
    latest = show.episodes[0] if show.episodes else None
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("Title", show.title)
    table.add_row("Author", show.author or "[dim]—[/]")
    if show.apple_id:
        table.add_row("Apple ID", show.apple_id)
    table.add_row("Feed", show.feed)
    table.add_row("Episodes", str(len(show.episodes)))
    if latest:
        table.add_row("Latest", f"{latest.date}  {latest.title}")
    ui.print(table)
    return 0


def cmd_list(args) -> int:
    kind, s = core.classify(args.src)
    if kind not in ("apple_show", "rss"):
        _err("list needs a show URL/id or RSS feed (not an episode link)")
        return 1
    show = _resolve_show(kind, s, args)
    eps = core.select(show.episodes, match=args.match) if args.match else show.episodes
    if not args.all and not args.match:
        eps = eps[: args.limit]
    if not eps:
        _err("no episodes matched")
        return 1
    table = Table(title=f"{show.title} — {len(show.episodes)} episodes", header_style="bold")
    table.add_column("#", justify="right", style="magenta", no_wrap=True)
    table.add_column("Date", style="cyan", no_wrap=True)
    table.add_column("Title")
    for i, e in enumerate(eps):
        table.add_row(str(i), e.date, e.title)
    ui.print(table)
    ui.print("[dim]Download:[/] podpull get <src> --index N[,N]  •  --match RE  •  --latest N "
             "•  or just `podpull get <src>` to pick interactively")
    return 0


def _ytdlp_fallback(src: str, out_dir: str) -> int:
    if not shutil.which("yt-dlp"):
        _err("episode not in recent list and yt-dlp not installed for fallback")
        return 2
    os.makedirs(out_dir, exist_ok=True)
    tmpl = os.path.join(out_dir, "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s")
    return subprocess.run(["yt-dlp", "--no-playlist", "-o", tmpl, src]).returncode


def _interactive_select(show: core.Show) -> list[core.Episode]:
    import questionary
    if not show.episodes:
        return []
    choices = [questionary.Choice(title=f"{e.date}  {e.title}", value=i)
               for i, e in enumerate(show.episodes)]
    picked = questionary.checkbox(
        f"Select episodes from “{show.title}”   "
        "(↑/↓ move · space toggle · a all · enter confirm)",
        choices=choices,
    ).ask()                            # None on Ctrl-C/Esc
    return [show.episodes[i] for i in (picked or [])]


def cmd_get(args) -> int:
    kind, s = core.classify(args.src)
    out = args.out

    # --- pasted episode links: download immediately ----------------------- #
    if kind == "xyz_episode":
        if args.quiet:
            url, title = core.xyz_episode_to_audio(s)
        else:
            with ui.status("[cyan]Resolving xiaoyuzhou episode…"):
                url, title = core.xyz_episode_to_audio(s)
        return 0 if _download_all([core.Episode(title=title, pub="", url=url,
                                                mime="audio/mp4")], out, args) else 1

    if kind == "apple_episode":
        if args.quiet:
            url, title, rel = core.apple_episode_to_audio(s)
        else:
            with ui.status("[cyan]Resolving Apple episode…"):
                url, title, rel = core.apple_episode_to_audio(s)
        if not url:
            _err("episode beyond recent catalog; trying yt-dlp")
            return _ytdlp_fallback(s, out)
        try:
            pub = datetime.fromisoformat((rel or "").replace("Z", "+00:00")).strftime(
                "%a, %d %b %Y %H:%M:%S +0000")
        except Exception:
            pub = ""
        return 0 if _download_all([core.Episode(title=title or "episode", pub=pub,
                                                url=url)], out, args) else 1

    # --- show / rss: select then download --------------------------------- #
    show = _resolve_show(kind, s, args)
    sel = core.select(show.episodes, match=args.match, latest=args.latest, index=args.index)

    if not sel and not (args.match or args.latest or args.index):
        # no selector given -> interactive picker, or list+hint if not a TTY (quiet mode disables picker)
        if not args.quiet and _interactive() and not args.no_input:
            sel = _interactive_select(show)
            if not sel:
                _err("nothing selected")
                return 1
        else:
            cmd_list(argparse.Namespace(src=s, match=None, all=False, limit=20, quiet=args.quiet))
            _err("no selector and not an interactive terminal — pass "
                 "--match RE / --latest N / --index 0,2")
            return 1

    if not sel:
        _err("no episode matched your selection")
        return 1

    # Multiple episodes -> drop them into a folder named after the show.
    target = out
    if len(sel) > 1:
        target = os.path.join(out, core.safe_filename(show.title))
    if not args.quiet:
        ui.print(f"[bold]Downloading {len(sel)} episode(s)[/] from “{show.title}” → [dim]{target}[/]")
    return 0 if _download_all(sel, target, args) else 1


# --------------------------------------------------------------------------- #
# skills — install podpull integrations into AI coding agents
# --------------------------------------------------------------------------- #
def _skills_agents(args) -> "list[str] | None":
    from . import skills
    if getattr(args, "all", False):
        return list(skills.AGENTS)
    if getattr(args, "agent", None):
        chosen = [a.strip().lower() for a in args.agent.split(",") if a.strip()]
        bad = [a for a in chosen if a not in skills.AGENTS]
        if bad:
            raise ValueError(f"unknown agent(s): {', '.join(bad)} (pick from {', '.join(skills.AGENTS)})")
        return chosen
    return None  # -> detected only


def cmd_skills_install(args) -> int:
    from . import skills
    agents = _skills_agents(args)
    if agents is None and not skills.detect():
        _err("no supported agents detected (Claude Code, Codex, OpenCode, Cursor). "
             "Use --all to install for all, or --agent claude,codex,…")
        return 1
    results = skills.install(agents, project=getattr(args, "project", False))
    for r in results:
        if r.status == "installed":
            ui.print(f"[green]✓[/] {r.label}: [dim]{r.path}[/]" + (f"  ({r.note})" if r.note else ""))
        elif r.status == "manual":
            ui.print(f"[yellow]●[/] {r.label}: {r.note}\n    [dim]{r.path}[/]")
    ui.print("[dim]Re-run anytime (e.g. after an upgrade) to refresh.[/]")
    return 0


def cmd_skills_status(args) -> int:
    from . import skills
    table = Table(title="podpull agent integrations", header_style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Detected")
    table.add_column("Installed")
    table.add_column("Path", style="dim")
    for r in skills.status():
        detected = "yes" if r.note == "detected" else "—"
        installed = "[green]yes[/]" if r.status == "installed" else "no"
        table.add_row(r.label, detected, installed, r.path or "—")
    ui.print(table)
    ui.print("[dim]Install/refresh:[/] podpull skills install [--all]")
    return 0


def cmd_skills_uninstall(args) -> int:
    from . import skills
    agents = _skills_agents(args) or skills.AGENTS
    for r in (skills.uninstall_one(a, project=getattr(args, "project", False)) for a in agents):
        mark = "[green]✓ removed[/]" if r.note == "removed" else "[dim]— not installed[/]"
        ui.print(f"{mark}  {r.label}  [dim]{r.path}[/]")
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
EXAMPLES = """
[bold]Examples[/]
  [cyan]podpull search[/] "睡前故事"                 find shows (Apple ID, episode count)
  [cyan]podpull info[/]  1532755821                  show metadata + latest episode
  [cyan]podpull list[/]  1532755821 --match EP34     list episodes (filter by title regex)

  [cyan]podpull get[/]   1532755821                  ← pick episodes interactively (↑/↓, space, enter)
  [cyan]podpull get[/]   1532755821 --latest 3       newest 3 episodes
  [cyan]podpull get[/]   1532755821 --index 0,2,5    by list number (0 = newest)
  [cyan]podpull get[/]   1532755821 --match "牛頭人"  by title regex
  [cyan]podpull get[/]   "https://www.xiaoyuzhoufm.com/episode/<id>"   a pasted link

[dim]<src> = Apple show URL · bare Apple ID · RSS feed URL · Apple ?i= episode URL · xiaoyuzhou link[/]
[dim]Downloads default to ~/Downloads/Podcasts (override with --out).[/]

[dim]Optional: set PODCASTINDEX_API_KEY + PODCASTINDEX_API_SECRET (free — podcastindex.org)[/]
[dim]to enrich search results and add a feed-resolution fallback.[/]
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="podpull", formatter_class=_Formatter,
        description="Download specific podcast episode audio from Apple Podcasts, "
                    "RSS feeds, or xiaoyuzhou links.",
        epilog=EXAMPLES)
    p.add_argument("--version", action="version", version=f"podpull {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    s = sub.add_parser("search", help="search for podcast shows", formatter_class=_Formatter,
                       description="Search the iTunes catalog for shows by name/keyword.")
    s.add_argument("term", help="search keywords, e.g. \"睡前故事\"")
    s.add_argument("--limit", type=int, default=10, metavar="N", help="max results (default 10)")
    s.add_argument("--country", default="US", metavar="CC", help="iTunes storefront (default US)")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("info", help="show metadata for a podcast", formatter_class=_Formatter,
                       description="Print a show's title, author, feed, episode count, and latest episode.")
    s.add_argument("src", help="Apple show URL/id or RSS feed URL")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("list", help="list a show's episodes", formatter_class=_Formatter,
                       description="List episodes (newest first). # is the index used by `get --index`.")
    s.add_argument("src", help="Apple show URL/id or RSS feed URL")
    s.add_argument("--match", metavar="RE", help="case-insensitive title regex filter")
    s.add_argument("--all", action="store_true", help="show every episode (not just recent)")
    s.add_argument("--limit", type=int, default=40, metavar="N", help="how many recent to show (default 40)")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("get", aliases=["pull"], help="download episode audio (alias: pull)",
                       formatter_class=_Formatter,
                       description="Download one or more episodes. With a show/feed and no selector, "
                                   "opens an interactive multi-select picker. `podpull pull` is an alias.",
                       epilog=EXAMPLES)
    s.add_argument("-q", "--quiet", action="store_true", help="quiet mode; suppresses spinner and progress bar")
    s.add_argument("src", help="show URL/id, RSS URL, or a single-episode link")
    g = s.add_argument_group("episode selection (omit all → interactive picker)")
    g.add_argument("--match", metavar="RE", help="case-insensitive title regex")
    g.add_argument("--latest", type=int, metavar="N", help="newest N episodes")
    g.add_argument("--index", metavar="N[,N]", help="0-based list indices (0 = newest)")
    s.add_argument("--out", default=DEFAULT_OUT, metavar="DIR",
                   help=f"output directory (default: {DEFAULT_OUT})")
    s.add_argument("--no-input", action="store_true",
                   help="never prompt; fail instead of opening the interactive picker")
    s.set_defaults(func=cmd_get)

    sk = sub.add_parser("skills", formatter_class=_Formatter,
                        help="set up podpull integrations for AI agents",
                        description="Install podpull instructions into your AI coding agents so they "
                                    "know how to use it: Claude Code & Codex (skills), OpenCode (a "
                                    "/podpull command), and Cursor (a project rule).")
    sk.set_defaults(func=cmd_skills_status)         # bare `podpull skills` -> status
    sksub = sk.add_subparsers(dest="skills_cmd", metavar="<action>")

    ski = sksub.add_parser("install", formatter_class=_Formatter,
                           help="install/refresh integrations (detected agents by default)")
    ski.add_argument("--all", action="store_true", help="install for all supported agents, not just detected")
    ski.add_argument("--agent", metavar="LIST", help="comma list: claude,codex,opencode,cursor")
    ski.add_argument("--project", action="store_true", help="for Cursor, write a rule into ./.cursor/rules")
    ski.set_defaults(func=cmd_skills_install)

    sksub.add_parser("status", formatter_class=_Formatter,
                     help="show what's detected and installed").set_defaults(func=cmd_skills_status)

    sku = sksub.add_parser("uninstall", formatter_class=_Formatter, help="remove installed integrations")
    sku.add_argument("--all", action="store_true")
    sku.add_argument("--agent", metavar="LIST", help="comma list: claude,codex,opencode,cursor")
    sku.add_argument("--project", action="store_true", help="also remove the Cursor project rule in ./.cursor/rules")
    sku.set_defaults(func=cmd_skills_uninstall)
    return p


def main(argv: list[str] | None = None) -> int:
    # Ensure Unicode (CJK titles/paths) never crash on a legacy Windows console
    # or when stdout is redirected to a non-UTF-8 pipe.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):     # bare `podpull` -> show usage, not an error
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError) as e:
        _err(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
