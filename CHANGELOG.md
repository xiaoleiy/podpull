# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [0.1.0] — 2026-06-29

Initial public release. Core feature set, Python standard library only.

### Added
- `podget search <term>` — find shows via the iTunes Search API.
- `podget info <src>` — show metadata (title, author, Apple id, feed, episode count, latest).
- `podget list <src>` — list episodes, with `--match REGEX`, `--all`, `--limit`.
- `podget get <src>` — download episode audio, by `--match` / `--latest N` / `--index 0,2`.
- Direct episode links: xiaoyuzhou (`og:audio`) and Apple (`?i=`, matched in feed; `yt-dlp` fallback).
- Resumable, stdlib-only downloader; filenames as `YYYY-MM-DD - title.ext`.
