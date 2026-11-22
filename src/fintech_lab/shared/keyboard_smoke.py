"""Automated keyboard smoke test of a RUNNING dashboard (partial evidence, not an a11y sign-off).

    python -m fintech_lab.shared.keyboard_smoke --url http://localhost:8503 --out reports/keyboard_smoke.md

It presses Tab repeatedly in headless Edge/Chrome (no blur/refocus tricks that could change the
focus order) and reports: how many visible controls are reached with Tab and which candidates are
not, whether focus ever gets stuck (keyboard trap), whether the focused element (or one of 5
ancestors) changes outline/shadow/border/background compared with its state before any key press (a
heuristic for a visible focus indicator), and whether the arrow keys move between tabs. Tabs and
radio groups use arrow keys by design (roving tabindex) and are checked separately. A screen-reader
pass and a human keyboard pass remain [TO VERIFY].
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from fintech_lab.shared.browser_cdp import close, open_page

CANDIDATES = (
    "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), "
    "select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1']), "
    "[role=combobox], [role=tab], [role=radio], [role=button]"
)
SIG = """const sig = el => { const out = []; let n = el, d = 0;
  while (n && d < 6) { const s = getComputedStyle(n);
    out.push([s.outlineStyle, s.outlineWidth, s.boxShadow, s.borderTopColor, s.borderBottomColor,
              s.backgroundColor, s.textDecorationLine].join('/')); n = n.parentElement; d++; }
  return out.join('|'); };"""
INIT = f"""(() => {{
  {SIG}
  const vis = e => {{ const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; }};
  const all = [...document.querySelectorAll({json.dumps(CANDIDATES)})].filter(vis);
  window.__kb = {{ base: new WeakMap(), visited: new WeakSet(), all: all }};
  all.forEach(e => window.__kb.base.set(e, sig(e)));
  const roving = all.filter(e => ['tab', 'radio'].includes(e.getAttribute('role')) ||
                                 e.type === 'radio');
  return {{total: all.length, roving: roving.length, tabbable: all.length - roving.length}};
}})()"""
DESCRIBE = f"""(() => {{
  {SIG}
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  window.__kb.visited.add(e);
  const r = e.getBoundingClientRect();
  const base = window.__kb.base.get(e);
  const name = (e.getAttribute('aria-label') || e.innerText || e.value || e.placeholder ||
                e.getAttribute('title') || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
  return {{id: e.tagName + '|' + (e.getAttribute('role') || '') + '|' + name + '|' +
               Math.round(r.x) + ',' + Math.round(r.y),
          tag: e.tagName.toLowerCase(), role: e.getAttribute('role') || '', name: name,
          w: Math.round(r.width), h: Math.round(r.height),
          indicator: base === undefined ? null : sig(e) !== base}};
}})()"""
UNREACHED = """(() => {
  const out = [];
  for (const e of window.__kb.all) {
    const role = e.getAttribute('role');
    if (['tab', 'radio'].includes(role) || e.type === 'radio') continue;
    if (!window.__kb.visited.has(e)) {
      out.push(e.tagName.toLowerCase() + '[' + (role || '') + '] ' +
               (e.getAttribute('aria-label') || e.innerText || e.placeholder || '').trim()
               .replace(/\\s+/g, ' ').slice(0, 40) + ' tabindex=' + e.getAttribute('tabindex'));
    }
  }
  return out;
})()"""


async def smoke(url: str, port: int = 9338) -> dict:
    proc, profile, cdp = await open_page(port, "kbsmoke")
    try:
        await cdp("Emulation.setDeviceMetricsOverride", width=1440, height=1400,
                  deviceScaleFactor=1, mobile=False)
        await cdp("Page.navigate", url=url)
        await cdp.settle()
        # no CSS transitions, so style comparisons are not caught mid-animation
        await cdp.js("document.head.appendChild(Object.assign(document.createElement('style'), "
                     "{textContent: '*{transition:none !important;animation:none !important}'}))")
        counts = await cdp.js(INIT)
        seen: dict[str, dict] = {}
        stuck = trap = 0
        trap_id = ""
        last = None
        presses = min(400, counts["total"] * 2 + 40)
        for _ in range(presses):
            await cdp.press("Tab", "Tab", 9)
            d = await cdp.js(DESCRIBE)
            if d is None:
                continue
            seen.setdefault(d["id"], d)
            stuck = stuck + 1 if d["id"] == last else 0
            if stuck > trap:
                trap, trap_id = stuck, d["name"] or d["tag"]
            last = d["id"]
        unreached = await cdp.js(UNREACHED)
        arrow_ok = None
        if await cdp.js("!!document.querySelector('[role=tab][aria-selected=true]')"):
            await cdp.js("document.querySelector('[role=tab][aria-selected=true]').focus()")
            before = await cdp.js(DESCRIBE)
            await cdp.press("ArrowRight", "ArrowRight", 39)
            after = await cdp.js(DESCRIBE)
            arrow_ok = bool(before and after and before["id"] != after["id"])
        no_ind = [v for v in seen.values() if v["indicator"] is False]
        unknown = [v for v in seen.values() if v["indicator"] is None]
        return {"url": url, "counts": counts, "presses": presses, "distinct_stops": len(seen),
                "max_consecutive_same_focus": trap, "max_run_element": trap_id,
                "tab_arrow_navigation": arrow_ok,
                "unreached": unreached,
                "stops_without_indicator": [f"{v['tag']}[{v['role']}] {v['name']}" for v in no_ind],
                "stops_indicator_unknown": len(unknown),
                "zero_size_stops": [f"{v['tag']} {v['name']}" for v in seen.values()
                                    if v["w"] == 0 or v["h"] == 0],
                "first_stops": [f"{v['tag']}[{v['role']}] {v['name']}" for v in seen.values()][:12]}
    finally:
        close(proc, profile)


TRAP_LIMIT = 25  # data grids (canvas) use Tab to walk across cells, so short runs are expected


def write_report(res: dict, out: Path, name: str) -> None:
    ok_trap = res["max_consecutive_same_focus"] < TRAP_LIMIT
    c = res["counts"]
    ni = res["stops_without_indicator"]
    lines = [
        f"# Keyboard smoke test — {name} (automated, partial)", "",
        "> Automated Tab/arrow-key probe in headless Edge/Chrome against the running app "
        "(synthetic data). It is **not** an accessibility sign-off: a human keyboard pass and a "
        "screen-reader pass remain [TO VERIFY].", "",
        f"- Visible interactive candidates on the first tab: {c['total']} ({c['tabbable']} expected "
        f"via Tab, {c['roving']} in arrow-key groups: tabs and radios).",
        f"- Tab presses: {res['presses']}; distinct focus stops: {res['distinct_stops']}; "
        f"candidates never focused by Tab: {len(res['unreached'])}"
        + (" — " + "; ".join(res["unreached"][:8]) if res["unreached"] else "") + ".",
        f"- Keyboard trap (same element keeps focus for {TRAP_LIMIT}+ consecutive Tab presses): "
        f"{'none' if ok_trap else 'DETECTED'}. Longest run: {res['max_consecutive_same_focus']} "
        f"extra presses on `{res['max_run_element'] or '-'}` (Streamlit data grids are canvases that "
        "use Tab to move across cells and then release focus; runs ≈ column count are expected).",
        f"- ArrowRight moves focus between tabs: {res['tab_arrow_navigation']}.",
        f"- Stops with zero size: {len(res['zero_size_stops'])}.",
        f"- Stops with NO style change versus the pre-interaction state on the element or 5 "
        f"ancestors (heuristic for a missing focus indicator; false negatives possible): {len(ni)}"
        + (" — " + "; ".join(ni[:8]) if ni else "") + ".",
        "", "First stops: " + "; ".join(res["first_stops"]) + ".",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="dashboard")
    ap.add_argument("--port", type=int, default=9338)
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on a keyboard trap, a zero-size stop or broken arrow navigation")
    a = ap.parse_args()
    r = asyncio.run(smoke(a.url, a.port))
    write_report(r, Path(a.out), a.name)
    print(json.dumps({k: v for k, v in r.items() if k != "first_stops"}, indent=2))
    if a.strict and (r["max_consecutive_same_focus"] >= TRAP_LIMIT or r["zero_size_stops"]
                     or r["tab_arrow_navigation"] is False):
        raise SystemExit(1)
