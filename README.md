# podget

Download a **specific podcast episode's audio** from the command line — given an
Apple Podcasts show, a raw RSS feed, or an episode link (Apple or
[xiaoyuzhou / 小宇宙](https://www.xiaoyuzhoufm.com)).

No login, no DRM, **no third-party dependencies** (Python standard library only).

## How it works

Apple Podcasts hosts **no audio** — it is a directory that points at each show's
RSS feed, and every episode in that feed carries a direct `<enclosure>` audio URL.
podget walks that chain:

```
Apple show URL/id ──(iTunes Lookup API)──▶ RSS feedUrl
RSS feed          ──(<enclosure url>)────▶ direct .mp3 / .m4a
download          ──(resumable)──────────▶ <YYYY-MM-DD> - <title>.<ext>
```

It also resolves a pasted **xiaoyuzhou** episode page (via its `og:audio` tag) and a
pasted **Apple episode** link (`…?i=<id>`, matched in the feed).

## Install

```bash
pipx install git+https://github.com/xiaoliy/podget        # recommended
# or
pip install git+https://github.com/xiaoliy/podget
```

Requires Python 3.9+. Optional: `yt-dlp` (deep-catalog Apple-episode fallback),
`ffmpeg`/`ffprobe` (verify downloads).

> **Note:** the name `podget` is taken on PyPI by an unrelated project, so this
> tool is installed from git, not `pip install podget`.

## Usage

```bash
podget search "睡前故事"                 # find shows -> id, #episodes, name, author
podget info  1532755821                  # show metadata (accepts URL, id, or RSS)
podget list  1532755821                  # recent episodes, numbered (0 = newest)
podget list  1532755821 --match "EP34"   # filter by title regex

# download (default output dir: ~/Downloads/Podcasts)
podget get 1532755821 --latest 1               # newest episode
podget get 1532755821 --match "牛頭人"          # by title regex
podget get 1532755821 --index 0,2,5            # browse-then-pick by number
podget get 1532755821 --match "EP34" --out ~/Audio/bedtime

# pasted episode links
podget get "https://www.xiaoyuzhoufm.com/episode/<id>"
podget get "https://podcasts.apple.com/.../id<show>?i=<track>"
```

`<src>` accepts: an Apple show URL, a bare Apple ID, a raw RSS feed URL, an Apple
episode URL (`?i=`), or a xiaoyuzhou episode URL.

## Roadmap

- **v0.1** (this release): search · info · list · download. Stdlib only.
- **v0.2+**: nicer output (tables/progress), more robust feed parsing, tests on
  more hosts, Podcast Index support.
- **v1+ (`podget[ai]`)**: opt-in **BYOK summarization** — local transcription
  (faster-whisper) + your own LLM key (Anthropic/OpenAI). Fully local, private,
  no subscription. Cleanly isolated from the core.

## Ethics & legal

podget reads the **public RSS feeds** that podcasters publish for exactly this
purpose, and downloads the enclosure files they distribute. Respect each show's
copyright and terms — download only what you're entitled to, for personal use.

## License

MIT © xiaoleiyu
