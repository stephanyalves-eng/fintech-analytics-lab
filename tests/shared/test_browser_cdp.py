from __future__ import annotations

from fintech_lab.shared import browser_cdp as b
from fintech_lab.shared import keyboard_smoke as k


def test_find_browser_prefers_env_override(monkeypatch, tmp_path):
    exe = tmp_path / "my-browser"
    exe.write_text("x")
    monkeypatch.setenv("FAL_BROWSER", str(exe))
    assert b.find_browser() == str(exe)


def test_find_browser_returns_none_when_nothing_is_available(monkeypatch):
    monkeypatch.delenv("FAL_BROWSER", raising=False)
    monkeypatch.setattr(b, "KNOWN_PATHS", [])
    monkeypatch.setattr(b, "NAMES", [])
    assert b.find_browser() is None


def test_find_browser_ignores_a_bad_override(monkeypatch):
    monkeypatch.setenv("FAL_BROWSER", "definitely-not-a-browser-xyz")
    monkeypatch.setattr(b, "KNOWN_PATHS", [])
    monkeypatch.setattr(b, "NAMES", [])
    assert b.find_browser() is None


def _res(trap=0, ni=None, unreached=None):
    return {"counts": {"total": 10, "tabbable": 8, "roving": 2}, "presses": 30,
            "distinct_stops": 7, "max_consecutive_same_focus": trap, "max_run_element": "canvas",
            "tab_arrow_navigation": True, "unreached": unreached or [], "zero_size_stops": [],
            "stops_without_indicator": ni or [], "stops_indicator_unknown": 0,
            "first_stops": ["a[] Skip"]}


def test_keyboard_report_flags_traps_only_above_the_grid_threshold(tmp_path):
    out = tmp_path / "r.md"
    k.write_report(_res(trap=9), out, "x")
    assert "none" in out.read_text(encoding="utf-8").split("Keyboard trap")[1][:120]
    k.write_report(_res(trap=k.TRAP_LIMIT), out, "x")
    assert "DETECTED" in out.read_text(encoding="utf-8")


def test_keyboard_report_lists_unreached_and_states_it_is_not_a_signoff(tmp_path):
    out = tmp_path / "r.md"
    k.write_report(_res(ni=["button[] Foo"], unreached=["div[] Bar"]), out, "x")
    text = out.read_text(encoding="utf-8")
    assert "not** an accessibility sign-off" in text and "[TO VERIFY]" in text
    assert "button[] Foo" in text and "div[] Bar" in text
