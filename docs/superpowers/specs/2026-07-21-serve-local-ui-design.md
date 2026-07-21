# Design: `podpull serve` local web UI

Date: 2026-07-21 · Target release: **v0.8.0** (tentative) · Status: **amended — search-first + browser download; awaiting re-approval**

Backlog source: Obsidian `Projects/Podpull/调研 Investigation.md` → 调研 2
(local web UI as GUI demand probe); Follow-ups sequencing **A `--json` → B serve → C BYOK**.

Open Design project: `podpull-serve-ui` (frontend-design skill, Aurora brand).
- Studio: http://127.0.0.1:5174/projects/podpull-serve-ui/conversations/eed87ea6-dc09-49a1-ae58-3c3a031780c9/files/index.html
- Preview: http://127.0.0.1:7456/api/projects/podpull-serve-ui/raw/index.html

## Decisions (locked / amended)

1. **Primary workflow = CLI discovery parity:**  
   **Search / trending → pick episode(s) → download.**  
   Paste-a-link is **not** the hero (Advanced disclosure only).
2. **Download = browser-side, not serve-to-disk (amended 2026-07-21 night):**  
   - Primary: **direct enclosure / `og:audio` URL**.  
   - Strategy **B:** try `fetch` → blob → `<a download>` (**force Save** when CORS allows);
     on failure, **open the audio URL in a new tab** (browser may play or save — CDN-dependent).  
   - Secondary per episode: **Open show/episode page** (Apple / 小宇宙 / feed link) — hybrid **C**.  
   - Multi-select: **one tab / one save attempt per episode** (warn if selecting many, e.g. >5).  
   - **`podpull serve` does not proxy audio** and does not write `~/Downloads/Podcasts`.  
     CLI `podpull get` remains the path for guaranteed disk saves via the tool.
3. **Why we cannot always force Save vs Play:** cross-origin CDNs ignore `<a download>`;
   blob-save needs CORS (often absent). Opening a new tab leaves play-vs-save to the host’s
   `Content-Type` / `Content-Disposition`. UI copy: button **“Download”**; tip when falling
   back: “If it plays in the browser, use Save As.”
4. **Bind:** default `127.0.0.1`; opt-in `--host 0.0.0.0` (document risk).
5. **Architecture:** stdlib HTTP JSON API (metadata only: search / list / trending / resolve)
   + static UI. No audio bytes through serve.
6. **Brand:** Aurora (`#080a11`, mint `#35e0a1`, cyan `#3bc7ff`, Sora / Manrope / JetBrains Mono).
7. **Trending:**
   - **Serve:** 中文 (xyzrank) + International (Apple); ≥24 visible, Load more → 40+.
   - **Landing:** Apple top 24 live (CORS `*`); teaser + install / `podpull serve` CTA.
     xyzrank serve-only.
8. **Paste link:** Advanced only — resolve to enclosure, then same browser download path.

## Non-goals (v0.8)

- Proxying / mirroring audio through serve (bandwidth + ToS risk).
- Guaranteeing “Save as file” on every CDN.
- Hosted SaaS, DRM unlock, Electron, BYOK AI.
- Replacing CLI disk downloads (`podpull get` stays for that).

## Architecture

```
browser  --JSON API-->  serve (stdlib)  --metadata-->  core / charts APIs
   |                         (no audio)
   +-- fetch/open enclosure URL ------>  podcast CDN  (bytes stay client↔ CDN)
```

### Module layout (proposed)

```
src/podpull/
  serve/
    __init__.py
    server.py      # metadata routes only
    trending.py    # xyzrank + Apple charts
    static/        # UI; client does blob-save / tab open
  cli.py
```

### CLI

```
podpull serve [--host 127.0.0.1] [--port 8787] [--no-open]
```

`--out` is **not** needed for serve (no server-side saves). Optional later if we add a
“also save with CLI” bridge — YAGNI for v0.8.

### HTTP API (draft)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | `{ ok, version }` |
| GET | `/api/trending?source=xyzrank\|apple&limit=&offset=&country=` | Show cards |
| GET | `/api/search?q=&limit=` | `--json search` shape |
| GET | `/api/info?src=` | `--json info` shape |
| GET | `/api/list?src=&match=&limit=&all=` | Episodes **must include `url`** (enclosure) + optional `link` (episode page) |
| POST | `/api/resolve` | `{ src }` for Advanced paste → `{ title, url, link? }` (enclosure + page) |

No `POST /api/download` that streams audio. Client uses `url` from list/resolve.

### Trending sources (verified 2026-07-21)

| Source | URL | Notes |
|---|---|---|
| xyzrank 热门播客 | `https://xyzrank.com/api/podcasts` | Prefer apple/rss from `links[]` |
| Apple Top Podcasts | `https://itunes.apple.com/{cc}/rss/toppodcasts/limit={N}/json` | Official JSON |

Serve-side fetch + short TTL cache. Soft-fail per source.

## UI structure (search-first)

**First viewport:** brand + find-a-show headline + **Search** CTA (no paste).

**Below:**
1. **Trending** — 中文 | International; dense grid; Load more; attribution.
2. **Episodes** — checkboxes; **Download** (blob then fallback); **Open page** link per row;
   multi → one attempt per selected episode; confirm if count > 5.
3. **Status** — “Saved / opened N episode(s)” (not filesystem paths from serve).
4. **Advanced** — paste episode link → same download helpers.

## Marketing landing companion

- Apple top 24 teaser after hero; links to Apple show URL + `podpull get <id>` hint.
- CTA: install + `podpull serve` for 中文榜 + in-browser episode download.
- No audio proxy on Pages.

## Success criteria

- Hero is search, not paste.
- Trending works; list returns enclosure `url`s.
- Download tries blob-save, falls back to new tab; Open page works; no audio through serve.
- Landing Apple strip; offline tests; no new runtime deps; `core.py` purity.

## Out of scope

Audio proxy, forced Save on all CDNs, Electron, BYOK AI, xyzrank on static Pages.
