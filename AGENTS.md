# AGENTS.md

**The full agent guide for this repository is [`CLAUDE.md`](./CLAUDE.md) — read it first.**
It covers the architecture, dev workflow, testing, the release process, and the invariants
below in detail. This file is a short pointer for agents that look for `AGENTS.md`.

## podpull in one line

A stdlib-core Python CLI that downloads a specific podcast episode's audio from Apple Podcasts,
an RSS feed, or a xiaoyuzhou (小宇宙) link. Python ≥ 3.9. Official hosted UI:
https://podpull.xiaolei.work (see `docs/HOSTING.md`).

## The must-know invariants (details in CLAUDE.md)

1. **`src/podpull/core.py` is dependency-free** (stdlib only). All third-party deps
   (`rich`, `questionary`, `rich-argparse`) belong in `cli.py`. Use callbacks, not imports, to
   surface UI concerns from core.
2. **stdout = file paths, stderr = all UI.** Don't mix them.
3. **`podpull get <show>`** opens the interactive picker only on a TTY without `--no-input`;
   otherwise it lists + exits non-zero. Never hang in non-interactive contexts.
4. **Filenames** go through `core.safe_filename` (cloud-/Windows-safe). Text I/O is always
   `encoding="utf-8"`. `core.UA` is a browser User-Agent on purpose (xiaoyuzhou 403s tool UAs).
5. If you change CLI commands/flags, **update the bundled agent instructions** in
   `src/podpull/integrations/` too.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q          # offline; keep green on macOS/Linux/Windows
```

## Releasing

Bump the version in **both** `src/podpull/__init__.py` and `pyproject.toml`, update
`CHANGELOG.md`, then `git tag vX.Y.Z && git push origin main --tags` — this auto-publishes to
PyPI and bumps the Homebrew tap. See [`CLAUDE.md`](./CLAUDE.md) for the dependency-change caveat.
