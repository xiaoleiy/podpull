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
    ("media_content_only.xml", "MRSS Show", "editor@example.test (MRSS Author)", 1,
     "https://cdn.example.test/mrss1.mp3", "2026-07-02"),
    ("wavpub.xml", "半拿铁 | 商业沉浮录", "潇磊布道", 1,
     "https://tk.wavpub.com/track/caffebreve/91.m4a", "2026-07-01"),
    ("omny.xml", "馬力歐陪你喝一杯", "鏡好聽", 1,
     "https://omny.example.test/ep388.mp3", "2026-06-30"),
    ("dirty_entities.xml", "Dirty Show", "Dirty & Sons", 1,
     "https://cdn.example.test/dirty1.mp3?a=1&b=2", "2026-06-29"),
    ("utf16_bom.xml", "UTF16 Show", "", 1,
     "https://cdn.example.test/u16.mp3", "2026-06-28"),
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


def test_parse_feed_hopeless_xml_raises(monkeypatch):
    monkeypatch.setattr(core, "fetch", lambda url, timeout=45: io.BytesIO(b"<rss><channel>"))
    with pytest.raises(core.ET.ParseError):
        core.parse_feed("https://example.test/feed")


def test_sanitize_preserves_cdata_and_unknown_entities(monkeypatch):
    raw = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<rss version="2.0"><channel>\n'
        b'<title><![CDATA[AT&T R&D Show]]></title>\n'
        b'<managingEditor>Dirty & Sons</managingEditor>\n'
        b'<item><title>A &bogus123; B</title>\n'
        b'<pubDate>Wed, 01 Jul 2026 08:00:00 GMT</pubDate>\n'
        b'<enclosure url="https://cdn.example.test/x.mp3" type="audio/mpeg"/>\n'
        b'</item></channel></rss>'
    )
    monkeypatch.setattr(core, "fetch", lambda url, timeout=45: io.BytesIO(raw))
    title, _a, eps = core.parse_feed("https://example.test/feed")
    assert title == "AT&T R&D Show"          # CDATA content untouched
    assert eps[0].title == "A &bogus123; B"  # unknown entity preserved, not dropped


def test_sanitize_handles_utf16_without_bom(monkeypatch):
    xml = ('<?xml version="1.0" encoding="UTF-16"?>'
           '<rss version="2.0"><channel><title>中文播客&nbsp;标题</title>'
           '<item><title>EP 一</title>'
           '<pubDate>Wed, 01 Jul 2026 08:00:00 GMT</pubDate>'
           '<enclosure url="https://cdn.example.test/cn.mp3" type="audio/mpeg"/>'
           '</item></channel></rss>')
    raw = xml.encode("utf-16-le")  # deliberately NO BOM
    monkeypatch.setattr(core, "fetch", lambda url, timeout=45: io.BytesIO(raw))
    title, _a, eps = core.parse_feed("https://example.test/feed")
    assert title == "中文播客 标题"
    assert eps[0].title == "EP 一"


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
