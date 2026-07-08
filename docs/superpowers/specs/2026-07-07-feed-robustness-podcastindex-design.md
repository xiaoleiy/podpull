# Design: robust feed parsing, multi-host tests, Podcast Index support

Date: 2026-07-07 · Target release: **v0.6.0** · Status: awaiting user review

Backlog source: Obsidian `Projects/Podpull/跟进 Follow-ups.md` → "later hardening":
robust parsing across arbitrary hosts, tests vs more hosts + a network-marked integ
test, Podcast Index API ("richer search than iTunes"). `--json` mode is **out of
scope** for this iteration (not requested).

## Decisions (made while user was AFK — please confirm)

1. **No `feedparser`; harden the stdlib parser instead.** CLAUDE.md invariant #1
   (`core.py` stays pure stdlib) outweighs the backlog's "consider feedparser".
   podpull needs only title/author/enclosure/date per item — a narrow slice that
   stdlib `ElementTree` + targeted fallbacks covers. Avoids optional-dep matrix,
   Homebrew resource churn, and a heavyweight dependency.
2. **Podcast Index = search enrichment + resolve fallback**, BYOK via env vars
   `PODCASTINDEX_API_KEY` / `PODCASTINDEX_API_SECRET`. With no keys set, behavior
   is byte-for-byte unchanged. Not a first-class input source (no PI URLs/IDs as
   `get` arguments) — YAGNI, can be added later.
3. **Host coverage** (revised 2026-07-07 after Chinese-market research, per user
   request) = the hosts that actually carry mainstream Chinese-language podcasts —
   xiaoyuzhou/xyzfm, Ximalaya RSS export, SoundOn, Firstory, WavPub/播客公社,
   Typlog, Fireside, Lizhi — plus global hosts (Anchor/Spotify, Acast, Omny,
   Libsyn, Transistor) and synthetic edge-case fixtures (Atom, RSS 1.0/RDF,
   dirty entities, media:content-only, UTF-16/BOM). Closed CN platforms
   (蜻蜓FM, 网易云音乐播客, Ximalaya's non-enrolled/paid catalog) stay out of
   scope — no public RSS; supporting them means scraping, a different project.

## 1. Robust feed parsing (`core.py`)

`parse_feed(feed_url) -> (title, author, episodes)` keeps its signature; all
changes are internal. New small helpers (all stdlib):

- **`_localname(tag)`** — strip `{namespace}` so traversal matches elements by
  local name regardless of namespace or prefix. This one change makes RSS 2.0,
  namespaced RSS 1.0 (RDF), and Atom traversable with shared code.
- **Feed shapes**: RSS 2.0 `channel/item` (current), RSS 1.0 `{rss-1.0}item`,
  Atom `feed/entry`.
- **`_find_enclosure(item)`** — per-item audio URL discovery, priority order:
  1. `<enclosure url=…>` (any namespace)
  2. `<media:content url=…>` (MRSS ns) with `type` audio/* or `medium="audio"` —
     first match wins
  3. Atom `<link rel="enclosure" href=…>`
  Items with no audio URL are skipped, as today. First match wins **and stops** —
  WavPub and Omny feeds carry a duplicate `media:content` alongside `enclosure`
  per item; the priority order must yield exactly one URL, never two episodes.
- **Metadata fallbacks** (first non-empty wins):
  - show author: `itunes:author` (accept both `http://` and `https://` namespace
    variants) → `managingEditor` → `dc:creator` → Atom `author/name`
  - episode pub date: `pubDate` → `dc:date` → Atom `published`/`updated`
  - title/guid/link: by localname (ET already folds CDATA to text); collapse
    whitespace
- **`Episode.date`** — RFC-822 parse (current) then ISO-8601 fallback
  (`datetime.fromisoformat`, tolerating trailing `Z`); `0000-00-00` as last resort.
- **`_sanitize_xml(raw: bytes)` recovery path** — `ET.fromstring` is tried on the
  raw bytes first (honors XML encoding declarations; strip UTF-8/16 BOM first).
  Only on `ParseError` do we sanitize and retry once:
  - undefined named HTML entities (`&nbsp;` etc.) → numeric refs via
    `html.entities.html5` (XML's five predefined entities left untouched)
  - bare `&` not starting a valid entity → `&amp;`
  - stray control chars (except tab/newline/CR) → dropped
  If the retry still fails, raise the original `ParseError` (fail loudly, not
  silently-empty).

- **Input classification**: `classify()` learns one new pattern —
  `ximalaya.com/album/<id>` (album page or `.xml` link) → kind `rss` normalized
  to `https://www.ximalaya.com/album/<id>.xml`. Ximalaya's Podcast托管 product
  issues public RSS at exactly that URL; for non-enrolled albums the fetch 404s
  and the existing error path reports it. (No page scraping.)
- **Download sanity guard** (`download_url`) — Ximalaya's CDN answers a
  malformed/stale enclosure query with **HTTP 200, `Content-Type: text/plain`,
  a 7-byte body** — today podpull would write a 7-byte ".m4a" and exit 0. New
  guard: when the destination is an audio download and the final response's
  `Content-Type` starts with `text/`, raise `ValueError` ("server returned text,
  not audio — feed enclosure may be stale") instead of writing the file.
  `application/octet-stream` and all `audio/*` types remain accepted.

Explicitly **not** doing: full HTML-in-XML soup recovery, itunes:duration/episode
numbers (no consumer yet), paged feeds (RFC 5005), non-audio enclosure handling,
scraping closed CN platforms (蜻蜓FM / 网易云音乐 / Lizhi-app-only content).

## 2. Podcast Index support (`core.py` + `cli.py`)

Core (pure stdlib — auth is `hashlib.sha1`):

- `PODCASTINDEX_API = "https://api.podcastindex.org/api/1.0"`
- `pi_credentials() -> tuple[str, str] | None` — reads the two env vars; `None`
  disables everything PI-related.
- `_pi_get(path, params)` — GET with headers `X-Auth-Key`, `X-Auth-Date` (unix ts),
  `Authorization: sha1(key + secret + ts)` hexdigest, and the existing `UA`.
- `pi_search_shows(term, limit) -> list[dict]` — `/search/byterm`; results
  normalized to the **same dict keys the iTunes search path yields**
  (`collectionName`, `artistName`, `feedUrl`, `collectionId`) so `cli.cmd_search`'s
  table code is reused untouched.
- `pi_feed_by_itunes_id(pid) -> str | None` — `/podcasts/byitunesid`; used by
  `apple_show_to_feed` as a fallback **only when** iTunes lookup returns no
  result or no `feedUrl` and credentials exist.
- **Chinese-content caveat (from 2026-07-07 research):** Podcast Index does
  index CN/TW shows (incl. `feed.xyzfm.space` feeds) but lags feed migrations —
  observed stale feed URLs (故事FM) and duplicate entries (声动早咖啡 on both its
  old Fireside and new xyzfm feeds). iTunes therefore stays the primary
  directory; PI is enrichment/fallback only — which is exactly this design.
  Related: keep `search_shows`'s `country=US` default; the US storefront indexes
  every sampled CN/TW show while `country=CN` is censored (e.g. 不明白播客 absent).

CLI (`cmd_search`): when credentials exist, query iTunes then Podcast Index,
merge and dedupe by normalized `feedUrl` (iTunes result wins ties), render the
same table. Either backend failing degrades gracefully: warning to stderr, the
other backend's results still shown (search fails only when both fail — and
without keys, iTunes failure behaves exactly as today). No new CLI flags. Help epilog + README document the env
vars; integrations files get a one-line note (env vars only — no flag/UX change).

## 3. Tests

- **Offline fixtures** (default suite, no network — CLAUDE.md rule):
  `tests/fixtures/feeds/*.xml`, each a trimmed 2–3-item sample reproducing the
  host's observed quirks (verified live 2026-07-07):

  | Fixture | Modeled on | Quirk the fixture must reproduce |
  |---|---|---|
  | `xiaoyuzhou` | 忽左忽右 (`feed.xyzfm.space/cv4bkgpuglwp`) | CDATA-heavy; `dts-api.xiaoyuzhoufm.com/track/...` tracking enclosure with nested host-in-path |
  | `ximalaya` | 声动早咖啡 (`ximalaya.com/album/51076156.xml`) | `//` double-slash in enclosure path; `&amp;`-escaped query with nested full URL in `jt=` param |
  | `soundon` | 股癌 (`feeds.soundon.fm/podcasts/<uuid>.xml`) | `soundon:` custom namespace; self-referencing `itunes:new-feed-url`; `?times=` querystring enclosure |
  | `firstory` | 百靈果 News (`feed.firstory.me/rss/user/<cuid>`) | **every** field CDATA-wrapped incl. `<language>`; stale channel-level `pubDate`; percent-encoded URL embedded in enclosure path |
  | `wavpub` | 半拿铁 (`proxy.wavpub.com/caffebreve.xml`) | duplicate `enclosure` **and** `media:content` per item (must yield 1 episode, not 2); 15 declared namespaces |
  | `typlog` | 疯投圈 (`crazy.capital/feed`) | zero CDATA, fully entity-escaped text (counter-fixture) |
  | `fireside` | 科技早知道 (`feeds.fireside.fm/guiguzaozhidao/rss`) | `+0800` timezone pubDates; `podcast:` (Podcasting 2.0) namespace |
  | `lizhi` | 大内密谈 (`rss.lizhi.fm/rss/14275.xml`) | non-zero-padded RFC-822 dates (`Sun, 5 Jul 2026`); plain-`http` feed URL |
  | `anchor` | 台灣通勤第一品牌 | percent-encoded CloudFront URL inside enclosure path |
  | `acast`, `omny`, `libsyn`, `transistor` | 不明白播客 / 馬力歐陪你喝一杯 / — | Omny: 2× `media:content` + enclosure per item; others: mainstream-global regression |
  | `atom`, `rss10_rdf`, `dirty_entities`, `media_content_only`, `utf16_bom` | synthetic | Atom feed/entry; RSS 1.0 namespaced items; undefined `&nbsp;` + bare `&`; MRSS-only items; UTF-16 + BOM |

  A parametrized `test_core` case asserts per fixture: parse succeeds, expected
  show title/author, episode count (dedupe!), first episode URL + date. Plus a
  unit test that `fetch`/`download_url` send `core.UA` — four of the CN hosts
  (SoundOn, Typlog, Fireside, Lizhi CDN) 403 `Python-urllib`, so the browser-UA
  invariant (CLAUDE.md #5) now has teeth beyond xiaoyuzhou.
- **Podcast Index tests** (offline): auth-header construction with a frozen
  timestamp; env-var gating (no keys → PI functions never called); result
  normalization; `apple_show_to_feed` fallback path; search merge/dedupe in
  `cli` with mocked core.
- **Network integ test**: `tests/test_network.py`, `@pytest.mark.network`,
  excluded by default via `pyproject.toml` (`markers` + `addopts = -m "not network"`).
  Hits ~4 live feeds end-to-end (resolve → parse → enclosure URL sanity):
  xiaoyuzhou (忽左忽右), Ximalaya (声动早咖啡), SoundOn (股癌), Firstory (百靈果).
  Run manually with `pytest -m network`; not wired into CI in this iteration.

## Error handling summary

- Malformed XML: one sanitize-retry, then original `ParseError` propagates (cli
  already prints errors to stderr and exits non-zero).
- PI unavailable/misconfigured: stderr warning, feature degrades to iTunes-only.
- No credentials: PI code paths are dead — zero behavioral or network change.

## Release notes / docs to touch

- `CHANGELOG.md` v0.6.0; version bump in `__init__.py` + `pyproject.toml` (both).
- README: "Podcast Index (optional)" section — free key signup, env vars.
- `src/podpull/integrations/*`: one-line env-var note.
- No dependency changes → no Homebrew resource work.
