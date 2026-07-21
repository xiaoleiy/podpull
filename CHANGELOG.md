# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [0.8.1] — 2026-07-21

### Fixed
- **`podpull serve` search results** now appear above trending (with status text and artwork),
  so keyword search no longer looks like a no-op.
- Show tiles share a fixed footprint (square art + reserved title/author lines) in trending
  and search grids.

### Changed
- Episode list uses per-row **Download** / **Open page** actions instead of multi-select bulk
  download (browsers block multiple file downloads by default).
- Serve UI and marketing landing: EN / 中文 language switch (preference in `localStorage`).
- Landing hero copy aligned to: find episodes → download to disk (`~/Downloads/Podcasts`).
- Serve favicon uses the podpull icon (`icon.svg` / `favicon-32.png`).

## [0.8.0] — 2026-07-21

### Added
- **`podpull serve`** — local web UI (default `http://127.0.0.1:8787`): search shows,
  browse trending (**中文** via [xyzrank](https://xyzrank.com/) · **International** via
  Apple Top Podcasts), pick episodes, then download enclosure URLs **in the browser**
  (blob-save when CORS allows, else new tab). Does not proxy audio. `--host` / `--port` /
  `--no-open`.
- Marketing landing: live Apple Top Podcasts strip (top 24) with CLI id hints.

## [0.7.0] — 2026-07-21

### Added
- Global `--json` flag (`podpull --json <command> …`): emits one JSON document on
  stdout for `search` / `info` / `list` / `get`, with no rich UI. Failures stay
  human messages on stderr + non-zero exit. Implies quiet for `get` (no picker /
  progress). Place `--json` before the subcommand.

## [0.6.0] — 2026-07-08

### Added
- `-q/--quiet` flag for `podpull get`: suppresses the spinner/progress UI and prints
  only saved file paths to stdout — for scripting/piping. (#1, thanks @adjenk!)
- Robust feed parsing: RSS 2.0 / RSS 1.0 (RDF) / Atom, any-namespace matching,
  `media:content` + Atom-enclosure fallbacks, dirty-XML sanitize-and-retry
  (undefined entities, bare `&`, control chars), ISO-8601 dates.
- Verified against Chinese-market hosts: xiaoyuzhou, Ximalaya, SoundOn, Firstory,
  WavPub, Typlog, Fireside, Lizhi (offline fixtures + `pytest -m network` live suite).
- `ximalaya.com/album/<id>` links are now accepted directly.
- Optional Podcast Index support (BYOK: `PODCASTINDEX_API_KEY`/`_SECRET`):
  enriches `search` and adds a feed-resolution fallback when iTunes has no feed.

### Fixed
- Download guard: `text/*` responses (stale enclosures, e.g. Ximalaya CDN) now
  error instead of writing a garbage audio file.

## [0.5.1] — 2026-06-30

### Fixed
- **Windows compatibility**: normalized filenames now avoid Windows reserved device names
  (`CON`, `NUL`, `COM1`…, even with an extension); stdout/stderr are reconfigured to UTF-8 so CJK
  titles/paths never raise `UnicodeEncodeError` on a legacy console or when piped.
- **CI** now runs on Windows and macOS in addition to Linux (Python 3.9/3.11/3.13).

## [0.5.0] — 2026-06-30

### Added
- **`podpull skills install`** — sets up podpull integrations for AI coding agents in their
  native formats: Claude Code & Codex skills (`SKILL.md`), an OpenCode `/podpull` command, and a
  Cursor project rule. Also `podpull skills status` and `podpull skills uninstall`. Detects
  installed agents by default; `--all` installs for every supported agent. Idempotent (re-run to
  refresh after upgrades); nothing is written until you run it.
- **`pull` alias** for `get` — `podpull pull …` works the same as `podpull get …`.

## [0.4.0] — 2026-06-30

### Added
- **Per-show folders**: selecting multiple episodes now saves them into a sub-folder
  named after the show (single-episode downloads still land directly in `--out`).

### Changed
- **Cloud-safe filename normalization**: titles are NFKC-folded, emoji/other symbols
  and control/format characters dropped, OS-forbidden and full-width characters
  stripped, and whitespace/edges trimmed — so files upload cleanly to Drive/OneDrive/
  Dropbox/iCloud. CJK and ordinary punctuation are preserved. Empty results fall back
  to `untitled`; names cap at 120 chars.

## [0.3.0] — 2026-06-29

### Changed
- **Renamed `podget` → `podpull`** — repo, command, import package, and Homebrew formula.
  No functional changes. (`podget` was taken on PyPI; `podpull` is free, descriptive, and
  reads as "pull a pod".) The old GitHub URL auto-redirects.

## [0.2.1] — 2026-06-29

### Fixed
- **xiaoyuzhou 403**: `feed.xyzfm.space` (and similar CDNs) returned `HTTP 403 Forbidden`
  to podpull's tool User-Agent, breaking `info`/`list`/`get` for xiaoyuzhou-hosted shows
  (e.g. 小小新问 LittleNews). podpull now sends a standard browser User-Agent.
- Running `podpull` with no command prints usage/help (exit 0) instead of an argparse error.

### Added
- Project landing page under `docs/` (served via GitHub Pages).

## [0.2.0] — 2026-06-29

UX overhaul. Adds dependencies: `rich`, `rich-argparse`, `questionary`.

### Added
- **Interactive multi-select picker**: `podpull get <show>` with no selector opens a
  keyboard-driven checkbox list (↑/↓ move, space toggle, `a` select-all, enter confirm).
- **Progress feedback**: spinners with step messages for network fetches (resolving
  show → fetching feed → parsing), and `rich` progress bars (size, speed, ETA) for downloads.
- **Colored, example-rich help** via `rich-argparse`; grouped `get` selection options.
- `--no-input` flag on `get` to never prompt (for scripts/CI).

### Changed
- Saved file paths print to **stdout**; all UI (spinners, tables, bars, messages) to **stderr** — clean for scripting.
- `search`/`list`/`info` now render as tidy tables.
- Non-interactive / piped `get <show>` without a selector falls back to a listing + hint instead of hanging.
- `core.download_url` reports progress via an `on_progress(done, total)` callback (core stays dependency-free).

## [0.1.0] — 2026-06-29

Initial public release. Core feature set, Python standard library only.

### Added
- `podpull search <term>` — find shows via the iTunes Search API.
- `podpull info <src>` — show metadata (title, author, Apple id, feed, episode count, latest).
- `podpull list <src>` — list episodes, with `--match REGEX`, `--all`, `--limit`.
- `podpull get <src>` — download episode audio, by `--match` / `--latest N` / `--index 0,2`.
- Direct episode links: xiaoyuzhou (`og:audio`) and Apple (`?i=`, matched in feed; `yt-dlp` fallback).
- Resumable, stdlib-only downloader; filenames as `YYYY-MM-DD - title.ext`.
