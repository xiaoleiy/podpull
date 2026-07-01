# podpull

[![PyPI](https://img.shields.io/pypi/v/podpull.svg)](https://pypi.org/project/podpull/)
[![CI](https://github.com/xiaoleiy/podpull/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaoleiy/podpull/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/platforms-macOS%20·%20Linux%20·%20Windows-lightgrey.svg)

**Download any podcast episode — Apple Podcasts, RSS, or 小宇宙/xiaoyuzhou — straight to your shell.**

Pick episodes from an **interactive multi-select list**, with spinners and progress bars.
No app, no login, no DRM. Files are named cloud-safe and (for multiple picks) grouped per show.

**▶ Live animated demo & landing page:** https://xiaoleiy.github.io/podpull

## Demo

```text
$ podpull get 1532755821
✓ 我們家的睡前故事 — 394 episodes
? Select episodes  (↑/↓ · space · enter)
❯ ◉ 2026-06-23  EP343 迷宮中的牛頭人
  ◯ 2026-06-16  EP342 午睡任務
  ◉ 2026-06-09  EP341 修煉龍 4
██████████████████  100%  21.2 MB  •  saved to ~/Downloads/Podcasts/我們家的睡前故事/
```

<!-- Animated GIF: `brew install vhs` then `vhs docs/demo.tape` -> docs/demo.gif, then embed here. -->

## How it works

Apple Podcasts hosts **no audio** — it is a directory that points at each show's
RSS feed, and every episode in that feed carries a direct `<enclosure>` audio URL.
podpull walks that chain:

```
Apple show URL/id ──(iTunes Lookup API)──▶ RSS feedUrl
RSS feed          ──(<enclosure url>)────▶ direct .mp3 / .m4a
download          ──(resumable)──────────▶ <YYYY-MM-DD> - <title>.<ext>
```

It also resolves a pasted **xiaoyuzhou** episode page (via its `og:audio` tag) and a
pasted **Apple episode** link (`…?i=<id>`, matched in the feed).

## Install

```bash
# pipx (recommended) or pip — from PyPI
pipx install podpull
pip   install podpull

# or Homebrew (macOS / Linux)
brew install xiaoleiy/tap/podpull
```

Requires Python 3.9+. Optional: `yt-dlp` (deep-catalog Apple-episode fallback),
`ffmpeg`/`ffprobe` (verify downloads). Also on [PyPI](https://pypi.org/project/podpull/).

### Set up your AI coding agents (optional)

Teach your AI agents to use podpull so you can just ask them to grab an episode:

```bash
podpull skills install        # detected agents
podpull skills install --all  # all supported agents
podpull skills status         # see what's detected / installed
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
podpull info  1532755821                  # show metadata (accepts URL, id, or RSS)
podpull list  1532755821                  # recent episodes, numbered (0 = newest)
podpull list  1532755821 --match "EP34"   # filter by title regex
```

### Download

```bash
# Interactive picker — just give a show; pick one or many episodes with the keyboard:
podpull get 1532755821
#   ↑/↓ move · space toggle · a select-all · enter confirm

# Or select non-interactively (also used when piping / scripting):
podpull get 1532755821 --latest 1               # newest episode
podpull get 1532755821 --match "牛頭人"          # by title regex
podpull get 1532755821 --index 0,2,5            # by list number (0 = newest)
podpull get 1532755821 --latest 3 --out ~/Audio/bedtime

# Pasted single-episode links:
podpull get "https://www.xiaoyuzhoufm.com/episode/<id>"
podpull get "https://podcasts.apple.com/.../id<show>?i=<track>"
```

Downloads default to `~/Downloads/Podcasts` (override with `--out`). The saved file
path is printed to **stdout** (so you can pipe/capture it); progress and messages go
to **stderr**. Use `--no-input` to never open the picker (fail instead) for scripts.

**Filenames** are normalized for cloud storage — emoji and other symbols are dropped,
full-width/illegal characters folded or stripped — so files upload cleanly to Google
Drive, OneDrive, Dropbox, iCloud, etc. (CJK and ordinary text are kept). When you grab
**multiple** episodes at once, they're placed in a sub-folder named after the show.

`<src>` accepts: an Apple show URL, a bare Apple ID, a raw RSS feed URL, an Apple
episode URL (`?i=`), or a xiaoyuzhou episode URL.

## Roadmap

- **v0.1**: search · info · list · download (stdlib only).
- **v0.2**: interactive multi-select picker, rich progress bars + spinners,
  colored help, scriptable stdout. Adds `rich` + `questionary`.
- **v0.3**: renamed `podget` → `podpull`.
- **v0.4**: cloud-safe filename normalization; multi-episode downloads grouped into a per-show folder.
- **v0.5** (current): `pull` alias for `get`; `podpull skills install` sets up integrations for Claude Code, Codex, OpenCode, and Cursor.
- **next**: more robust feed parsing, tests on more hosts, Podcast Index support.
- **v1+ (`podpull[ai]`)**: opt-in **BYOK summarization** — local transcription
  (faster-whisper) + your own LLM key (Anthropic/OpenAI). Fully local, private,
  no subscription. Cleanly isolated from the core.

## Ethics & legal

podpull reads the **public RSS feeds** that podcasters publish for exactly this
purpose, and downloads the enclosure files they distribute. Respect each show's
copyright and terms — download only what you're entitled to, for personal use.

## License

MIT © xiaoleiyu
