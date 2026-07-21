# `--json` Output Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global `podpull --json` flag that emits one JSON document on stdout for `search` / `info` / `list` / `get`, suppressing rich UI — shipping as v0.7.0.

**Architecture:** All changes in `cli.py` (helpers `_emit_json`, `_show_dict`, `_episode_dict`, `_is_quiet`; branch at end of each `cmd_*`). Root argparse `--json`. `core.py` untouched. Offline CLI tests in `tests/test_cli.py`.

**Tech Stack:** Python ≥3.9 stdlib `json`; existing `rich` / `questionary` (suppressed when `--json`); pytest.

**Spec:** `docs/superpowers/specs/2026-07-21-json-output-design.md` (approved 2026-07-21)

## Global Constraints

- `core.py` stays pure stdlib — no serializers added there for v0.7.
- stdout = one JSON document (+ newline) on success under `--json`; stderr = humans / errors only.
- Failures: human `_err` on stderr, non-zero exit, **no** JSON on stdout.
- `--json` implies quiet (no spinner/progress/picker). Root flag only: `podpull --json <cmd> …`.
- `get` without selector under `--json` → exit 1 + stderr hint (no list dump, no picker).
- Version bump in **both** `__init__.py` and `pyproject.toml` → `0.7.0`.
- Default test suite must never touch the network.
- Update integrations + README + CHANGELOG + Obsidian Follow-ups checkbox when shipping.

---

### Task 1: Failing CLI tests for `--json`

**Files:**
- Modify: `tests/test_cli.py`
- Test: same

**Interfaces:**
- Consumes: `cli.cmd_*`, `cli.main` / `cli.build_parser`, mocked `core`
- Produces: failing tests that define expected JSON shapes

- [ ] **Step 1: Add helper + tests** (append to `tests/test_cli.py`)

```python
import json

def _ns(**kw):
    """Namespace with defaults matching build_parser defaults for missing keys."""
    base = dict(json=False, quiet=False, no_input=False, match=None, latest=None,
                index=None, all=False, limit=40, country="US", term="故事")
    base.update(kw)
    return argparse.Namespace(**base)

def test_json_search(monkeypatch, capsys):
    monkeypatch.setattr(core, "pi_credentials", lambda: None)
    monkeypatch.setattr(core, "search_shows", lambda term, limit, country: [
        {"collectionId": 1, "collectionName": "A", "artistName": "x",
         "feedUrl": "https://f/a", "trackCount": 3}])
    buf = io.StringIO()
    monkeypatch.setattr(cli, "ui", Console(file=buf, stderr=True))
    rc = cli.cmd_search(_ns(term="故事", json=True, limit=10))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"query": "故事", "results": [
        {"apple_id": "1", "title": "A", "author": "x",
         "episode_count": 3, "feed_url": "https://f/a"}]}
    assert "Podcasts matching" not in buf.getvalue()

def test_json_info(monkeypatch, capsys):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    buf = io.StringIO()
    monkeypatch.setattr(cli, "ui", Console(file=buf, stderr=True))
    rc = cli.cmd_info(_ns(src="123", json=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["title"] == "Demo Show"
    assert out["episode_count"] == 3
    assert out["latest"]["index"] == 0
    assert out["latest"]["title"] == "EP0"
    assert out["latest"]["url"] == "u0"
    assert buf.getvalue() == ""

def test_json_list_limit(monkeypatch, capsys):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    rc = cli.cmd_list(_ns(src="123", json=True, limit=2, match=None, all=False))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["episodes"]) == 2
    assert out["episodes"][0]["index"] == 0
    assert out["episodes"][1]["title"] == "EP1"

def test_json_get_emits_downloads(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    got = _record_downloads(monkeypatch)
    buf = io.StringIO()
    monkeypatch.setattr(cli, "ui", Console(file=buf, stderr=True))
    rc = cli.cmd_get(_ns(src="123", latest=1, out=str(tmp_path), json=True))
    assert rc == 0
    assert got == ["EP0"]
    out = json.loads(capsys.readouterr().out)
    assert out["show"]["title"] == "Demo Show"
    assert len(out["downloads"]) == 1
    assert out["downloads"][0]["title"] == "EP0"
    assert out["downloads"][0]["path"].endswith("EP0.mp3")
    assert buf.getvalue() == ""

def test_json_get_no_selector_exits(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    got = _record_downloads(monkeypatch)
    rc = cli.cmd_get(_ns(src="123", out=str(tmp_path), json=True))
    assert rc == 1
    assert got == []
    raw = capsys.readouterr().out.strip()
    assert raw == "" or not raw.startswith("{")

def test_parser_accepts_root_json():
    args = cli.build_parser().parse_args(["--json", "search", "foo"])
    assert args.json is True
    assert args.term == "foo"
```

Also update existing `cmd_get` Namespace constructions to include `json=False` **or** ensure production code uses `getattr(args, "json", False)` so old tests keep working — prefer `getattr` so Task 1 only adds new tests.

- [ ] **Step 2: Run tests — expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k json -v`
Expected: FAIL (no `--json` / no JSON emit yet)

- [ ] **Step 3: Commit tests**

```bash
git add tests/test_cli.py
git commit -m "test: add failing coverage for --json output mode"
```

---

### Task 2: Implement `--json` in `cli.py`

**Files:**
- Modify: `src/podpull/cli.py`

**Interfaces:**
- Produces: `_is_quiet(args) -> bool`, `_emit_json(obj) -> None`, `_show_dict(show) -> dict`, `_episode_dict(ep, index=None) -> dict`; root `--json`; JSON branches in `cmd_search` / `cmd_info` / `cmd_list` / `cmd_get` / `_download_all`

- [ ] **Step 1: Add helpers + root flag + command branches** (per spec schemas)

Key behaviors:
- `_is_quiet(args)` = `getattr(args, "quiet", False) or getattr(args, "json", False)`
- Replace `args.quiet` checks that mean "suppress UI" with `_is_quiet(args)` (picker, spinner, progress, download banner). Keep printing bare paths only when **not** json; when json, `_download_all` returns `(n, records)`.
- `cmd_search`: skip status spinner when json; build results list; `_emit_json` instead of table.
- `cmd_info` / `cmd_list`: emit JSON when set.
- `cmd_get`: if json and no selector → `_err(...)` exit 1 (do **not** call `cmd_list`). After downloads, if json and n>0 emit document; if n==0 exit 1 with no JSON.
- Root: `p.add_argument("--json", action="store_true", help="emit machine-readable JSON on stdout (no UI)")`
- `episode_count`: int if `trackCount` is int-like else `null`
- `apple_id`: `str(collectionId)` if present else `""`

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`
Expected: all pass (including new json tests; existing quiet tests still pass)

- [ ] **Step 3: Commit**

```bash
git add src/podpull/cli.py
git commit -m "feat: add global --json output for search/info/list/get"
```

---

### Task 3: Docs, integrations, version bump to 0.7.0

**Files:**
- Modify: `src/podpull/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md`
- Modify: `src/podpull/integrations/SKILL.md`, `opencode_command.md`, `cursor_rule.mdc`
- Modify: Obsidian `Projects/Podpull/跟进 Follow-ups.md` (check off `--json`)

- [ ] **Step 1: Bump version to 0.7.0 in both version files; CHANGELOG entry; README roadmap + example; integrations mention `podpull --json …`**

- [ ] **Step 2: Run full suite + ruff**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src`
Expected: green

- [ ] **Step 3: Commit**

```bash
git add -u src/podpull/__init__.py pyproject.toml CHANGELOG.md README.md src/podpull/integrations/
git commit -m "docs: v0.7.0 — document --json output mode"
```

(Obsidian vault path is outside the repo — edit Follow-ups separately, no git commit there unless vault is tracked.)

---

## Spec coverage checklist

| Spec requirement | Task |
|---|---|
| Global `--json` root flag | 2 |
| search/info/list/get schemas | 1+2 |
| Suppress UI; errors stderr only | 2 |
| get no-selector → exit 1, no JSON | 1+2 |
| get emits downloads array; n==0 no JSON | 2 |
| skills unchanged | — |
| Integrations + README + CHANGELOG | 3 |
| Offline tests | 1 |
| core.py untouched | — |

## Out of scope (do not implement)

NDJSON, JSON errors, `skills --json`, schema version, `serve`, BYOK summarization.
