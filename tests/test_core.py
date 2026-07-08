"""Pure-logic tests (no network)."""
import io
from pathlib import Path

import pytest

from podpull import core
from podpull.core import Episode

FIXTURES = Path(__file__).parent / "fixtures" / "feeds"

# (fixture, show_title, show_author, n_episodes, first_url, first_date)
FEED_CASES = [
    ("rss2_plain.xml", "Plain RSS2 Show", "Plain Author", 2,
     "https://cdn.example.test/ep2.mp3", "2026-07-03"),
    ("rss10_rdf.xml", "RDF Show", "RDF Author", 1,
     "https://cdn.example.test/rdf1.mp3", "2026-06-30"),
    ("atom.xml", "Atom Show", "Atom Author", 1,
     "https://cdn.example.test/atom1.mp3", "2026-07-01"),
    ("itunes_title_order.xml", "Real Channel Title", "Order Author", 1,
     "https://cdn.example.test/order1.mp3", "2026-07-04"),
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
    if fname == "itunes_title_order.xml":
        assert eps[0].title == "Real Episode Title"


def test_classify():
    assert core.classify("1532755821") == ("apple_show", "1532755821")
    assert core.classify("https://podcasts.apple.com/us/podcast/x/id123")[0] == "apple_show"
    assert core.classify("https://podcasts.apple.com/us/podcast/x/id123?i=456")[0] == "apple_episode"
    assert core.classify("https://www.xiaoyuzhoufm.com/episode/abc")[0] == "xyz_episode"
    assert core.classify("https://feed.firstory.me/rss/user/xyz")[0] == "rss"
    with pytest.raises(ValueError):
        core.classify("not a url")


def test_safe_filename():
    # OS-forbidden characters are removed
    assert "/" not in core.safe_filename("EP1: a/b?c*d")
    assert not set(core.safe_filename('a:b"c<d>e|f')) & set(':"<>|/\\*?')
    assert core.safe_filename("  spaced   out  ") == "spaced out"
    assert len(core.safe_filename("x" * 500)) <= 120
    # emoji & decorative symbols dropped; CJK and meaningful text kept
    assert core.safe_filename("🎧🌍 認識 SDGs｜未來玩家探險隊") == "認識 SDGs 未來玩家探險隊"
    assert core.safe_filename("我們家的睡前故事") == "我們家的睡前故事"
    # full-width punctuation folded then stripped; no leading/trailing junk
    assert core.safe_filename("：？ hello ｜") == "hello"
    assert core.safe_filename("...   ") == "untitled"
    assert core.safe_filename("") == "untitled"
    # Windows reserved device names are made safe (case-insensitive, incl. with extension)
    assert core.safe_filename("CON") == "_CON"
    assert core.safe_filename("nul") == "_nul"
    assert core.safe_filename("COM1") == "_COM1"
    assert core.safe_filename("CON.mp3").startswith("_")
    assert not core.safe_filename("Console war").startswith("_")  # not actually reserved


def test_ext_for():
    assert core.ext_for("https://x/a.m4a", "") == ".m4a"
    assert core.ext_for("https://x/track/a", "audio/mp4") == ".m4a"
    assert core.ext_for("https://x/a.mp3?v=1", "audio/mpeg") == ".mp3"
    assert core.ext_for("https://x/track/redirect", "") == ".mp3"  # default


def _eps():
    return [
        Episode(title="EP3 newest", pub="Sat, 27 Jun 2026 22:02:06 GMT", url="u3"),
        Episode(title="EP2 middle", pub="Tue, 23 Jun 2026 22:02:06 GMT", url="u2"),
        Episode(title="EP1 oldest", pub="Tue, 16 Jun 2026 22:02:07 GMT", url="u1"),
    ]


def test_episode_date():
    assert _eps()[0].date == "2026-06-27"
    assert Episode(title="x", pub="garbage", url="u").date == "0000-00-00"
    # RFC-822 with non-zero-padded day (Lizhi) — parsedate handles it
    assert Episode(title="x", pub="Sun, 5 Jul 2026 21:00:00 +0800", url="u").date == "2026-07-05"
    # ISO-8601 (Atom published / dc:date), with and without Z
    assert Episode(title="x", pub="2026-07-01T08:30:00Z", url="u").date == "2026-07-01"
    assert Episode(title="x", pub="2026-07-01T08:30:00+08:00", url="u").date == "2026-07-01"
    assert Episode(title="x", pub="", url="u").date == "0000-00-00"


def test_select_match():
    sel = core.select(_eps(), match="middle")
    assert [e.url for e in sel] == ["u2"]


def test_select_latest():
    assert [e.url for e in core.select(_eps(), latest=2)] == ["u3", "u2"]


def test_select_index():
    assert [e.url for e in core.select(_eps(), index="0,2")] == ["u3", "u1"]
    assert [e.url for e in core.select(_eps(), index="-1")] == ["u1"]  # negative ok


def test_select_none():
    assert core.select(_eps()) == []
