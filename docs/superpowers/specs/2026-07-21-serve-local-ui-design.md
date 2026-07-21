# Design: `podpull serve` local web UI

Date: 2026-07-21 · Target release: **v0.8.0** (tentative) · Status: **amended — search-first UX; awaiting re-approval**

Backlog source: Obsidian `Projects/Podpull/调研 Investigation.md` → 调研 2
(local web UI as GUI demand probe); Follow-ups sequencing **A `--json` → B serve → C BYOK**.

Open Design project: `podpull-serve-ui` (frontend-design skill, Aurora brand).
- Studio: http://127.0.0.1:5174/projects/podpull-serve-ui/conversations/eed87ea6-dc09-49a1-ae58-3c3a031780c9/files/index.html
- Preview: http://127.0.0.1:7456/api/projects/podpull-serve-ui/raw/index.html

## Decisions (locked / amended)

1. **Primary workflow = CLI parity (amended 2026-07-21 evening):**  
   **Search show → pick episode(s) → download.**  
   Paste-a-link is **not** the hero. Most users cannot easily obtain an episode URL;
   the CLI/TUI already centers search/list/get. The local UI must match.
2. **Download outcome:** server writes files to disk (`~/Downloads/Podcasts` or `--out`);
   UI shows success + path(s). Not a browser Save-dialog primary path.
3. **Bind:** default `127.0.0.1` only; opt-in `--host 0.0.0.0` for LAN (document risk).
4. **Architecture:** stdlib HTTP JSON API calling `core.py` + static UI assets vendored from
   Open Design (no React/build toolchain at runtime).
5. **Brand:** Aurora (`#080a11`, mint `#35e0a1`, cyan `#3bc7ff`, Sora / Manrope /
   JetBrains Mono, soft aurora blobs).
6. **Trending discovery:**
   - **`podpull serve`:** tabs **中文 (xyzrank 热门播客)** + **International (Apple Top
     Podcasts)**; click show → episode list → download. Load **more** shows (default
     **40** per tab, “Load more” to next page / higher limit). Episode lists default
     **40** recent with “show more” / `--all`-equivalent.
   - **Marketing landing (`docs/index.html`):** also shows trending — **Apple charts
     live** (CORS `*`), denser strip (**top 24**). Teaser only (no disk download on
     Pages). CTA to install + `podpull serve` for 中文榜 + actual downloads. xyzrank
     remains serve-only (no reliable browser CORS).
7. **Paste link:** demoted to a small **Advanced** disclosure (“Already have an episode
   link?”) below the fold — optional power-user path for Apple `?i=` / 小宇宙 URLs.
   Not in the first viewport.

## Non-goals (v0.8)

- Hosted / public SaaS, audio proxying for third parties, accounts, DRM/paid unlock.
- Native desktop wrapper.
- BYOK summarization (C — later).
- Replacing the CLI or agent channel.
- Making paste-link the primary discovery path.

## Architecture

```
browser  --HTTP-->  serve (stdlib)  --calls-->  core.py (+ trending fetchers)
   ^                      |
   |                      +-- writes audio under --out
   +-- static HTML/CSS/JS packaged in wheel
```

### Module layout (proposed)

```
src/podpull/
  serve/
    __init__.py
    server.py      # HTTP handler + route table (stdlib)
    trending.py    # xyzrank + Apple chart fetch/normalize (stdlib)
    static/        # index.html — from OD, wired to API
  cli.py           # `serve` subcommand
```

`core.py` stays dependency-free. Prefer `--json` (v0.7) dict shapes for search/list/download.

### CLI

```
podpull serve [--host 127.0.0.1] [--port 8787] [--out DIR] [--no-open]
```

### HTTP API (draft)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | `{ ok, version }` |
| GET | `/api/trending?source=xyzrank\|apple&limit=40&offset=0&country=US` | Paginated shows |
| GET | `/api/search?q=&limit=` | `--json search` shape |
| GET | `/api/info?src=` | `--json info` shape |
| GET | `/api/list?src=&match=&limit=&all=` | `--json list`; default limit 40 |
| POST | `/api/download` | `{ src, match?, latest?, index? }` → `{ show, downloads }` |

Ignore client-supplied `out`; always use server `--out`.

### Trending sources (verified 2026-07-21)

| Source | URL | Notes |
|---|---|---|
| xyzrank 热门播客 | `https://xyzrank.com/api/podcasts` | `items[]` with `links` apple/rss/xyz |
| Apple Top Podcasts | `https://itunes.apple.com/{cc}/rss/toppodcasts/limit={N}/json` | Official; `limit` up to 200 |

Serve-side fetch + short TTL cache (15–60 min). Soft-fail per source.

## UI structure (search-first)

**First viewport (one composition):**
- Brand `podpull`
- Headline oriented to **find a show** (not “paste a link”)
- One supporting line
- **Search field + Search CTA** (primary)
- Optional muted hint: trending is just below

**Next sections:**
1. **Trending** — 中文 | International; dense grid (**≥24 visible**, Load more → 40+);
   click → episode panel.
2. **Episodes** — checkbox multi-select (CLI picker parity); Download selected; show more
   episodes when the feed is long.
3. **Status** — progress / path success + copy / error.
4. **Advanced (collapsed)** — paste episode URL.

No paste field in the hero. No podcast “manager” chrome (library/player/subscriptions).

## Marketing landing companion

- Section after hero (not inside first viewport): **Trending on Apple Podcasts** —
  fetch top **24** client-side; art + title + rank; link to Apple URL + monospace
  `podpull get <id>` hint.
- Soft-fail if charts unavailable.
- CTA: install + `podpull serve` for 中文 trending + downloads.
- Aurora styling; one job = discovery teaser.

## Open Design handoff

- Project: `podpull-serve-ui` — rewrite mock to search-first + denser trending.
- After approval: vend into `src/podpull/serve/static/`; wire `fetch('/api/…')`.
- No frontend build step.

## Success criteria

- Hero is search, not paste.
- Trending 中文 + International; ≥24 shows initially; load more works.
- Click show → episodes → multi-download to `--out` with paths in UI.
- Landing shows Apple top 24 teaser.
- Offline tests mock network; `core.py` purity; no new runtime deps.

## Out of scope

NDJSON progress streaming, auth, Electron, BYOK AI, xyzrank on static Pages.
