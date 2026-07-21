# `podpull serve` + landing trending Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `podpull serve` — local metadata UI (search / trending / episodes) with browser-side enclosure download (blob-save then new-tab fallback) — plus an Apple trending strip on the marketing landing page.

**Architecture:** Stdlib HTTP server + `trending.py` fetchers call `core` for feed/search; static `index.html` never proxies audio. Landing page fetches Apple RSS-JSON client-side only.

**Tech Stack:** Python ≥3.9 stdlib (`http.server`, `urllib`, `json`); existing `core.py`; pytest; Aurora static HTML/JS.

**Spec:** `docs/superpowers/specs/2026-07-21-serve-local-ui-design.md` (approved)

## Global Constraints

- `core.py` stays pure stdlib; no new runtime dependencies.
- Serve does **not** proxy audio or write `--out` files; CLI `get` remains for disk saves.
- Download UX: blob-save when CORS allows, else `window.open(enclosure)`; secondary “Open page”; one attempt per selected episode.
- Default bind `127.0.0.1`; `--host 0.0.0.0` opt-in with stderr warning.
- Offline tests only in default suite; mock HTTP for trending.
- Version bump **0.8.0** in `__init__.py` + `pyproject.toml`.
- Package static files under `src/podpull/serve/static/` (wheel data via package dir).

## File map

| Path | Role |
|---|---|
| `src/podpull/serve/__init__.py` | package |
| `src/podpull/serve/trending.py` | xyzrank + Apple chart normalize |
| `src/podpull/serve/server.py` | HTTP routes + static |
| `src/podpull/serve/static/index.html` | UI (from OD, wired to API) |
| `src/podpull/cli.py` | `serve` subcommand |
| `tests/test_trending.py` | unit tests |
| `tests/test_serve.py` | handler tests via `HTTPConnection` / handler |
| `docs/index.html` | Apple top-24 strip |
| README / CHANGELOG / integrations / Follow-ups | docs |

---

### Task 1: Trending fetchers + tests

**Files:** Create `src/podpull/serve/trending.py`, `tests/test_trending.py`

- [ ] **Step 1:** Failing tests for `fetch_apple_charts(country, limit)` and `fetch_xyzrank_podcasts(limit, offset)` with mocked `urllib` / `core.fetch` / `fetch_json`.
- [ ] **Step 2:** Implement normalize → `{ rank, title, author, apple_id, feed, artwork, page_url }` (xyzrank: parse apple id from links; prefer rss as feed).
- [ ] **Step 3:** pytest green; commit.

### Task 2: HTTP server (metadata API)

**Files:** Create `src/podpull/serve/server.py`, `tests/test_serve.py`

Routes: `/api/health`, `/api/trending`, `/api/search`, `/api/info`, `/api/list`, `/api/resolve`, `GET /` + static.
- List/resolve JSON must include episode `url` + optional `link`.
- In-memory TTL cache for trending (~30 min).
- [ ] Tests with mocked core/trending; commit.

### Task 3: CLI `serve` + static UI

**Files:** `cli.py`, `serve/static/index.html` (adapt OD artifact)

- [ ] `podpull serve [--host] [--port] [--no-open]`
- [ ] UI: search-first; trending tabs; episodes; Download = blob then tab; Open page; Advanced paste → `/api/resolve`
- [ ] Commit.

### Task 4: Landing Apple strip + docs + v0.8.0

**Files:** `docs/index.html`, README, CHANGELOG, integrations, version files, Obsidian Follow-ups

- [ ] Section after hero: fetch Apple top 24; soft-fail; CTA to serve.
- [ ] Bump 0.8.0; pytest + ruff; commit.

## Out of scope

Audio proxy, `--out` on serve, xyzrank on Pages, BYOK AI.
