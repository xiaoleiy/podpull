<p align="center"><img src="docs/icon.png" alt="podpull" width="132"></p>
<h1 align="center">podpull</h1>

<p align="center">
<a href="https://pypi.org/project/podpull/"><img src="https://img.shields.io/pypi/v/podpull.svg" alt="PyPI"></a>
<a href="https://github.com/xiaoleiy/podpull/actions/workflows/ci.yml"><img src="https://github.com/xiaoleiy/podpull/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-informational.svg" alt="License: MIT"></a>
<img src="https://img.shields.io/badge/platforms-macOS%20·%20Linux%20·%20Windows-lightgrey.svg" alt="Platforms">
</p>

<p align="center"><b>Find episodes from any show. Download straight to disk — Apple Podcasts, RSS, or 小宇宙/xiaoyuzhou.</b></p>

Use the **CLI** (interactive multi-select picker, spinners, progress bars) or the
**browser UI**. No app, no login, no DRM. Filenames are cloud-safe; multiple CLI
picks land in a per-show folder under `~/Downloads/Podcasts`.

**▶ Official site:** https://podpull.xiaolei.work — landing `/` · app [`/app`](https://podpull.xiaolei.work/app)  
**▶ GitHub Pages mirror:** https://xiaoleiy.github.io/podpull

## Demo

<p align="center">
  <img src="docs/demo.gif" alt="podpull: search a show, pick episodes, download with a progress bar" width="820">
</p>

<details><summary>text version</summary>

```text
$ podpull get 1532755821
✓ 我們家的睡前故事 — 394 episodes
? Select episodes  (↑/↓ · space · enter)
❯ ◉ 2026-06-23  EP343 迷宮中的牛頭人
  ◯ 2026-06-16  EP342 午睡任務
  ◉ 2026-06-09  EP341 修煉龍 4
██████████████████  100%  21.2 MB  •  saved to ~/Downloads/Podcasts/我們家的睡前故事/
```
</details>

## How it works

Apple Podcasts hosts **no audio** — it is a directory that points at each show's
RSS feed, and every episode in that feed carries a direct `<enclosure>` audio URL.
podpull walks that chain:

```
Apple show URL/id ──(iTunes Lookup API)──▶ RSS feedUrl
RSS feed          ──(<enclosure url>)────▶ direct .mp3 / .m4a
download          ──(resumable)──────────▶ <YYYY-MM-DD> - <title>.<ext>
```

It also resolves a pasted **xiaoyuzhou** episode page (via its `og:audio` tag), a
pasted **Apple episode** link (`…?i=<id>`, matched in the feed), and a **Ximalaya**
album URL (`ximalaya.com/album/<id>` → that album's RSS).

## Install

```bash
# pipx (recommended) or pip — from PyPI
pipx install podpull
pip   install podpull

# or Homebrew (macOS / Linux)
brew install xiaoleiy/tap/podpull
```

Requires Python 3.9+. Optional: `yt-dlp` (deep-catalog Apple-episode fallback when
the track isn't in the recent feed window). Also on [PyPI](https://pypi.org/project/podpull/).

### Windows

Homebrew is macOS/Linux only — on Windows, install with pip/pipx (PowerShell or Windows Terminal):

```powershell
# 1) Python 3.9+ (skip if you have it):
winget install Python.Python.3.12

# 2) Recommended — isolated install via pipx:
py -m pip install --user pipx
py -m pipx ensurepath          # then reopen the terminal
pipx install podpull

# …or plain pip:
py -m pip install podpull
```

Then run `podpull` in Windows Terminal or PowerShell. The interactive picker, colors, and progress
bars work there; filenames are sanitized for Windows too (reserved names, illegal characters). If
`podpull` isn't found after install, reopen the terminal (so `PATH` refreshes) or use `py -m podpull`.

### Set up your AI coding agents (optional)

Teach your AI agents to use podpull so you can just ask them to grab an episode:

```bash
podpull skills install        # detected agents
podpull skills install --all  # all supported agents
podpull skills status         # see what's detected / installed
podpull skills uninstall      # remove what was installed
```

This writes podpull's instructions in each agent's native format:

| Agent | Installed as | Location |
|---|---|---|
| Claude Code | skill | `~/.claude/skills/podpull/SKILL.md` |
| Codex | skill | `~/.codex/skills/podpull/SKILL.md` |
| OpenCode | `/podpull` command | `~/.config/opencode/commands/podpull.md` |
| Cursor | project rule | `<project>/.cursor/rules/podpull.mdc` |

Re-run after `brew upgrade` to refresh. Nothing is written until you run it.
(Cursor has no file-based *global* rule — run it inside a project for a project rule,
or paste the printed rule into Cursor Settings → Rules.)

## Usage

```bash
podpull search "睡前故事"                 # find shows -> id, #episodes, name, author
podpull search "NPR" --country US --limit 5
podpull info  1532755821                  # show metadata (accepts URL, id, or RSS)
podpull list  1532755821                  # recent episodes, numbered (0 = newest)
podpull list  1532755821 --match "EP34"   # filter by title regex
podpull list  1532755821 --all            # every episode in the feed
```

### Download

```bash
# Interactive picker — just give a show; pick one or many episodes with the keyboard:
podpull get 1532755821
#   ↑/↓ move · space toggle · a select-all · enter confirm
#   (podpull pull … is an alias for get)

# Or select non-interactively (also used when piping / scripting):
podpull get 1532755821 --latest 1               # newest episode
podpull get 1532755821 --match "牛頭人"          # by title regex
podpull get 1532755821 --index 0,2,5            # by list number (0 = newest)
podpull get 1532755821 --latest 3 --out ~/Audio/bedtime
podpull get 1532755821 --latest 1 -q            # quiet: paths on stdout only

# Pasted single-episode / album links:
podpull get "https://www.xiaoyuzhoufm.com/episode/<id>"
podpull get "https://podcasts.apple.com/.../id<show>?i=<track>"
podpull get "https://www.ximalaya.com/album/<id>"
```

Downloads default to `~/Downloads/Podcasts` (override with `--out`). The saved file
path is printed to **stdout** (so you can pipe/capture it); progress and messages go
to **stderr**. Use `--no-input` to never open the picker (fail instead) for scripts.

### JSON (scripting)

```bash
podpull --json search "睡前故事"
podpull --json list 1532755821 --limit 5 | jq '.episodes[0].title'
podpull --json get 1532755821 --latest 1 --no-input | jq -r '.downloads[].path'
```

`--json` goes **before** the command. On success, stdout is one JSON document (no
tables/progress); on failure, a human message on stderr and a non-zero exit.

**Filenames** are normalized for cloud storage — emoji and other symbols are dropped,
full-width/illegal characters folded or stripped — so files upload cleanly to Google
Drive, OneDrive, Dropbox, iCloud, etc. (CJK and ordinary text are kept). When you grab
**multiple** episodes at once, they're placed in a sub-folder named after the show.

`<src>` accepts: an Apple show URL, a bare Apple ID, a raw RSS feed URL, an Apple
episode URL (`?i=`), a xiaoyuzhou episode URL, or a Ximalaya album URL
(`ximalaya.com/album/<id>`).

### Podcast Index (optional)

podpull can enrich `search` and feed resolution with the open
[Podcast Index](https://podcastindex.org) directory. Get a free API key at
[api.podcastindex.org](https://api.podcastindex.org/signup) and set:

```bash
export PODCASTINDEX_API_KEY=...
export PODCASTINDEX_API_SECRET=...
```

Without these, podpull behaves exactly as before (iTunes only).

### Web UI

**Hosted** at [podpull.xiaolei.work](https://podpull.xiaolei.work):

| Path | What |
|------|------|
| `/` | Marketing landing (live Apple Top Podcasts strip) |
| [`/app`](https://podpull.xiaolei.work/app) | Search, trending, per-episode browser download |
| `/api/*` | Metadata only — **no audio proxy** |

In the app: search shows, browse trending (**中文** via [xyzrank](https://xyzrank.com/) ·
**International** via Apple Top Podcasts), EN / 中文 UI, then **Download** or **Open page**
per episode (browsers block bulk multi-file downloads). Audio always comes from the
publisher CDN in your browser. Hosting notes: [`docs/HOSTING.md`](docs/HOSTING.md).

**Local twin** (same UI/API contract):

```bash
podpull serve                 # http://127.0.0.1:8787 (opens browser)
podpull serve --port 9000
podpull serve --host 0.0.0.0  # LAN (prints a warning)
podpull serve --no-open       # don't open a browser
```

For guaranteed saves into `~/Downloads/Podcasts` with cloud-safe names, keep using
`podpull get`.

## Roadmap

- **v0.1**: search · info · list · download (stdlib only).
- **v0.2**: interactive multi-select picker, rich progress bars + spinners,
  colored help, scriptable stdout. Adds `rich` + `questionary`.
- **v0.3**: renamed `podget` → `podpull`.
- **v0.4**: cloud-safe filename normalization; multi-episode downloads grouped into a per-show folder.
- **v0.5**: `pull` alias for `get`; `podpull skills install` sets up integrations for Claude Code, Codex, OpenCode, and Cursor.
- **v0.6**: robust feed parsing (RSS 2.0 / RSS 1.0 / Atom, dirty-XML recovery),
  verified against Chinese-market hosts, `ximalaya.com/album/<id>` links, optional
  Podcast Index (BYOK) search + feed-resolution fallback.
- **v0.7**: `--json` output mode for scripting (`podpull --json list … | jq`).
- **v0.8** (current): `podpull serve` + hosted site at [podpull.xiaolei.work](https://podpull.xiaolei.work)
  (landing `/`, app `/app`, metadata `/api`); trending (中文 / International); EN/中文;
  per-episode browser download (no audio proxy).
- **next**: BYOK summarization (`podpull[ai]`).
- **v1+ (`podpull[ai]`)**: opt-in **BYOK summarization** — local transcription
  (faster-whisper) + your own LLM key (Anthropic/OpenAI). Fully local, private,
  no subscription. Cleanly isolated from the core.

## Ethics & legal

podpull reads the **public RSS feeds** that podcasters publish for exactly this
purpose, and downloads the enclosure files they distribute. Respect each show's
copyright and terms — download only what you're entitled to, for personal use.

## License

MIT © xiaoleiyu
