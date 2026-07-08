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
