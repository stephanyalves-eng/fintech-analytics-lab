"""Automated accessibility audit (axe-core 4.10.2) of the RUNNING P3 dashboard.

Usage (app already running on :8502, e.g. ``python -m fintech_lab.p3_experiments.cli dashboard``)::

    python projects/03-experimentation-lab/app/a11y_audit.py [--url URL]

Injects the vendored, hash-pinned ``shared/vendor/axe.min.js`` into each tab (and the SRM scenario)
via headless Edge/Chrome + CDP, and writes ``reports/a11y_axe.json`` and ``reports/a11y_axe.md``.
This is an AUTOMATED check only: keyboard navigation and screen-reader behaviour stay [TO VERIFY].
Nothing is sent outside the machine. Elements injected by browser extensions
(``deepl-input-controller``) are excluded: they are not part of the app.
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

from fintech_lab.shared.browser_cdp import close, open_page  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AXE = Path(__file__).resolve().parents[3] / "shared" / "vendor" / "axe.min.js"
AXE_SHA256 = "b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3"
PORT = 9335
RUN = (
    "axe.run({exclude: [['deepl-input-controller']]}, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}})"
    ".then(r => JSON.stringify({violations: r.violations.map(v => ({id: v.id, impact: v.impact,"
    " help: v.help, nodes: v.nodes.length,"
    " targets: v.nodes.map(n => ({t: n.target.join(' '), s: (n.any[0] || {}).message || '',"
    " h: n.html.slice(0, 120)}))})), passes: r.passes.length,"
    " incomplete: r.incomplete.length}))"
)


async def audit(url: str) -> list[dict]:
    src = AXE.read_bytes()
    if hashlib.sha256(src).hexdigest() != AXE_SHA256:
        raise SystemExit("axe.min.js does not match the pinned SHA-256; refusing to inject it")
    proc, profile, cdp = await open_page(PORT, "p3axe")
    out: list[dict] = []
    try:
        await cdp("Emulation.setDeviceMetricsOverride", width=1440, height=2300,
                  deviceScaleFactor=1, mobile=False)  # fmt: skip
        await cdp("Page.navigate", url=url)
        await cdp.settle()
        await cdp.js(src.decode("utf-8"))
        if not await cdp.js("typeof axe !== 'undefined'"):
            raise RuntimeError("axe-core did not load")

        async def run(label: str) -> None:
            r = json.loads(await cdp.js(RUN))
            out.append({"view": label, **r})
            print(f"{label:34} violations={len(r['violations'])} incomplete={r['incomplete']}")

        for i, name in enumerate(TABS):
            await cdp.js(f"document.querySelectorAll('[role=\"tab\"]')[{i}].click()")
            await cdp.settle()
            await run(f"positive/{name}")
        await cdp.js("[...document.querySelectorAll('label')].find(l => l.innerText.trim()"
                     " === 'srm').click()")
        await cdp.settle()
        await cdp.js("document.querySelectorAll('[role=\"tab\"]')[4].click()")
        await cdp.settle()
        if not await cdp.js("typeof axe !== 'undefined'"):  # rerun may reload the page
            await cdp.js(src.decode("utf-8"))
        await run("srm/data_quality")
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
            a.setdefault("nodes", []).extend(t["t"] for t in v.get("targets", []))
    L = ["# Auditoria de acessibilidade automática (axe-core 4.10.2)", "",
         "> Regras WCAG 2.0/2.1 A e AA, sobre o app rodando (dados sintéticos). **Só checagem "
         "automática**: navegação por teclado e leitor de tela seguem [TO VERIFY] (teste manual).",
         "", f"Telas analisadas: {len(results)}. Itens `incomplete` (revisão manual) por tela: "
         + ", ".join(f"{r['view']}={r['incomplete']}" for r in results), ""]
    if agg:
        L += ["| Regra | Impacto | Descrição | Telas (nós) |", "|---|---|---|---|"]
        L += [f"| `{k}` | {v['impact']} | {v['help']} | {'; '.join(v['views'])} |"
              for k, v in sorted(agg.items())]
    else:
        L.append("Nenhuma violação encontrada pelas regras automáticas.")
    (rep / "a11y_axe.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8502")
    write_reports(asyncio.run(audit(ap.parse_args().url)))
