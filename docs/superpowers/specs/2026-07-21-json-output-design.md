# Design: `--json` output mode for scripting

Date: 2026-07-21 · Target release: **v0.7.0** · Status: approved (awaiting final spec review)

Backlog source: Obsidian `Projects/Podpull/跟进 Follow-ups.md` → "later hardening"
(`--json` output mode); README roadmap → **next**. Explicitly out of scope for
v0.6.0 (see `2026-07-07-feed-robustness-podcastindex-design.md`).

Sequencing (user): **A `--json` → B `podpull serve` → C BYOK summarization**.
This spec covers **A only**.

## Decisions (locked 2026-07-21)

1. **Global `--json`** on the root parser (`podpull --json <cmd> …`), applying to
   every command that emits structured data: `search`, `info`, `list`, `get`/`pull`.
   Not `skills` (no useful structured payload).
2. **One JSON document per successful command** on stdout (not NDJSON). Easy for
   `jq` and agents; lists are already capped; `get` emits one array after all
   downloads finish.
3. **Suppress all rich UI** when `--json` is set (spinners, tables, progress bars,
   path-line chatter). Failures stay human text on **stderr** + non-zero exit —
   **no** JSON error object. Same spirit as `--quiet`.
4. **Implementation lives in `cli.py`** — each `cmd_*` builds a plain `dict` and
   `json.dumps` to stdout. No new module; no serializers in `core.py` yet (YAGNI;
   `serve` can copy or extract later).
5. **`--json` implies non-interactive** for `get`: without a selector, behave like
   non-TTY / `--no-input` (list+hint on stderr, exit 1) — never open the picker.

## Invariants preserved

- `core.py` stays dependency-free (stdlib only). `json` is already used in core
  for HTTP; CLI may `import json` for dumping.
- **stdout = machine output, stderr = humans.** With `--json`, stdout is exactly
  one JSON document (plus trailing newline); stderr may still carry failure
  messages.
- Cloud-/Windows-safe filenames unchanged; download paths in JSON are the real
  filesystem paths returned by `download_episode`.

## Flag wiring

```
podpull [--json] <command> …
```

- Add `p.add_argument("--json", action="store_true", …)` on the **root** parser
  in `build_parser()`.
- Thread via `args.json` (default `False` when absent — skills / bare help
  unaffected).
- `get --quiet` + `--json` is allowed and redundant; `--json` alone is enough to
  silence UI. Prefer treating `args.json` as implying quiet inside `cmd_get` /
  `_download_all` rather than mutating `args.quiet`.

Argparse note: root flags must appear **before** the subcommand
(`podpull --json search "…"`). Document this in help/epilog and integrations.
Do **not** duplicate `--json` on every subparser unless we later add a shared
parent parser — keep one place for v0.7.

## Behavior by command

### Success path

| Command | stdout | stderr UI |
|---|---|---|
| `search` | JSON document | silent (no table/hints) |
| `info` | JSON document | silent |
| `list` | JSON document | silent |
| `get` / `pull` | JSON document | silent (no spinner/bar/✓ lines; no bare path prints) |

### Failure path (any command)

- Human message via existing `_err(...)` on stderr.
- Non-zero exit code unchanged.
- **No** JSON on stdout (empty or partial stdout is fine; callers must not parse
  on non-zero).

### `get` without selector under `--json`

Same as non-interactive today: print a short list/hint to stderr (or skip the
rich table and print a one-line hint — prefer reusing `cmd_list` only if it
respects `--json`; simpler: `_err("… pass --match / --latest / --index")` and
exit 1 without dumping a list JSON). Never hang on questionary.

Recommendation: under `--json` + no selector → exit 1 with stderr hint only
(no list dump). Scripts must pass an explicit selector. (Listing is available via
`podpull --json list <src>`.)

## Schemas

Omit null/empty optional fields only where noted; otherwise use `""` / `null`
consistently — **prefer empty string for missing strings, `null` for missing
nested objects**, integers always present.

### `search`

```json
{
  "query": "睡前故事",
  "results": [
    {
      "apple_id": "1532755821",
      "title": "我們家的睡前故事",
      "author": "…",
      "episode_count": 394,
      "feed_url": "https://…"
    }
  ]
}
```

- `apple_id`: string (iTunes `collectionId`), or `""` if absent (PI-only hits).
- `episode_count`: int when known, else `null`.
- `feed_url`: string, may be `""`.
- Search warnings (iTunes/PI partial failure) still go to stderr; results JSON
  is emitted if `results` is non-empty.

### `info`

```json
{
  "title": "…",
  "author": "…",
  "apple_id": "1532755821",
  "feed": "https://…",
  "episode_count": 394,
  "latest": {
    "index": 0,
    "date": "2026-07-01",
    "title": "…",
    "url": "https://…"
  }
}
```

- `latest` is `null` when the show has no episodes.
- `apple_id` may be `""` for pure RSS inputs.

### `list`

```json
{
  "show": {
    "title": "…",
    "author": "…",
    "apple_id": "…",
    "feed": "https://…"
  },
  "episodes": [
    {
      "index": 0,
      "date": "2026-07-01",
      "title": "…",
      "url": "https://…"
    }
  ]
}
```

- `index` matches the `#` column / `--index` semantics (0 = newest in the
  filtered view as today).
- Respect existing `--match` / `--all` / `--limit` filtering before building
  `episodes`.

### `get` / `pull`

```json
{
  "show": {
    "title": "…",
    "feed": "https://…"
  },
  "downloads": [
    {
      "date": "2026-07-01",
      "title": "…",
      "url": "https://…",
      "path": "/Users/…/Downloads/Podcasts/2026-07-01 - ….mp3"
    }
  ]
}
```

- Emit **after** all selected downloads finish (including partial success: only
  successful paths appear in `downloads`; per-file failures still print to
  stderr as today, and exit code stays `0` if at least one succeeded / `1` if
  none — match current `_download_all` semantics).
- Pasted episode links (`xyz_episode` / `apple_episode`): `show.title` may be
  `""` or a best-effort title; `show.feed` may be `""`; `downloads` has one
  entry when successful.
- `path` is the absolute or as-returned path string from `download_episode`
  (do not rewrite).

No schema version field in v0.7 (YAGNI).

## Implementation sketch (`cli.py`)

- `import json` at module top.
- Helper `_emit_json(obj) -> None`: `print(json.dumps(obj, ensure_ascii=False, indent=2))`
  to stdout. **Always `indent=2`** (readable for agents/humans; list sizes are capped).
- Helpers `_episode_dict(ep, index=…)` / `_show_dict(show)` as private functions
  in `cli.py` to avoid drift between `info`/`list`/`get`.
- Branch at the end of each `cmd_*`: if `getattr(args, "json", False): _emit_json(…); return …`
  else existing table/path path.
- `_download_all(..., *, as_json=False)`: when `as_json`, collect successful
  records instead of `print(path)`; return `(n, records)`. Caller emits the
  document only when `n > 0` (on `n == 0`, exit 1 with stderr only — no empty
  JSON success document).

## Docs & integrations

When shipping:

- README: show `podpull --json list … | jq …` example; mark roadmap item done;
  bump version notes toward 0.7.0.
- CHANGELOG `[0.7.0]`.
- Update bundled agent files under `src/podpull/integrations/` (SKILL.md,
  opencode command, Cursor rule) so agents pass `--json` when scripting.
- Obsidian Follow-ups: check off `--json`.

## Tests (offline)

Extend `tests/test_cli.py` with mocked `core`:

1. `podpull --json search X` → stdout parses; has `query` + `results`; stderr has
   no table title.
2. `podpull --json info <src>` → keys as above; `latest` null when empty eps.
3. `podpull --json list <src> --limit 2` → `episodes` length 2; indices 0..1.
4. `podpull --json get <src> --latest 1` → `downloads[0].path` set; no bare path
   line outside JSON; quiet UI.
5. `podpull --json get <src>` (no selector) → exit 1; no JSON object on stdout.
6. Failure (e.g. classify error) → non-zero; stdout not a JSON object (or empty).

No network in default suite.

## Out of scope

- NDJSON / streaming JSON.
- JSON-formatted errors.
- `--json` on `skills`.
- Schema `$schema` / version field.
- Placing `--json` after the subcommand (`podpull search --json`) — not required
  for v0.7; root-only.
- `podpull serve` (B) and BYOK summarization (C).

## Success criteria

- `pytest -q` green.
- Manual: `podpull --json list <known-id> | jq .episodes[0].title` works.
- Without `--json`, human UI byte-identical to v0.6.0 behavior.
