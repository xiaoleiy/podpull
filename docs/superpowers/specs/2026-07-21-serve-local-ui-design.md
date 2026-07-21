# Design: `podpull serve` local web UI

Date: 2026-07-21 · Target release: **v0.8.0** (tentative) · Status: **amended — trending discovery; awaiting re-approval**

Backlog source: Obsidian `Projects/Podpull/调研 Investigation.md` → 调研 2
(local web UI as GUI demand probe); Follow-ups sequencing **A `--json` → B serve → C BYOK**.

Open Design project: `podpull-serve-ui` (frontend-design skill, Aurora brand).
- Studio: http://127.0.0.1:5174/projects/podpull-serve-ui/conversations/eed87ea6-dc09-49a1-ae58-3c3a031780c9/files/index.html
- Preview: http://127.0.0.1:7456/api/projects/podpull-serve-ui/raw/index.html
- Note: first OD pass overbuilt a manager app; rewrite pass matches this spec (hero paste + browse + status).

## Decisions (locked 2026-07-21)

1. **Flows:** paste-link hero **and** browse-a-show secondary (search → checkbox → download).
2. **Download outcome:** server writes files to disk (`~/Downloads/Podcasts` or `--out`);
   UI shows success + path(s). Not a browser Save-dialog primary path.
3. **Bind:** default `127.0.0.1` only; opt-in `--host 0.0.0.0` for LAN (document risk).
4. **Architecture:** stdlib HTTP JSON API calling `core.py` + static UI assets vendored from
   Open Design (no React/build toolchain at runtime). Approach **2** from brainstorming.
5. **Brand:** Aurora (match landing: `#080a11`, mint `#35e0a1`, cyan `#3bc7ff`, Sora /
   Manrope / JetBrains Mono, soft aurora blobs).
6. **Trending discovery (amendment 2026-07-21):**
   - **`podpull serve`:** interactive trending — tabs **中文 (xyzrank 热门播客)** +
     **International (Apple Top Podcasts)**; click a show → episode list → download.
     Also keep free-text search.
   - **Marketing landing (`docs/index.html`):** live **Apple charts only** (browser fetch;
     CORS `*`). Teaser cards link to install / “run `podpull serve`” — **no download on
     Pages**. xyzrank stays serve-only (API lacks reliable browser CORS).

## Non-goals (v0.8)

- Hosted / public SaaS, audio proxying for third parties, accounts, DRM/paid unlock.
- Native desktop wrapper.
- BYOK summarization (C — later).
- Replacing the CLI or agent channel.

## Architecture

```
browser  --HTTP-->  serve (stdlib)  --calls-->  core.py
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
    static/        # index.html (+ css/js if split) — from OD, trimmed
  cli.py           # `serve` subcommand
```

`core.py` stays dependency-free. Prefer reusing the same dict shapes as `--json`
(v0.7) for API responses where practical (`search` / `list` / download results).

### CLI

```
podpull serve [--host 127.0.0.1] [--port 8787] [--out DIR] [--no-open]
```

- Prints the URL to stderr; optionally opens the default browser (`webbrowser`).
- Blocks until Ctrl-C.
- `--host` default `127.0.0.1`; LAN bind requires explicit `0.0.0.0` (or a LAN IP).

### HTTP API (draft)

All under `/api/…`, JSON in/out, UTF-8. Errors: `{ "error": "…" }` + 4xx/5xx.

| Method | Path | Body / query | Success |
|---|---|---|---|
| GET | `/api/health` | — | `{ "ok": true, "version": "…" }` |
| GET | `/api/trending?source=xyzrank\|apple&limit=20&country=US` | — | `{ "source", "country"?, "shows": [ { rank, title, author, apple_id?, feed?, artwork?, links? } ] }` |
| GET | `/api/search?q=&limit=` | — | same shape as `--json search` (`query` + `results`) |
| GET | `/api/info?src=` | — | `--json info` shape |
| GET | `/api/list?src=&match=&limit=&all=` | — | `--json list` shape |
| POST | `/api/download` | `{ "src": "…", "match"?, "latest"?, "index"?, "out"? }` | `{ "show": {…}, "downloads": [ {date,title,url,path} ] }` |

### Trending data sources (verified 2026-07-21)

| Source | URL | Notes |
|---|---|---|
| xyzrank 热门播客 | `GET https://xyzrank.com/api/podcasts` | JSON `{ items: [...] }`; each item has `name`, `logoURL`, `links[]` with `apple` / `rss` / `xyz`. Prefer `apple` id or `rss` as `src` for list/download. Credit: [中文播客榜](https://xyzrank.com/) / 枫言枫语. |
| Apple Top Podcasts | `GET https://itunes.apple.com/{cc}/rss/toppodcasts/limit={N}/json` | Official RSS-JSON; `entry[].id.attributes.im:id` → Apple show id. Default `cc=US` for International tab; optional CN storefront is a later tweak. CORS `*` (also usable from Pages). |

- Serve fetches these **server-side** (stdlib `urllib`); short in-memory TTL cache (~15–60 min) to be polite.
- On xyzrank failure: return Apple-only + warning field; never block the whole UI.
- Do **not** scrape xyzrank HTML; use their public JSON only. Respect their non-official disclaimer in UI footer/attribution.

- Paste-link path: `POST /api/download` with episode URL as `src` (no selector).
- Browse path: `search` → `list` → `download` with `index` / `match` / `latest`.
- Downloads are **synchronous** for v1 of serve (request waits until files finish).
  Progress can be a later SSE/`--json`-style enhancement if needed; mock may show a
  client-side spinner while the request is in flight.
- Reject path traversal / absolute `out` outside the configured root if we ever accept
  client `out` — safer: ignore client `out` and always use the server's `--out`.

### Static routes

- `GET /` → `index.html`
- `GET /assets/…` → static files
- No directory listing.

### Security posture

- Default loopback bind.
- No auth (localhost trust model).
- When `--host` is non-loopback, print a loud stderr warning.
- Do not follow redirects to `file:` or unexpected schemes in download URLs beyond what
  `core` already does.
- CORS: same-origin only (UI served from the same host) — no `Access-Control-Allow-Origin: *`.

## UI structure (product; visuals from OD)

1. **Hero:** brand `podpull` (mint on “pull”), one headline, one line, paste field + Download; aurora blobs on `#080a11`.
2. **Trending (new):** below hero — chips/tabs **中文** | **International**; horizontal or compact grid of top shows (art + title + rank). Click → load episodes (same panel as browse). Attribution line for xyzrank / Apple.
3. **Browse / search:** free-text search (existing) when the user wants a specific show; episode checkboxes → Download selected.
4. **Status:** progress → success with path + Copy → error.

Hero stays one composition (no trending cards *inside* the first viewport). Trending is the next section — discovery without competing with paste CTA.

Handoff: copy/adapt OD HTML into `src/podpull/serve/static/`, wire `fetch('/api/trending')` + list/download.

## Marketing landing (`docs/index.html`) — companion

- New section **after** the hero pipeline (not inside the first viewport): “Trending on Apple Podcasts” — fetch
  `https://itunes.apple.com/us/rss/toppodcasts/limit=8/json` client-side; render title + artwork + rank.
- Each card links to the Apple show URL (and/or a monospace hint `podpull get <id>`).
- CTA under the strip: install brew/pipx + “For 中文榜 + one-click download: `podpull serve`”.
- No xyzrank on Pages (CORS). Fail soft: hide section or show “charts unavailable”.
- Keep Aurora visual language; one job for the section (discovery teaser only).

## Packaging & docs

- Static files as wheel package data (like `integrations/`).
- README: `podpull serve` section; ethics note unchanged (personal use / public RSS).
- Integrations: mention `serve` for humans who prefer a browser over the CLI.
- Obsidian Follow-ups: check off when shipped.

## Open Design handoff

- Project id: `podpull-serve-ui`
- After mock approval: copy/adapt HTML/CSS/JS into `src/podpull/serve/static/`, strip
  unused chrome, wire fetch() to the API above.
- Do **not** add a frontend build step.

## Success criteria

- `podpull serve` opens UI on loopback; paste a known xiaoyuzhou/Apple episode link →
  file appears under `--out`; UI shows path.
- Trending: 中文 tab loads xyzrank shows; International loads Apple US top; click → episodes → download.
- Browse/search still works alongside trending.
- Landing: Apple top strip renders (or soft-fails); no download from Pages.
- Offline tests: mock trending fetchers; handler unit tests. Default suite never hits network.
- `core.py` purity intact; no new runtime deps.

## Out of scope

NDJSON progress streaming, auth, reverse-proxy deploy guides, Electron, BYOK AI.
