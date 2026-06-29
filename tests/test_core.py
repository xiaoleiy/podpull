"""Pure-logic tests (no network)."""
import pytest

from podget import core
from podget.core import Episode


def test_classify():
    assert core.classify("1532755821") == ("apple_show", "1532755821")
    assert core.classify("https://podcasts.apple.com/us/podcast/x/id123")[0] == "apple_show"
    assert core.classify("https://podcasts.apple.com/us/podcast/x/id123?i=456")[0] == "apple_episode"
    assert core.classify("https://www.xiaoyuzhoufm.com/episode/abc")[0] == "xyz_episode"
    assert core.classify("https://feed.firstory.me/rss/user/xyz")[0] == "rss"
    with pytest.raises(ValueError):
        core.classify("not a url")


def test_safe_filename():
    assert "/" not in core.safe_filename("EP1: a/b?c*d")
    assert core.safe_filename("  spaced   out  ") == "spaced out"
    assert len(core.safe_filename("x" * 500)) <= 140


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
