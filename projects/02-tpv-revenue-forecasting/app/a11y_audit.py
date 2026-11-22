"""Automated accessibility audit (axe-core 4.10.2) of the RUNNING P2 dashboard.

Usage (app on :8503)::

    python projects/02-tpv-revenue-forecasting/app/a11y_audit.py [--url URL]

Injects the vendored, hash-pinned ``shared/vendor/axe.min.js`` into each tab via headless
Edge/Chrome + CDP and writes ``reports/a11y_axe.json`` and ``reports/a11y_axe.md``. AUTOMATED only:
keyboard navigation and screen-reader behaviour stay [TO VERIFY]. Elements injected by browser
extensions (``deepl-input-controller``) are excluded.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_screenshots import TABS  # noqa: E402

AXE_SHA256 = "b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3"
RUN = (
    "axe.run({exclude: [['deepl-input-controller']]}, {runOnly: {type: 'tag', values: "
    "['wcag2a','wcag2aa','wcag21a','wcag21aa']}}).then(r => JSON.stringify({violations: "
    "r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, "
    "targets: v.nodes.map(n => ({t: n.target.join(' '), s: (n.any[0] || {}).message || '', "
    "h: n.html.slice(0, 120)}))})), "
    "passes: r.passes.length, incomplete: r.incomplete.length}))"
)

from fintech_lab.shared.browser_cdp import close, open_page  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AXE = Path(__file__).resolve().parents[3] / "shared" / "vendor" / "axe.min.js"
PORT = 9337


async def audit(url: str) -> list[dict]:
    src = AXE.read_bytes()
    if hashlib.sha256(src).hexdigest() != AXE_SHA256:
        raise SystemExit("axe.min.js does not match the pinned SHA-256; refusing to inject it")
    proc, profile, cdp = await open_page(PORT, "p2axe")
    out: list[dict] = []
    try:
        await cdp("Emulation.setDeviceMetricsOverride", width=1440, height=2400,
                  deviceScaleFactor=1, mobile=False)
        await cdp("Page.navigate", url=url)
        await cdp.settle()
        await cdp.js(src.decode("utf-8"))
        if not await cdp.js("typeof axe !== 'undefined'"):
            raise RuntimeError("axe-core did not load")
        for i, name in enumerate(TABS):
            await cdp.js(f"document.querySelectorAll('[role=\"tab\"]')[{i}].click()")
            await cdp.settle()
            r = json.loads(await cdp.js(RUN))
            out.append({"view": name, **r})
            print(f"{name:22} violations={len(r['violations'])} incomplete={r['incomplete']}")
    finally:
        close(proc, profile)
    return out


def write_reports(results: list[dict]) -> None:
    rep = ROOT / "reports"
    (rep / "a11y_axe.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8",
                                       newline="\n")
    agg: dict[str, dict] = {}
    for r in results:
        for v in r["violations"]:
            a = agg.setdefault(v["id"], {"impact": v["impact"], "help": v["help"], "views": []})
            a["views"].append(f"{r['view']} ({v['nodes']})")
    lines = ["# Automated accessibility audit (axe-core 4.10.2)", "",
             "> WCAG 2.0/2.1 A and AA rules on the running app (synthetic data). **Automated check "
             "only**: keyboard navigation and screen-reader behaviour stay [TO VERIFY].", "",
             f"Views analysed: {len(results)}. `incomplete` items (manual review) per view: "
             + ", ".join(f"{r['view']}={r['incomplete']}" for r in results), ""]
    if agg:
        lines += ["| Rule | Impact | Description | Views (nodes) |", "|---|---|---|---|"]
        lines += [f"| `{k}` | {v['impact']} | {v['help']} | {'; '.join(v['views'])} |"
                  for k, v in sorted(agg.items())]
    else:
        lines.append("No violations found by the automated rules.")
    (rep / "a11y_axe.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8503")
    write_reports(asyncio.run(audit(ap.parse_args().url)))
