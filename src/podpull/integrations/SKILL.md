---
name: podpull
description: Use when the user wants to download a podcast episode's audio file (mp3/m4a) to disk — from an Apple Podcasts show or episode link, a raw RSS feed, or a 小宇宙/xiaoyuzhou episode link. Covers searching for a show, listing episodes, and downloading one or many. Keywords: download podcast, save episode audio, Apple Podcasts, RSS, xiaoyuzhou, 小宇宙, mp3, m4a, podpull, 下载播客.
---

# podpull — download podcast episode audio

Use the installed **`podpull`** command-line tool to download podcast audio.
Repo: https://github.com/xiaoleiy/podpull

If it isn't installed: `brew install xiaoleiy/tap/podpull` (macOS/Linux) or
`pipx install git+https://github.com/xiaoleiy/podpull`.

## How it works (so you pick the right command)

Apple Podcasts holds no audio — it points at each show's RSS feed, where every
episode has a direct `<enclosure>` URL. podpull resolves Apple show URLs/IDs, raw
RSS feeds, and xiaoyuzhou links to that audio and downloads it.

## Commands

```
podpull search "<keywords>"                  # find shows -> Apple ID, #episodes, name
podpull info  <src>                          # show metadata (title, author, feed, latest)
podpull list  <src> [--match RE] [--all]     # list episodes; index 0 = newest
podpull get   <src> --match RE | --latest N | --index 0,2[,..]   # download (alias: `pull`)
podpull get   <episode-url>                  # download a pasted Apple ?i= or xiaoyuzhou link
podpull get   <src> ... -q / --quiet         # suppress spinner/progress bar

```

`<src>` = Apple show URL · bare Apple ID · RSS feed URL · Apple episode `?i=` URL · xiaoyuzhou episode URL.

## Workflow

1. Resolve the show: if you only have a name, `podpull search "<name>"`; then `podpull list <id>` to see episodes.
2. Download with a **selector** — `--match` (title regex), `--latest N`, or `--index 0,2`.
3. Report the saved path. The file path is printed to **stdout**; progress/UI go to **stderr**, so capture stdout when scripting.

## Important for agents (non-interactive)

- **Always pass a selector and `--no-input`.** Running `podpull get <show>` with *no* selector opens an
  interactive keyboard picker — which can't be driven non-interactively and will instead error with a hint.
  Use e.g. `podpull get 1532755821 --latest 1 --no-input`.
- **Add `-q`/`--quiet`** to suppress the spinner and live progress bar on stderr — recommended for
  agent transcripts, since neither renders meaningfully outside a live terminal. Saved file paths still
  print to stdout either way.
- Downloads default to `~/Downloads/Podcasts`; pass `--out DIR` to change.
- Selecting **multiple** episodes creates a per-show sub-folder. Filenames are normalized to be
  cloud-storage-safe (emoji/illegal characters removed; CJK kept).
- Optional: if PODCASTINDEX_API_KEY/PODCASTINDEX_API_SECRET are set, `search` also queries Podcast Index and feed resolution gains a fallback; ximalaya.com/album/<id> links work as a source.

## Examples

```
podpull search "睡前故事"
podpull get 1532755821 --latest 1 --no-input --quiet
podpull get 1532755821 --match "牛頭人" --no-input --out ~/Audio
podpull get "https://www.xiaoyuzhoufm.com/episode/<id>" --no-input
```
