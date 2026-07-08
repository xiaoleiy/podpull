---
description: Download a podcast episode's audio with podpull (Apple Podcasts / RSS / xiaoyuzhou)
---

The user wants to download podcast audio using the `podpull` CLI. Their request: $ARGUMENTS

Use the installed **`podpull`** tool (install: `brew install xiaoleiy/tap/podpull` or
`pipx install git+https://github.com/xiaoleiy/podpull`). It resolves Apple Podcasts
show URLs/IDs, raw RSS feeds, and xiaoyuzhou (小宇宙) links to direct audio and downloads it.

Commands:
- `podpull search "<keywords>"` — find a show (returns Apple ID, episode count).
- `podpull list <src> [--match RE]` — list episodes; index 0 = newest.
- `podpull get <src> --match RE | --latest N | --index 0,2` — download (alias: `pull`).
- `podpull get <episode-url>` — download a pasted Apple `?i=` or xiaoyuzhou link.
- `podpull get <src> ... -q/--quiet` — suppress spinner/progress bar output.

Rules:
- ALWAYS pass a selector (`--match` / `--latest` / `--index`) **and `--no-input`** — never run a bare
  `podpull get <show>`, which opens an interactive picker you can't drive here.
- ALSO pass `-q`/`--quiet` — it suppresses the spinner and live progress bar, which don't render
  meaningfully outside a live terminal anyway. The saved file path still prints to stdout regardless.
- The saved file path is printed to stdout; progress to stderr. Default output dir is `~/Downloads/Podcasts`
  (`--out DIR` to change). Multiple episodes go into a per-show folder; filenames are cloud-safe.
- Optional: if PODCASTINDEX_API_KEY/PODCASTINDEX_API_SECRET are set, `search` also queries Podcast Index and feed resolution gains a fallback; ximalaya.com/album/<id> links work as a source.

Steps: figure out the show (search/list if needed), then download with the right selector, then report the saved path(s).
