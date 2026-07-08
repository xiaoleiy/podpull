"""CLI wiring tests (no network, no real TTY)."""
import argparse
import io
import os
import sys
import types

from podpull import cli, core
from rich.console import Console

def _show():
    eps = [core.Episode(title=f"EP{i}", pub="Sat, 27 Jun 2026 22:02:06 GMT", url=f"u{i}")
           for i in range(3)]
    return core.Show(title="Demo Show", feed="https://feed", episodes=eps)


def _fake_questionary(selection):
    return types.SimpleNamespace(
        Choice=lambda title, value: value,
        checkbox=lambda *a, **k: types.SimpleNamespace(ask=lambda: selection),
    )


def _record_downloads(monkeypatch):
    got = []

    def fake_dl(ep, out, **kw):
        got.append(ep.title)
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, ep.title + ".mp3")
        with open(p, "wb") as f:
            f.write(b"x")
        return p

    monkeypatch.setattr(cli.core, "download_episode", fake_dl)
    return got


def test_get_interactive_selection_downloads_picked(monkeypatch, tmp_path):
    show = _show()
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: show)
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    monkeypatch.setitem(sys.modules, "questionary", _fake_questionary([0, 2]))
    got = _record_downloads(monkeypatch)

    rc = cli.cmd_get(argparse.Namespace(src="123", match=None, latest=None,
                                        index=None, out=str(tmp_path), no_input=False, quiet=False))
    assert rc == 0
    assert got == ["EP0", "EP2"]


def test_get_interactive_cancel_returns_error(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    monkeypatch.setitem(sys.modules, "questionary", _fake_questionary(None))  # Ctrl-C
    got = _record_downloads(monkeypatch)

    rc = cli.cmd_get(argparse.Namespace(src="123", match=None, latest=None,
                                        index=None, out=str(tmp_path), no_input=False, quiet=False))
    assert rc == 1
    assert got == []


def test_get_match_selector_skips_picker(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    # _interactive() must NOT be consulted when a selector is given
    monkeypatch.setattr(cli, "_interactive", lambda: (_ for _ in ()).throw(AssertionError("picker used")))
    got = _record_downloads(monkeypatch)

    rc = cli.cmd_get(argparse.Namespace(src="123", match="EP1", latest=None,
                                        index=None, out=str(tmp_path), no_input=False, quiet=False))
    assert rc == 0
    assert got == ["EP1"]


def test_get_no_input_flag_blocks_picker(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    got = _record_downloads(monkeypatch)

    rc = cli.cmd_get(argparse.Namespace(src="123", match=None, latest=None,
                                        index=None, out=str(tmp_path), no_input=True, quiet=False))
    assert rc == 1            # falls back to list+hint, downloads nothing
    assert got == []


def _capture_outdirs(monkeypatch):
    outs = []

    def fake_dl(ep, out, **kw):
        outs.append(out)
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, ep.title + ".mp3")
        with open(p, "wb") as f:
            f.write(b"x")
        return p

    monkeypatch.setattr(cli.core, "download_episode", fake_dl)
    return outs


def test_get_multiple_episodes_go_in_show_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())  # title "Demo Show"
    outs = _capture_outdirs(monkeypatch)

    rc = cli.cmd_get(argparse.Namespace(src="123", match=None, latest=2,
                                        index=None, out=str(tmp_path), no_input=True, quiet=False))
    assert rc == 0
    expected = os.path.join(str(tmp_path), "Demo Show")
    assert outs == [expected, expected]          # both into the show subfolder


def test_get_single_episode_no_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: _show())
    outs = _capture_outdirs(monkeypatch)

    rc = cli.cmd_get(argparse.Namespace(src="123", match=None, latest=1,
                                        index=None, out=str(tmp_path), no_input=True, quiet=False))
    assert rc == 0
    assert outs == [str(tmp_path)]               # single -> straight into out dir


def test_get_quiet_skips_picker_and_progress(monkeypatch, tmp_path):
    show = _show()
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: show)
    monkeypatch.setattr(cli, "_interactive",
                        lambda: (_ for _ in ()).throw(AssertionError("picker used")))
    got = _record_downloads(monkeypatch)

    buf = io.StringIO()
    monkeypatch.setattr(cli, "ui", Console(file=buf, stderr=True))

    rc = cli.cmd_get(argparse.Namespace(src="123", match="EP1", latest=None, index=None,
                                        out=str(tmp_path), no_input=False, quiet=True))

    assert rc == 0
    assert got == ["EP1"]
    assert buf.getvalue() == ""


def test_get_quiet_continues_after_one_failure(monkeypatch, tmp_path):
    show = _show()
    monkeypatch.setattr(cli.core, "classify", lambda s: ("apple_show", s))
    monkeypatch.setattr(cli, "_resolve_show", lambda kind, s, args=None: show)

    def fake_dl(ep, out, **kw):
        if ep.title == "EP1":
            raise RuntimeError("boom")
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, ep.title + ".mp3")
        with open(p, "wb") as f:
            f.write(b"x")
        return p

    monkeypatch.setattr(cli.core, "download_episode", fake_dl)

    rc = cli.cmd_get(argparse.Namespace(src="123", match=None, latest=3, index=None,
                                        out=str(tmp_path), no_input=True, quiet=True))
    assert rc == 0
    show_dir = os.path.join(str(tmp_path), "Demo Show")
    assert os.path.exists(os.path.join(show_dir, "EP0.mp3"))
    assert os.path.exists(os.path.join(show_dir, "EP2.mp3"))
    assert not os.path.exists(os.path.join(show_dir, "EP1.mp3"))
