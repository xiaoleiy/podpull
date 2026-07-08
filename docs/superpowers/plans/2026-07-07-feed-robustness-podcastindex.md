# Feed Robustness + Podcast Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `core.parse_feed` survive real-world feeds (CN + global hosts, Atom/RDF, dirty XML), add optional BYOK Podcast Index search/resolution, and back it all with offline fixtures — shipping as v0.6.0.

**Architecture:** All logic changes live in `src/podpull/core.py` (pure stdlib — CLAUDE.md invariant #1); the only `cli.py` change is `cmd_search` merging Podcast Index results. Tests are offline fixtures under `tests/fixtures/feeds/` driven by one parametrized case table; live-network checks go in a `network`-marked module excluded by default.

**Tech Stack:** Python ≥3.9 stdlib (`xml.etree`, `html.entities`, `hashlib`, `urllib`); pytest; no new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-07-07-feed-robustness-podcastindex-design.md` (approved 2026-07-07)

**Working branch:** `feed-robustness-podcastindex` (already exists; all commits go here)

**Conventions the engineer must know (from CLAUDE.md):**
- `core.py` may import ONLY the standard library. UI/rich stays in `cli.py`.
- stdout is machine output; all human messages go to stderr (`cli.ui` / `_err`).
- Default test suite must never touch the network.
- Run everything from the repo root with the venv: `. .venv/bin/activate` (or use `python3 -m pytest`). Full suite: `pytest -q`; lint: `ruff check src`.
- Version lives in BOTH `src/podpull/__init__.py` and `pyproject.toml`.

---

### Task 1: pytest `network` marker configuration

**Files:**
- Modify: `pyproject.toml` (add `[tool.pytest.ini_options]` at end of file)

- [ ] **Step 1: Add pytest config**

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "network: hits live podcast hosts; excluded by default (run: pytest -m network)",
]
addopts = "-m 'not network'"
```

- [ ] **Step 2: Verify the suite still passes and the marker is honored**

Run: `pytest -q`
Expected: all existing tests pass (24 passed at time of writing; count may differ after PR #3 merges), `no tests ran` is a FAILURE.

Run: `pytest -q -m network`
Expected: `no tests ran` / all deselected (no network tests exist yet — that's fine).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "test: add network marker, excluded by default"
```

---

### Task 2: `Episode.date` ISO-8601 fallback

**Files:**
- Modify: `src/podpull/core.py` (imports + `Episode.date`, currently lines 15–43)
- Test: `tests/test_core.py` (extend `test_episode_date`)

- [ ] **Step 1: Write the failing test**

In `tests/test_core.py`, replace `test_episode_date` with:

```python
def test_episode_date():
    assert _eps()[0].date == "2026-06-27"
    assert Episode(title="x", pub="garbage", url="u").date == "0000-00-00"
    # RFC-822 with non-zero-padded day (Lizhi) — parsedate handles it
    assert Episode(title="x", pub="Sun, 5 Jul 2026 21:00:00 +0800", url="u").date == "2026-07-05"
    # ISO-8601 (Atom published / dc:date), with and without Z
    assert Episode(title="x", pub="2026-07-01T08:30:00Z", url="u").date == "2026-07-01"
    assert Episode(title="x", pub="2026-07-01T08:30:00+08:00", url="u").date == "2026-07-01"
    assert Episode(title="x", pub="", url="u").date == "0000-00-00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py::test_episode_date -v`
Expected: FAIL — the ISO strings return `"0000-00-00"`.

- [ ] **Step 3: Implement**

In `src/podpull/core.py`, add to imports (after `from email.utils import parsedate_to_datetime`):

```python
from datetime import datetime
```

Replace the `date` property of `Episode`:

```python
    @property
    def date(self) -> str:
        for parse in (
            lambda s: parsedate_to_datetime(s),                                   # RFC-822
            lambda s: datetime.fromisoformat(s.strip().replace("Z", "+00:00")),   # ISO-8601
        ):
            try:
                return parse(self.pub).strftime("%Y-%m-%d")
            except Exception:
                continue
        return "0000-00-00"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_core.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/podpull/core.py tests/test_core.py
git commit -m "feat: parse ISO-8601 pub dates (Atom/dc:date) in Episode.date"
```

---

### Task 3: namespace-agnostic feed parsing (RSS 2.0 / RSS 1.0 RDF / Atom)

**Files:**
- Modify: `src/podpull/core.py` — replace `parse_feed` (currently lines 114–139) with helpers + new implementation
- Create: `tests/fixtures/feeds/rss2_plain.xml`, `tests/fixtures/feeds/rss10_rdf.xml`, `tests/fixtures/feeds/atom.xml`
- Test: `tests/test_core.py` — add fixture harness + parametrized test

- [ ] **Step 1: Create three fixture files**

`tests/fixtures/feeds/rss2_plain.xml` (regression: today's happy path — itunes author, enclosure):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Plain RSS2 Show</title>
    <itunes:author>Plain Author</itunes:author>
    <item>
      <title>EP2</title>
      <pubDate>Fri, 03 Jul 2026 08:00:00 GMT</pubDate>
      <guid>plain-ep2</guid>
      <link>https://example.test/ep2</link>
      <enclosure url="https://cdn.example.test/ep2.mp3" type="audio/mpeg" length="1"/>
    </item>
    <item>
      <title>EP1</title>
      <pubDate>Wed, 01 Jul 2026 08:00:00 GMT</pubDate>
      <guid>plain-ep1</guid>
      <enclosure url="https://cdn.example.test/ep1.mp3" type="audio/mpeg" length="1"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/rss10_rdf.xml` (RSS 1.0: default namespace on every element, items OUTSIDE channel — today's parser finds zero items because `.//item` misses namespaced tags):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns="http://purl.org/rss/1.0/"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel rdf:about="https://example.test/">
    <title>RDF Show</title>
    <dc:creator>RDF Author</dc:creator>
  </channel>
  <item rdf:about="https://example.test/1">
    <title>RDF EP1</title>
    <dc:date>2026-06-30T10:00:00Z</dc:date>
    <enclosure url="https://cdn.example.test/rdf1.mp3" type="audio/mpeg"/>
  </item>
</rdf:RDF>
```

`tests/fixtures/feeds/atom.xml` (Atom: `feed`/`entry`, `link rel="enclosure"`, `author/name`, ISO dates):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Show</title>
  <author><name>Atom Author</name></author>
  <entry>
    <title>Atom EP1</title>
    <id>atom-ep1</id>
    <published>2026-07-01T08:30:00Z</published>
    <link rel="alternate" href="https://example.test/atom1"/>
    <link rel="enclosure" href="https://cdn.example.test/atom1.mp3" type="audio/mpeg"/>
  </entry>
</feed>
```

- [ ] **Step 2: Add the fixture harness + failing parametrized test**

In `tests/test_core.py`, add after the imports:

```python
import io
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "feeds"

# (fixture, show_title, show_author, n_episodes, first_url, first_date)
FEED_CASES = [
    ("rss2_plain.xml", "Plain RSS2 Show", "Plain Author", 2,
     "https://cdn.example.test/ep2.mp3", "2026-07-03"),
    ("rss10_rdf.xml", "RDF Show", "RDF Author", 1,
     "https://cdn.example.test/rdf1.mp3", "2026-06-30"),
    ("atom.xml", "Atom Show", "Atom Author", 1,
     "https://cdn.example.test/atom1.mp3", "2026-07-01"),
]


def _parse_fixture(monkeypatch, fname):
    raw = (FIXTURES / fname).read_bytes()
    monkeypatch.setattr(core, "fetch", lambda url, timeout=45: io.BytesIO(raw))
    return core.parse_feed("https://example.test/feed")


@pytest.mark.parametrize("fname,title,author,count,first_url,first_date", FEED_CASES)
def test_parse_feed_fixture(monkeypatch, fname, title, author, count, first_url, first_date):
    t, a, eps = _parse_fixture(monkeypatch, fname)
    assert t == title
    assert a == author
    assert len(eps) == count
    assert eps[0].url == first_url
    assert eps[0].date == first_date
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_core.py::test_parse_feed_fixture -v`
Expected: `rss2_plain.xml` PASSES (regression guard); `rss10_rdf.xml` and `atom.xml` FAIL (0 episodes / empty title).

- [ ] **Step 4: Implement**

In `src/podpull/core.py`, replace the whole `parse_feed` function (keep its position in the file) with:

```python
def _localname(tag) -> str:
    """'{ns}Tag' -> 'tag'. Comments/PIs have non-str tags -> ''."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _clean(text) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _first_text(el, *names) -> str:
    """First non-empty direct-child text whose localname is in names."""
    wanted = {n.lower() for n in names}
    for child in el:
        if _localname(child.tag) in wanted and _clean(child.text):
            return _clean(child.text)
    return ""


def _author(el) -> str:
    """itunes:author / atom author>name -> managingEditor -> dc:creator."""
    for name in ("author", "managingeditor", "creator"):
        for child in el:
            if _localname(child.tag) == name:
                txt = _first_text(child, "name") or _clean(child.text)
                if txt:
                    return txt
    return ""


def _pub(item) -> str:
    """pubDate -> dc:date -> atom published -> atom updated (raw string)."""
    for name in ("pubdate", "date", "published", "updated"):
        for child in item:
            if _localname(child.tag) == name and _clean(child.text):
                return child.text.strip()
    return ""


def _find_enclosure(item) -> tuple[str, str]:
    """-> (audio_url, mime) or ('', ''). Priority: enclosure > media:content
    (audio) > atom link rel=enclosure. First match wins — WavPub/Omny items
    carry BOTH enclosure and media:content; one item must yield one URL."""
    for child in item:
        if _localname(child.tag) == "enclosure" and child.get("url"):
            return child.get("url"), child.get("type") or ""
    for child in item:
        if _localname(child.tag) == "content" and child.get("url"):
            mime = child.get("type") or ""
            if mime.startswith("audio/") or child.get("medium") == "audio":
                return child.get("url"), mime
    for child in item:
        if (_localname(child.tag) == "link" and child.get("rel") == "enclosure"
                and child.get("href")):
            return child.get("href"), child.get("type") or ""
    return "", ""


def _item_link(item) -> str:
    link = _first_text(item, "link")
    if link:
        return link
    for child in item:  # atom: <link href=…/> with no/alternate rel
        if (_localname(child.tag) == "link" and child.get("href")
                and child.get("rel") in (None, "alternate")):
            return child.get("href")
    return ""


def parse_feed(feed_url: str) -> tuple[str, str, list[Episode]]:
    """-> (show_title, show_author, episodes). Handles RSS 2.0, RSS 1.0 (RDF)
    and Atom, with any namespace layout (matching by localname)."""
    root = ET.fromstring(fetch(feed_url).read())
    chan = next((el for el in root.iter()
                 if _localname(el.tag) in ("channel", "feed")), root)
    eps: list[Episode] = []
    for it in root.iter():
        if _localname(it.tag) not in ("item", "entry"):
            continue
        url, mime = _find_enclosure(it)
        if not url:
            continue
        eps.append(Episode(
            title=_first_text(it, "title"),
            pub=_pub(it),
            url=url,
            mime=mime,
            guid=_first_text(it, "guid", "id"),
            link=_item_link(it),
        ))
    return _first_text(chan, "title"), _author(chan), eps
```

Note: the old `itunes = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"` constant inside `parse_feed` disappears — `_author`'s localname matching covers both `http://` and `https://` itunes namespace variants for free.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_core.py -q`
Expected: PASS (all, including all three fixture rows).

- [ ] **Step 6: Commit**

```bash
git add src/podpull/core.py tests/test_core.py tests/fixtures/feeds/
git commit -m "feat: namespace-agnostic feed parsing — RSS 2.0, RSS 1.0/RDF, Atom"
```

---

### Task 4: enclosure fallbacks + duplicate dedupe

**Files:**
- Create: `tests/fixtures/feeds/media_content_only.xml`, `tests/fixtures/feeds/wavpub.xml`, `tests/fixtures/feeds/omny.xml`
- Test: `tests/test_core.py` (extend `FEED_CASES`)

The implementation already landed in Task 3 (`_find_enclosure`); this task pins its behavior with fixtures. If any row fails, fix `_find_enclosure`, not the fixture.

- [ ] **Step 1: Create fixtures**

`tests/fixtures/feeds/media_content_only.xml` (MRSS only, no `<enclosure>` — today's parser yields zero episodes; also one non-audio `media:content` that must be skipped):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>MRSS Show</title>
    <managingEditor>editor@example.test (MRSS Author)</managingEditor>
    <item>
      <title>MRSS EP1</title>
      <pubDate>Thu, 02 Jul 2026 08:00:00 GMT</pubDate>
      <media:content url="https://cdn.example.test/cover.jpg" type="image/jpeg"/>
      <media:content url="https://cdn.example.test/mrss1.mp3" type="audio/mpeg"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/wavpub.xml` (半拿铁-shaped: duplicate `enclosure` + `media:content` per item — must yield ONE episode with the `enclosure` URL; note enclosure and media URLs differ so the test catches wrong-priority bugs):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:media="http://search.yahoo.com/mrss/" xmlns:wavpub="https://wavpub.com/rss">
  <channel>
    <title>半拿铁 | 商业沉浮录</title>
    <itunes:author>潇磊布道</itunes:author>
    <item>
      <title><![CDATA[91. 蜜雪冰城：贫穷限制了它的想象]]></title>
      <pubDate>Wed, 01 Jul 2026 22:00:00 +0800</pubDate>
      <guid>wavpub-91</guid>
      <enclosure url="https://tk.wavpub.com/track/caffebreve/91.m4a" type="audio/x-m4a" length="2"/>
      <media:content url="https://tk.wavpub.com/media/caffebreve/91.m4a" type="audio/x-m4a"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/omny.xml` (Omny-shaped: enclosure + TWO `media:content` per item):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>馬力歐陪你喝一杯</title>
    <itunes:author>鏡好聽</itunes:author>
    <item>
      <title>EP388 對談</title>
      <pubDate>Tue, 30 Jun 2026 20:00:00 +0800</pubDate>
      <enclosure url="https://omny.example.test/ep388.mp3" type="audio/mpeg" length="3"/>
      <media:content url="https://omny.example.test/ep388.mp3" type="audio/mpeg"/>
      <media:content url="https://omny.example.test/ep388.jpg" type="image/jpeg"/>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Add the (partly failing) case rows**

Append to `FEED_CASES` in `tests/test_core.py`:

```python
    ("media_content_only.xml", "MRSS Show", "editor@example.test (MRSS Author)", 1,
     "https://cdn.example.test/mrss1.mp3", "2026-07-02"),
    ("wavpub.xml", "半拿铁 | 商业沉浮录", "潇磊布道", 1,
     "https://tk.wavpub.com/track/caffebreve/91.m4a", "2026-07-01"),
    ("omny.xml", "馬力歐陪你喝一杯", "鏡好聽", 1,
     "https://omny.example.test/ep388.mp3", "2026-06-30"),
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_core.py::test_parse_feed_fixture -v`
Expected: PASS for all rows (Task 3's `_find_enclosure` already implements the behavior; treat any failure as an implementation bug to fix in `core.py`).

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: enclosure fallback + duplicate media:content dedupe fixtures"
```

---

### Task 5: dirty-XML recovery (`_sanitize_xml`)

**Files:**
- Modify: `src/podpull/core.py` (imports; new `_parse_xml` + `_sanitize_xml`; `parse_feed` first line)
- Create: `tests/fixtures/feeds/dirty_entities.xml`, `tests/fixtures/feeds/utf16_bom.xml`
- Test: `tests/test_core.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/feeds/dirty_entities.xml` — undefined HTML entity, bare `&`, control char, leading blank line. **Write this file exactly as shown** (the blank first line and the literal `&nbsp;` / bare `&` are the point; the `\x0b` control char is written via the printf command below since editors strip it):

```xml

<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Dirty&nbsp;Show</title>
    <managingEditor>Dirty & Sons</managingEditor>
    <item>
      <title>EP1 A &amp; B</title>
      <pubDate>Mon, 29 Jun 2026 08:00:00 GMT</pubDate>
      <enclosure url="https://cdn.example.test/dirty1.mp3?a=1&b=2" type="audio/mpeg"/>
    </item>
  </channel>
</rss>
```

Then inject a control character into the title (after writing the file):

```bash
python3 - <<'EOF'
from pathlib import Path
p = Path("tests/fixtures/feeds/dirty_entities.xml")
p.write_bytes(p.read_bytes().replace(b"Dirty&nbsp;Show", b"Dirty&nbsp;\x0bShow"))
EOF
```

`tests/fixtures/feeds/utf16_bom.xml` — UTF-16 with BOM. Generate it (don't hand-write):

```bash
python3 - <<'EOF'
from pathlib import Path
xml = '''<?xml version="1.0" encoding="UTF-16"?>
<rss version="2.0"><channel><title>UTF16 Show</title>
<item><title>U16 EP1</title><pubDate>Sun, 28 Jun 2026 08:00:00 GMT</pubDate>
<enclosure url="https://cdn.example.test/u16.mp3" type="audio/mpeg"/></item>
</channel></rss>'''
Path("tests/fixtures/feeds/utf16_bom.xml").write_bytes(b"\xff\xfe" + xml.encode("utf-16-le"))
EOF
```

- [ ] **Step 2: Add failing case rows + a fail-loudly test**

Append to `FEED_CASES`:

```python
    ("dirty_entities.xml", "Dirty Show", "Dirty & Sons", 1,
     "https://cdn.example.test/dirty1.mp3?a=1&b=2", "2026-06-29"),
    ("utf16_bom.xml", "UTF16 Show", "", 1,
     "https://cdn.example.test/u16.mp3", "2026-06-28"),
```

And add a standalone test (still-broken XML must raise, not return empty):

```python
def test_parse_feed_hopeless_xml_raises(monkeypatch):
    monkeypatch.setattr(core, "fetch", lambda url, timeout=45: io.BytesIO(b"<rss><channel>"))
    with pytest.raises(core.ET.ParseError):
        core.parse_feed("https://example.test/feed")
```

Note on expectations: `&nbsp;` becomes a non-breaking space which `_clean` collapses to a regular space → title `"Dirty Show"`; the `\x0b` control char is dropped; `&b=2` keeps its literal `&` after ET unescapes the sanitized `&amp;`.

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_core.py -q`
Expected: the two new fixture rows FAIL with `xml.etree.ElementTree.ParseError` (undefined entity / junk before declaration). (`utf16_bom` may pass — expat handles UTF-16 BOMs natively; if so it's a cheap regression guard, keep it.)

- [ ] **Step 4: Implement**

In `src/podpull/core.py` add `import html.entities` to the stdlib imports block, in alphabetical order (immediately before `import json`).

Add above `parse_feed`:

```python
_XML_PREDEFINED = frozenset({"amp", "lt", "gt", "quot", "apos"})


def _sanitize_xml(raw: bytes) -> bytes:
    """Best-effort repair of common real-world feed dirt: junk before the
    declaration, control chars, undefined HTML entities, bare '&'."""
    m = re.search(rb'<\?xml[^>]*encoding=["\']([A-Za-z0-9._-]+)["\']', raw[:200])
    enc = m.group(1).decode("ascii", "replace") if m else "utf-8"
    try:
        text = raw.decode(enc, "replace")
    except LookupError:                     # unknown codec name in declaration
        text = raw.decode("utf-8", "replace")
    text = text.lstrip("\ufeff\x00 \t\r\n")
    # we re-encode as UTF-8 below, so the declared encoding must not disagree
    text = re.sub(r'(<\?xml[^>]*?)\s+encoding=["\'][^"\']*["\']', r"\1", text, count=1)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    def _entity(mm):
        name = mm.group(1)
        if name in _XML_PREDEFINED:
            return mm.group(0)
        ch = html.entities.html5.get(name + ";")
        return "".join(f"&#{ord(c)};" for c in ch) if ch else ""
    text = re.sub(r"&([A-Za-z][A-Za-z0-9]{1,31});", _entity, text)
    text = re.sub(r"&(?![A-Za-z][A-Za-z0-9]{1,31};|#\d+;|#x[0-9A-Fa-f]+;)", "&amp;", text)
    return text.encode("utf-8")


def _parse_xml(raw: bytes) -> "ET.Element":
    try:
        return ET.fromstring(raw)
    except ET.ParseError as err:
        try:
            return ET.fromstring(_sanitize_xml(raw))
        except ET.ParseError:
            raise err from None             # fail loudly with the original error
```

In `parse_feed`, change the first line to:

```python
    root = _parse_xml(fetch(feed_url).read())
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_core.py -q`
Expected: PASS (all rows + `test_parse_feed_hopeless_xml_raises`).

- [ ] **Step 6: Commit**

```bash
git add src/podpull/core.py tests/
git commit -m "feat: sanitize-and-retry recovery for dirty feed XML"
```

---

### Task 6: Chinese-host fixtures (xiaoyuzhou, Ximalaya, SoundOn, Firstory)

**Files:**
- Create: `tests/fixtures/feeds/xiaoyuzhou.xml`, `ximalaya.xml`, `soundon.xml`, `firstory.xml`
- Test: `tests/test_core.py` (extend `FEED_CASES`)

Pure regression pinning — parser code from Tasks 3–5 should already handle these. Any failure = fix `core.py`.

- [ ] **Step 1: Create fixtures**

`tests/fixtures/feeds/xiaoyuzhou.xml` (忽左忽右-shaped: CDATA, dts-api tracking enclosure with the target host embedded in the path):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title><![CDATA[忽左忽右]]></title>
    <itunes:author><![CDATA[JustPod]]></itunes:author>
    <atom:link href="https://feed.xyzfm.space/cv4bkgpuglwp" rel="self" type="application/rss+xml"/>
    <item>
      <title><![CDATA[380 一战爆发110周年：欧洲旧秩序的黄昏]]></title>
      <pubDate>Thu, 02 Jul 2026 20:00:00 +0800</pubDate>
      <guid isPermaLink="false">xyz-380</guid>
      <link>https://www.xiaoyuzhoufm.com/episode/abc380</link>
      <enclosure url="https://dts-api.xiaoyuzhoufm.com/track/cv4bkgpuglwp/xyz380/media.xyzcdn.net/lvJzoGJDVn.m4a" type="audio/mp4" length="4"/>
      <content:encoded><![CDATA[<p>本期节目…</p>]]></content:encoded>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/ximalaya.xml` (声动早咖啡-shaped: `//` double-slash enclosure path, `&amp;`-escaped query with nested percent-encoded URL in `jt=`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>声动早咖啡</title>
    <itunes:author>声动活泼</itunes:author>
    <item>
      <title>硅谷巨头抢购核电，AI耗电有多猛？</title>
      <pubDate>Mon, 06 Jul 2026 07:30:00 +0800</pubDate>
      <guid>xmly-1</guid>
      <enclosure url="https://jt.ximalaya.com//GKwRIW8LWq_ZAX-DKgJcpzTV.m4a?channel=rss&amp;jt=https%3A%2F%2Faod.cos.tx.xmcdn.com%2Fstorages%2Fabc.m4a" type="audio/x-m4a" length="5"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/soundon.xml` (股癌-shaped: custom `soundon:` namespace, self-referencing `itunes:new-feed-url`, `?times=` querystring):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:soundon="https://soundon.fm/rss">
  <channel>
    <title>股癌</title>
    <itunes:author>謝孟恭</itunes:author>
    <itunes:new-feed-url>https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml</itunes:new-feed-url>
    <soundon:podcastId>954689a5-3096-43a4-a80b-7810b219cef3</soundon:podcastId>
    <item>
      <title>EP560 | 台股創高</title>
      <pubDate>Sun, 05 Jul 2026 10:00:00 +0800</pubDate>
      <guid>soundon-560</guid>
      <enclosure url="https://rss.soundon.fm/rssf/954689a5/ep560/rssFileVip.mp3?times=1751700000" type="audio/mpeg" length="6"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/firstory.xml` (百靈果-shaped: EVERYTHING CDATA-wrapped including `<language>`, stale channel-level `pubDate` that must NOT leak into episodes, percent-encoded URL embedded in enclosure path):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title><![CDATA[百靈果 News]]></title>
    <language><![CDATA[zh-Hant]]></language>
    <pubDate>Mon, 01 Dec 2025 00:00:00 +0000</pubDate>
    <itunes:author><![CDATA[百靈果 News]]></itunes:author>
    <item>
      <title><![CDATA[EP500 國際新聞]]></title>
      <pubDate><![CDATA[Sat, 04 Jul 2026 01:00:00 +0000]]></pubDate>
      <guid><![CDATA[firstory-500]]></guid>
      <enclosure url="https://m.cdn.firstory.me/track/cmjaz594i/https%3A%2F%2Ffile.cdn.firstory.me%2Fstory%2Fep500.mp3" type="audio/mpeg" length="7"/>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Add case rows**

Append to `FEED_CASES`:

```python
    ("xiaoyuzhou.xml", "忽左忽右", "JustPod", 1,
     "https://dts-api.xiaoyuzhoufm.com/track/cv4bkgpuglwp/xyz380/media.xyzcdn.net/lvJzoGJDVn.m4a",
     "2026-07-02"),
    ("ximalaya.xml", "声动早咖啡", "声动活泼", 1,
     "https://jt.ximalaya.com//GKwRIW8LWq_ZAX-DKgJcpzTV.m4a?channel=rss&jt=https%3A%2F%2Faod.cos.tx.xmcdn.com%2Fstorages%2Fabc.m4a",
     "2026-07-06"),
    ("soundon.xml", "股癌", "謝孟恭", 1,
     "https://rss.soundon.fm/rssf/954689a5/ep560/rssFileVip.mp3?times=1751700000", "2026-07-05"),
    ("firstory.xml", "百靈果 News", "百靈果 News", 1,
     "https://m.cdn.firstory.me/track/cmjaz594i/https%3A%2F%2Ffile.cdn.firstory.me%2Fstory%2Fep500.mp3",
     "2026-07-04"),
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_core.py::test_parse_feed_fixture -v`
Expected: PASS for all. (Firstory's `2026-07-04` proves the item's CDATA pubDate is used, not the stale channel one — a wrong implementation that reads channel-level pubDate yields `2025-12-01`.)

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: CN host fixtures — xiaoyuzhou, ximalaya, soundon, firstory"
```

---

### Task 7: remaining host fixtures (Lizhi, Typlog, Fireside, Anchor, Acast, Libsyn, Transistor)

**Files:**
- Create: `tests/fixtures/feeds/lizhi.xml`, `typlog.xml`, `fireside.xml`, `anchor.xml`, `acast.xml`, `libsyn.xml`, `transistor.xml`
- Test: `tests/test_core.py` (extend `FEED_CASES`)

- [ ] **Step 1: Create fixtures**

`tests/fixtures/feeds/lizhi.xml` (大内密谈-shaped: non-zero-padded RFC-822 date):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>大内密谈</title>
    <itunes:author>大内密谈</itunes:author>
    <item>
      <title>vol.1200 深夜谈谈</title>
      <pubDate>Sun, 5 Jul 2026 21:00:00 +0800</pubDate>
      <enclosure url="http://cdn.lizhi.fm/audio/2026/07/05/1200.mp3" type="audio/mpeg" length="8"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/typlog.xml` (疯投圈-shaped: zero CDATA, entity-escaped text, minimal namespaces):

```xml
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>疯投圈</title>
    <itunes:author>黄海、Rio</itunes:author>
    <item>
      <title>76. 咖啡 &amp; 茶饮：新消费的&#38472;年老酒</title>
      <pubDate>Fri, 03 Jul 2026 12:00:00 GMT</pubDate>
      <enclosure url="https://rio.xyzcdn.net/crazy-capital/ep76.m4a" type="audio/mp4" length="9"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/fireside.xml` (科技早知道-shaped: `+0800` dates, Podcasting 2.0 namespace):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>科技早知道</title>
    <itunes:author>声动活泼</itunes:author>
    <podcast:locked>no</podcast:locked>
    <item>
      <title>S8E20 硅谷现场</title>
      <pubDate>Thu, 02 Jul 2026 08:00:00 +0800</pubDate>
      <enclosure url="https://aphid.fireside.fm/d/1437767933/s8e20.mp3" type="audio/mpeg" length="10"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/anchor.xml` (台灣通勤第一品牌-shaped: percent-encoded CloudFront URL inside the enclosure path):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>台灣通勤第一品牌</title>
    <itunes:author>台通</itunes:author>
    <item>
      <title>EP600 通勤路上</title>
      <pubDate>Wed, 01 Jul 2026 16:00:00 GMT</pubDate>
      <enclosure url="https://anchor.fm/s/1ea77470/podcast/play/999/https%3A%2F%2Fd3ctxlq1ktw2nl.cloudfront.net%2Fstaging%2Fep600.m4a" type="audio/x-m4a" length="11"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/acast.xml` (不明白播客-shaped):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:acast="https://schema.acast.com/1.0/">
  <channel>
    <title>不明白播客</title>
    <itunes:author>袁莉和她的朋友们</itunes:author>
    <acast:showId>68004395b4ef799a7a410371</acast:showId>
    <item>
      <title>EP-100 访谈</title>
      <pubDate>Tue, 30 Jun 2026 22:00:00 GMT</pubDate>
      <enclosure url="https://sphinx.acast.com/p/open/s/68004395/e/100/media.mp3" type="audio/mpeg" length="12"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/libsyn.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Libsyn Show</title>
    <itunes:author>Libsyn Author</itunes:author>
    <item>
      <title>Libsyn EP1</title>
      <pubDate>Mon, 29 Jun 2026 09:00:00 +0000</pubDate>
      <enclosure url="https://traffic.libsyn.com/secure/example/ep1.mp3?dest-id=1" type="audio/mpeg" length="13"/>
    </item>
  </channel>
</rss>
```

`tests/fixtures/feeds/transistor.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Transistor Show</title>
    <itunes:author>Transistor Author</itunes:author>
    <item>
      <title>Transistor EP1</title>
      <pubDate>Sun, 28 Jun 2026 09:00:00 +0000</pubDate>
      <enclosure url="https://media.transistor.fm/abc123/ep1.mp3" type="audio/mpeg" length="14"/>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Add case rows**

Append to `FEED_CASES`:

```python
    ("lizhi.xml", "大内密谈", "大内密谈", 1,
     "http://cdn.lizhi.fm/audio/2026/07/05/1200.mp3", "2026-07-05"),
    ("typlog.xml", "疯投圈", "黄海、Rio", 1,
     "https://rio.xyzcdn.net/crazy-capital/ep76.m4a", "2026-07-03"),
    ("fireside.xml", "科技早知道", "声动活泼", 1,
     "https://aphid.fireside.fm/d/1437767933/s8e20.mp3", "2026-07-02"),
    ("anchor.xml", "台灣通勤第一品牌", "台通", 1,
     "https://anchor.fm/s/1ea77470/podcast/play/999/https%3A%2F%2Fd3ctxlq1ktw2nl.cloudfront.net%2Fstaging%2Fep600.m4a",
     "2026-07-01"),
    ("acast.xml", "不明白播客", "袁莉和她的朋友们", 1,
     "https://sphinx.acast.com/p/open/s/68004395/e/100/media.mp3", "2026-06-30"),
    ("libsyn.xml", "Libsyn Show", "Libsyn Author", 1,
     "https://traffic.libsyn.com/secure/example/ep1.mp3?dest-id=1", "2026-06-29"),
    ("transistor.xml", "Transistor Show", "Transistor Author", 1,
     "https://media.transistor.fm/abc123/ep1.mp3", "2026-06-28"),
```

- [ ] **Step 3: Run tests, then the whole suite**

Run: `pytest tests/test_core.py::test_parse_feed_fixture -v` → PASS (all 18 rows)
Run: `pytest -q` → PASS

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: host fixtures — lizhi, typlog, fireside, anchor, acast, libsyn, transistor"
```

---

### Task 8: browser-UA regression test

**Files:**
- Test: `tests/test_core.py`

Four researched hosts (SoundOn, Typlog, Fireside, Lizhi CDN) 403 `Python-urllib` UAs; this pins CLAUDE.md invariant #5 at the code level.

- [ ] **Step 1: Write the test**

```python
def test_fetch_and_download_send_browser_ua(monkeypatch, tmp_path):
    seen = []

    class _Resp(io.BytesIO):
        status = 200
        length = 2
        headers = {"Content-Type": "audio/mpeg"}

        def __init__(self):
            super().__init__(b"ok")

    def fake_urlopen(req, timeout=None):
        seen.append(req.get_header("User-agent"))
        return _Resp()

    monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)
    core.fetch("https://feeds.soundon.fm/x.xml")
    core.download_url("https://cdn.lizhi.fm/a.mp3", str(tmp_path / "a.mp3"))
    assert seen == [core.UA, core.UA]
    assert all("mozilla" in ua.lower() and "python" not in ua.lower() for ua in seen)
```

Note: `_Resp.headers` being a plain dict is fine — both `resp.headers.get(...)` call sites only use `.get`.

- [ ] **Step 2: Run it**

Run: `pytest tests/test_core.py::test_fetch_and_download_send_browser_ua -v`
Expected: PASS immediately (behavior already exists — this is a pin, not a change). If it fails, `core.fetch`/`download_url` stopped sending `core.UA`: fix core, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_core.py
git commit -m "test: pin browser User-Agent on fetch and download (CLAUDE.md invariant 5)"
```

---

### Task 9: `classify()` accepts Ximalaya album links

**Files:**
- Modify: `src/podpull/core.py` (`classify`, currently lines 70–84)
- Test: `tests/test_core.py` (`test_classify`)

- [ ] **Step 1: Extend the test (failing)**

Add to `test_classify` in `tests/test_core.py`:

```python
    assert core.classify("https://www.ximalaya.com/album/51076156") == \
        ("rss", "https://www.ximalaya.com/album/51076156.xml")
    assert core.classify("https://www.ximalaya.com/album/51076156.xml") == \
        ("rss", "https://www.ximalaya.com/album/51076156.xml")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_core.py::test_classify -v`
Expected: FAIL — the album page URL classifies as plain `rss` with the original (non-.xml) URL.

- [ ] **Step 3: Implement**

In `core.classify`, insert before the `if s.startswith("http"):` line:

```python
    m = re.search(r"ximalaya\.com/album/(\d+)", s)
    if m:  # Ximalaya Podcast托管 albums expose RSS at album/<id>.xml
        return "rss", f"https://www.ximalaya.com/album/{m.group(1)}.xml"
```

Update the docstring's kind list comment to mention that ximalaya album links normalize to `rss`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_core.py -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add src/podpull/core.py tests/test_core.py
git commit -m "feat: accept ximalaya.com/album/<id> links (normalize to RSS .xml)"
```

---

### Task 10: download sanity guard (reject `text/*` responses)

**Files:**
- Modify: `src/podpull/core.py` (`download_url`, currently lines 240–273)
- Test: `tests/test_core.py`

Motivation: Ximalaya's CDN answers stale enclosure queries with `HTTP 200`, `Content-Type: text/plain`, 7-byte body — podpull would write a 7-byte ".m4a" and exit 0.

- [ ] **Step 1: Write the failing test**

```python
def _fake_response(body: bytes, ctype: str):
    class _Resp(io.BytesIO):
        status = 200
        headers = {"Content-Type": ctype}

        def __init__(self):
            super().__init__(body)
            self.length = len(body)
    return _Resp()


def test_download_url_rejects_text_response(monkeypatch, tmp_path):
    monkeypatch.setattr(core.urllib.request, "urlopen",
                        lambda req, timeout=None: _fake_response(b"deleted", "text/plain; charset=utf-8"))
    dest = tmp_path / "ep.m4a"
    with pytest.raises(ValueError, match="not audio"):
        core.download_url("https://jt.ximalaya.com//x.m4a?bad=1", str(dest))
    assert not dest.exists()


def test_download_url_accepts_audio_and_octet_stream(monkeypatch, tmp_path):
    for ctype in ("audio/mpeg", "application/octet-stream", ""):
        monkeypatch.setattr(core.urllib.request, "urlopen",
                            lambda req, timeout=None, c=ctype: _fake_response(b"AUDIO", c))
        dest = tmp_path / f"ok-{ctype.replace('/', '_') or 'none'}.mp3"
        assert core.download_url("https://cdn.example.test/a.mp3", str(dest)) == str(dest)
        assert dest.read_bytes() == b"AUDIO"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_core.py::test_download_url_rejects_text_response -v`
Expected: FAIL — no ValueError; the 7-byte file gets written.

- [ ] **Step 3: Implement**

In `core.download_url`, right after the `if existing and getattr(resp, "status", 200) == 200:` block and before `mode = "ab" if existing else "wb"`, insert:

```python
    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype.startswith("text/"):
        # e.g. Ximalaya's CDN answers a stale enclosure query with 200 text/plain
        raise ValueError(f"server returned {ctype}, not audio — "
                         "the feed's enclosure URL may be stale")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_core.py -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add src/podpull/core.py tests/test_core.py
git commit -m "feat: reject text/* responses in download_url (stale-enclosure guard)"
```

---

### Task 11: Podcast Index core functions

**Files:**
- Modify: `src/podpull/core.py` (imports + new section between "search / resolve" and "direct-episode resolvers")
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_pi_credentials(monkeypatch):
    monkeypatch.delenv("PODCASTINDEX_API_KEY", raising=False)
    monkeypatch.delenv("PODCASTINDEX_API_SECRET", raising=False)
    assert core.pi_credentials() is None
    monkeypatch.setenv("PODCASTINDEX_API_KEY", "k")
    assert core.pi_credentials() is None          # secret still missing
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "s")
    assert core.pi_credentials() == ("k", "s")


def test_pi_headers_deterministic():
    h = core._pi_headers("key", "secret", now=1751900000)
    assert h["X-Auth-Key"] == "key"
    assert h["X-Auth-Date"] == "1751900000"
    import hashlib
    assert h["Authorization"] == hashlib.sha1(b"keysecret1751900000").hexdigest()
    assert h["User-Agent"] == core.UA


def test_pi_search_shows_normalizes(monkeypatch):
    monkeypatch.setenv("PODCASTINDEX_API_KEY", "k")
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "s")
    monkeypatch.setattr(core, "_pi_get", lambda path, params: {
        "feeds": [{"id": 887080, "title": "忽左忽右", "url": "https://feed.xyzfm.space/cv4bkgpuglwp",
                   "author": "JustPod", "itunesId": 1478791559, "episodeCount": 380}],
    })
    rows = core.pi_search_shows("忽左忽右", limit=5)
    assert rows == [{"collectionId": 1478791559, "collectionName": "忽左忽右",
                     "artistName": "JustPod", "feedUrl": "https://feed.xyzfm.space/cv4bkgpuglwp",
                     "trackCount": 380}]


def test_pi_feed_by_itunes_id(monkeypatch):
    monkeypatch.setattr(core, "_pi_get",
                        lambda path, params: {"feed": {"url": "https://feed.example.test/x"}})
    assert core.pi_feed_by_itunes_id("123") == "https://feed.example.test/x"
    monkeypatch.setattr(core, "_pi_get", lambda path, params: {"feed": []})
    assert core.pi_feed_by_itunes_id("123") is None

    def _boom(path, params):
        raise OSError("network down")
    monkeypatch.setattr(core, "_pi_get", _boom)
    assert core.pi_feed_by_itunes_id("123") is None   # degrades, never raises
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_core.py -q -k pi_`
Expected: FAIL with `AttributeError: module 'podpull.core' has no attribute ...`

- [ ] **Step 3: Implement**

In `src/podpull/core.py` imports, add `import hashlib` and `import time` (alphabetical order within the stdlib block). Then add a new section after `apple_show_to_feed` (before `parse_feed`'s helpers):

```python
# --------------------------------------------------------------------------- #
# Podcast Index (optional, BYOK) — free keys at https://api.podcastindex.org
# Active only when both env vars are set; otherwise podpull never contacts PI.
# --------------------------------------------------------------------------- #
PODCASTINDEX_API = "https://api.podcastindex.org/api/1.0"


def pi_credentials() -> "tuple[str, str] | None":
    key = os.environ.get("PODCASTINDEX_API_KEY", "").strip()
    secret = os.environ.get("PODCASTINDEX_API_SECRET", "").strip()
    return (key, secret) if key and secret else None


def _pi_headers(key: str, secret: str, now: "int | None" = None) -> dict:
    ts = str(int(time.time()) if now is None else now)
    auth = hashlib.sha1((key + secret + ts).encode()).hexdigest()
    return {"User-Agent": UA, "X-Auth-Key": key, "X-Auth-Date": ts,
            "Authorization": auth}


def _pi_get(path: str, params: dict) -> dict:
    creds = pi_credentials()
    if not creds:
        raise ValueError("Podcast Index credentials not set "
                         "(PODCASTINDEX_API_KEY / PODCASTINDEX_API_SECRET)")
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{PODCASTINDEX_API}{path}?{q}",
                                 headers=_pi_headers(*creds))
    return json.load(urllib.request.urlopen(req, timeout=45))


def pi_search_shows(term: str, limit: int = 10) -> list:
    """Search Podcast Index; rows use the same keys as iTunes search results
    so the CLI table code needs no changes."""
    data = _pi_get("/search/byterm", {"q": term, "max": limit})
    return [{"collectionId": f.get("itunesId") or "",
             "collectionName": f.get("title") or "",
             "artistName": f.get("author") or "",
             "feedUrl": f.get("url") or "",
             "trackCount": f.get("episodeCount") or 0}
            for f in data.get("feeds", [])]


def pi_feed_by_itunes_id(pid: str) -> "str | None":
    """Second-directory feed lookup by Apple ID. Never raises — returns None
    so callers degrade gracefully when PI is down or has no entry."""
    try:
        feed = _pi_get("/podcasts/byitunesid", {"id": pid}).get("feed") or {}
        return (feed.get("url") or None) if isinstance(feed, dict) else None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_core.py -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add src/podpull/core.py tests/test_core.py
git commit -m "feat: Podcast Index core — BYOK auth, search, by-itunes-id lookup"
```

---

### Task 12: `apple_show_to_feed` falls back to Podcast Index

**Files:**
- Modify: `src/podpull/core.py` (`apple_show_to_feed`, currently lines 98–111)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_apple_show_to_feed_pi_fallback(monkeypatch):
    monkeypatch.setenv("PODCASTINDEX_API_KEY", "k")
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "s")
    monkeypatch.setattr(core, "fetch_json", lambda url: {"results": []})   # iTunes empty
    monkeypatch.setattr(core, "pi_feed_by_itunes_id",
                        lambda pid: "https://feed.example.test/fallback")
    feed, name, author, pid = core.apple_show_to_feed("1478791559")
    assert feed == "https://feed.example.test/fallback"
    assert pid == "1478791559"
    assert name == "" and author == ""


def test_apple_show_to_feed_no_creds_still_raises(monkeypatch):
    monkeypatch.delenv("PODCASTINDEX_API_KEY", raising=False)
    monkeypatch.delenv("PODCASTINDEX_API_SECRET", raising=False)
    monkeypatch.setattr(core, "fetch_json", lambda url: {"results": []})
    calls = []
    monkeypatch.setattr(core, "pi_feed_by_itunes_id",
                        lambda pid: calls.append(pid))
    with pytest.raises(ValueError):
        core.apple_show_to_feed("123")
    assert calls == []                     # PI never contacted without keys
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_core.py -q -k apple_show`
Expected: `test_apple_show_to_feed_pi_fallback` FAILS (raises "iTunes lookup returned nothing").

- [ ] **Step 3: Implement**

Replace the body of `apple_show_to_feed` after `pid = m.group(1)`:

```python
    results = fetch_json(f"{ITUNES_LOOKUP}?id={pid}").get("results", [])
    r = results[0] if results else {}
    feed = r.get("feedUrl")
    if not feed and pi_credentials():      # second directory, BYOK-only
        feed = pi_feed_by_itunes_id(pid)
    if not feed:
        if not results:
            raise ValueError(f"iTunes lookup returned nothing for id={pid}")
        raise ValueError(f"No feedUrl for id={pid} (not a podcast?)")
    return feed, r.get("collectionName", ""), r.get("artistName", ""), pid
```

- [ ] **Step 4: Run tests**

Run: `pytest -q` → PASS (full suite: the two new tests plus no regressions).

- [ ] **Step 5: Commit**

```bash
git add src/podpull/core.py tests/test_core.py
git commit -m "feat: fall back to Podcast Index when iTunes lookup has no feed"
```

---

### Task 13: `cmd_search` merges Podcast Index results

**Files:**
- Modify: `src/podpull/cli.py` (`cmd_search`, currently lines 93–109; `EXAMPLES`, lines 296–310)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py` (it already imports `argparse`, `cli`, `core` — follow the file's existing conventions; add imports only if missing):

```python
def _search_args(term="故事"):
    return argparse.Namespace(term=term, limit=10, country="US")


def test_search_without_keys_never_calls_pi(monkeypatch):
    monkeypatch.setattr(core, "pi_credentials", lambda: None)
    monkeypatch.setattr(core, "search_shows", lambda term, limit, country: [
        {"collectionId": 1, "collectionName": "A", "artistName": "x",
         "feedUrl": "https://f/a", "trackCount": 3}])
    monkeypatch.setattr(core, "pi_search_shows",
                        lambda *a, **k: pytest.fail("PI must not be called without keys"))
    assert cli.cmd_search(_search_args()) == 0


def test_search_merges_and_dedupes_pi(monkeypatch):
    monkeypatch.setattr(core, "pi_credentials", lambda: ("k", "s"))
    monkeypatch.setattr(core, "search_shows", lambda term, limit, country: [
        {"collectionId": 1, "collectionName": "A", "artistName": "x",
         "feedUrl": "https://f/a", "trackCount": 3}])
    monkeypatch.setattr(core, "pi_search_shows", lambda term, limit: [
        {"collectionId": 1, "collectionName": "A (PI)", "artistName": "x",
         "feedUrl": "https://f/a/", "trackCount": 3},          # dup (trailing slash)
        {"collectionId": 2, "collectionName": "B", "artistName": "y",
         "feedUrl": "https://f/b", "trackCount": 9}])          # new
    seen = []
    monkeypatch.setattr(cli, "_render_search_table", lambda term, rows: seen.extend(rows))
    assert cli.cmd_search(_search_args()) == 0
    assert [r["collectionName"] for r in seen] == ["A", "B"]   # iTunes wins the dup


def test_search_survives_one_backend_failing(monkeypatch):
    monkeypatch.setattr(core, "pi_credentials", lambda: ("k", "s"))

    def _boom(term, limit, country):
        raise OSError("itunes down")
    monkeypatch.setattr(core, "search_shows", _boom)
    monkeypatch.setattr(core, "pi_search_shows", lambda term, limit: [
        {"collectionId": 2, "collectionName": "B", "artistName": "y",
         "feedUrl": "https://f/b", "trackCount": 9}])
    assert cli.cmd_search(_search_args()) == 0                 # PI results still shown

    monkeypatch.setattr(core, "pi_credentials", lambda: None)
    with pytest.raises(OSError):                               # no keys -> unchanged behavior
        cli.cmd_search(_search_args())
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli.py -q -k search`
Expected: FAIL (`_render_search_table` doesn't exist; merge behavior missing).

- [ ] **Step 3: Implement**

In `src/podpull/cli.py`, replace `cmd_search` with:

```python
def _render_search_table(term: str, results: list) -> None:
    table = Table(title=f"Podcasts matching “{term}”", header_style="bold", expand=False)
    table.add_column("Apple ID", style="cyan", no_wrap=True)
    table.add_column("Eps", justify="right", style="magenta")
    table.add_column("Show")
    table.add_column("Author", style="dim")
    for r in results:
        table.add_row(str(r.get("collectionId") or "—"), str(r.get("trackCount") or "?"),
                      r.get("collectionName") or "", r.get("artistName") or "")
    ui.print(table)
    ui.print("[dim]Next:[/] podpull list <Apple ID>  •  podpull get <Apple ID>")


def _merge_results(primary: list, extra: list) -> list:
    seen = {(r.get("feedUrl") or "").strip().rstrip("/") for r in primary}
    seen.discard("")
    merged = list(primary)
    for r in extra:
        key = (r.get("feedUrl") or "").strip().rstrip("/")
        if key and key in seen:
            continue
        seen.add(key)
        merged.append(r)
    return merged


def cmd_search(args) -> int:
    results, warnings = [], []
    with ui.status(f"[cyan]Searching for “{args.term}”…"):
        if core.pi_credentials() is None:
            # no PI keys -> exactly the old behavior (errors propagate to main)
            results = core.search_shows(args.term, limit=args.limit, country=args.country)
        else:
            try:
                results = core.search_shows(args.term, limit=args.limit, country=args.country)
            except Exception as e:
                warnings.append(f"iTunes search failed: {e}")
            try:
                results = _merge_results(results, core.pi_search_shows(args.term, limit=args.limit))
            except Exception as e:
                warnings.append(f"Podcast Index search failed: {e}")
    for w in warnings:
        _err(w)
    if not results:
        _err("no shows found")
        return 1
    _render_search_table(args.term, results)
    return 0
```

In `EXAMPLES` (the help epilog), add before the final `"""`:

```
[dim]Optional: set PODCASTINDEX_API_KEY + PODCASTINDEX_API_SECRET (free — podcastindex.org)[/]
[dim]to enrich search results and add a feed-resolution fallback.[/]
```

- [ ] **Step 4: Run tests**

Run: `pytest -q` → PASS (full suite).

- [ ] **Step 5: Commit**

```bash
git add src/podpull/cli.py tests/test_cli.py
git commit -m "feat: merge Podcast Index results into search (BYOK, graceful degradation)"
```

---

### Task 14: network-marked integration tests

**Files:**
- Create: `tests/test_network.py`

- [ ] **Step 1: Write the file**

```python
"""Live-network integration tests. EXCLUDED from the default suite.

Run explicitly:  pytest -m network
These hit real hosts and will flake if a show migrates feeds — that's the
point: they detect real-world drift the offline fixtures can't.
"""
import pytest

from podpull import core

pytestmark = pytest.mark.network

LIVE_FEEDS = [
    # (label, feed_url)
    ("xiaoyuzhou 忽左忽右", "https://feed.xyzfm.space/cv4bkgpuglwp"),
    ("ximalaya 声动早咖啡", "https://www.ximalaya.com/album/51076156.xml"),
    ("soundon 股癌", "https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml"),
    ("firstory 百靈果", "https://feed.firstory.me/rss/user/cmjaz594i0000hdvpdpnd4fw8"),
]


@pytest.mark.parametrize("label,feed", LIVE_FEEDS, ids=[f[0] for f in LIVE_FEEDS])
def test_live_feed_parses(label, feed):
    title, _author, eps = core.parse_feed(feed)
    assert title, f"{label}: empty show title"
    assert eps, f"{label}: no episodes parsed"
    first = eps[0]
    assert first.url.startswith("http"), f"{label}: bad enclosure {first.url!r}"
    assert first.date != "0000-00-00", f"{label}: unparseable pubDate {first.pub!r}"


def test_live_itunes_resolution():
    feed, name, _author, pid = core.apple_show_to_feed("1493503146")  # 忽左忽右
    assert feed.startswith("http") and pid == "1493503146" and name
```

- [ ] **Step 2: Verify exclusion and (optionally) run live**

Run: `pytest -q` → the new tests are DESELECTED (count unchanged).
Run: `pytest -m network -q` → should pass with live network; if a host is down or a show migrated, note it in the commit message but don't block the branch on it.

- [ ] **Step 3: Commit**

```bash
git add tests/test_network.py
git commit -m "test: live-network integration tests (pytest -m network)"
```

---

### Task 15: docs, integrations note, version bump, final verification

**Files:**
- Modify: `src/podpull/__init__.py` (version), `pyproject.toml` (version), `CHANGELOG.md`, `README.md`, `src/podpull/integrations/SKILL.md`, `src/podpull/integrations/opencode_command.md`, `src/podpull/integrations/cursor_rule.mdc`

- [ ] **Step 1: Version bump — BOTH files**

`src/podpull/__init__.py`: `__version__ = "0.6.0"`
`pyproject.toml`: `version = "0.6.0"`

- [ ] **Step 2: CHANGELOG entry**

Add at the top of `CHANGELOG.md` (match the existing entry format in that file):

```markdown
## 0.6.0 — 2026-07-07

- Robust feed parsing: RSS 2.0 / RSS 1.0 (RDF) / Atom, any-namespace matching,
  `media:content` + Atom-enclosure fallbacks, dirty-XML sanitize-and-retry
  (undefined entities, bare `&`, control chars), ISO-8601 dates.
- Verified against Chinese-market hosts: xiaoyuzhou, Ximalaya, SoundOn, Firstory,
  WavPub, Typlog, Fireside, Lizhi (offline fixtures + `pytest -m network` live suite).
- `ximalaya.com/album/<id>` links are now accepted directly.
- Download guard: `text/*` responses (stale enclosures, e.g. Ximalaya CDN) now
  error instead of writing a garbage audio file.
- Optional Podcast Index support (BYOK: `PODCASTINDEX_API_KEY`/`_SECRET`):
  enriches `search` and adds a feed-resolution fallback when iTunes has no feed.
```

(If the tag is cut on a later day, update the date in the same commit as the tag.)

- [ ] **Step 3: README — add an optional-PI section + ximalaya mention**

In `README.md`: add `ximalaya.com/album/<id>` to wherever supported inputs are listed, and add a short section:

```markdown
### Podcast Index (optional)

podpull can enrich `search` and feed resolution with the open
[Podcast Index](https://podcastindex.org) directory. Get a free API key at
[api.podcastindex.org](https://api.podcastindex.org/signup) and set:

```bash
export PODCASTINDEX_API_KEY=...
export PODCASTINDEX_API_SECRET=...
```

Without these, podpull behaves exactly as before (iTunes only).
```

- [ ] **Step 4: Integrations one-liners**

Add one line to each of `src/podpull/integrations/SKILL.md`, `opencode_command.md`, `cursor_rule.mdc`, in their existing style, near their command/rules list:

```
- Optional: if PODCASTINDEX_API_KEY/PODCASTINDEX_API_SECRET are set, `search` also queries Podcast Index and feed resolution gains a fallback; ximalaya.com/album/<id> links work as a source.
```

- [ ] **Step 5: Full verification**

Run: `pytest -q` → ALL PASS
Run: `ruff check src` → clean
Run: `python -m build && unzip -l dist/*.whl | grep integrations` → integration files present in the wheel (`pip install build` first if missing; then delete `dist/` — it's gitignored but don't commit it)
Run: `podpull --help` → epilog shows the PI note; `podpull search --help` still renders.

- [ ] **Step 6: Commit**

```bash
git add src/podpull/__init__.py pyproject.toml CHANGELOG.md README.md src/podpull/integrations/
git commit -m "docs: v0.6.0 — changelog, README Podcast Index section, integrations note"
```

---

## Post-plan notes for the executor

- **Do not** merge or rebase against PR #3 (`--quiet`) mid-plan; if it lands on main first, rebasing this branch is the integrator's job at the end (conflicts, if any, are confined to `cli.py`).
- The release itself (tag `v0.6.0`, PyPI, Homebrew bump) is NOT part of this plan — the user decides when to cut it. No dependency changes were made, so no `brew update-python-resources` run is needed.
- If a live `pytest -m network` run fails because a show migrated its feed, update `LIVE_FEEDS`, don't weaken assertions.
