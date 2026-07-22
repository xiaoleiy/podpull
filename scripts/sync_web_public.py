#!/usr/bin/env python3
"""Sync canonical web sources into ./public/ for Vercel static hosting.

Sources of truth (edit these, not public/):
  docs/index.html              → public/index.html  (marketing landing)
  docs/icon.svg, favicons…     → public/
  src/podpull/serve/static/*   → public/app/ (+ root icons from static)

Run before deploy:  python3 scripts/sync_web_public.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DOCS = ROOT / "docs"
SERVE_STATIC = ROOT / "src" / "podpull" / "serve" / "static"


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  {src.relative_to(ROOT)} → {dst.relative_to(ROOT)}")


def main() -> int:
    if not (DOCS / "index.html").is_file():
        print("missing docs/index.html", file=sys.stderr)
        return 1
    if not (SERVE_STATIC / "index.html").is_file():
        print("missing serve/static/index.html", file=sys.stderr)
        return 1

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)

    print("syncing public/")
    _copy(DOCS / "index.html", PUBLIC / "index.html")

    for name in ("icon.svg", "favicon-32.png", "icon-256.png", "icon.png"):
        src = DOCS / name
        if src.is_file():
            _copy(src, PUBLIC / name)

    app_dir = PUBLIC / "app"
    app_dir.mkdir(parents=True)
    _copy(SERVE_STATIC / "index.html", app_dir / "index.html")

    # App page favicons resolve from site root (/icon.svg); also keep copies under /app.
    for name in ("icon.svg", "favicon-32.png"):
        src = SERVE_STATIC / name
        if not src.is_file():
            src = DOCS / name
        if src.is_file():
            _copy(src, app_dir / name)
            if not (PUBLIC / name).is_file():
                _copy(src, PUBLIC / name)

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
