"""Capture REAL screenshots of the RUNNING P2 dashboard (P2.5.e) via headless Edge/Chrome + CDP.

Usage (app already running on :8503, e.g. ``python -m fintech_lab.p2_forecasting.cli dashboard``)::

    python projects/02-tpv-revenue-forecasting/app/capture_screenshots.py [--url URL]

Writes PNGs to ``projects/02-tpv-revenue-forecasting/assets/screenshots/``. Nothing is mocked: if
the app is unreachable or shows an exception, the script fails. It reuses the small CDP helper of
the P3 capture script.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fintech_lab.shared.browser_cdp import CDP, close, open_page  # noqa: E402,F401

OUT = Path(__file__).resolve().parents[1] / "assets" / "screenshots"
TABS = ["closing", "history", "forecast_intervals", "models", "scenarios", "variance_bridge",
        "risk_alerts", "about_export"]
PORT = 9336


async def _no_exception(cdp: CDP, where: str) -> None:
    if await cdp.js("!!document.querySelector('[data-testid=\"stException\"]')"):
        raise RuntimeError(f"app shows an exception on {where}; not capturing")


async def capture(url: str) -> None:
    proc, profile, cdp = await open_page(PORT, "p2shots")
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        for label, w, h, mobile in (("desktop", 1440, 2400, False), ("mobile", 390, 3400, True)):
            await cdp("Emulation.setDeviceMetricsOverride", width=w, height=h,
                      deviceScaleFactor=1, mobile=mobile)
            await cdp("Page.navigate", url=url)
            await cdp.settle()
            idx = range(len(TABS)) if label == "desktop" else (0, 5)
            for i in idx:
                tab = f"document.querySelectorAll('[role=\"tab\"]')[{i}]"
                await cdp.js(f"{tab}.click()")
                await cdp.settle()
                if await cdp.js(f"{tab}.getAttribute('aria-selected')") != "true":
                    raise RuntimeError(f"tab {TABS[i]} was not selected")
                await _no_exception(cdp, TABS[i])
                await cdp.shot(OUT / f"{i + 1:02d}_{TABS[i]}_{label}.png")
            if label == "desktop":  # a real filtered state: monthly grain on the History tab
                await cdp.js("document.querySelectorAll('[role=\"tab\"]')[1].click()")
                await cdp.settle()
                await cdp.js("[...document.querySelectorAll('label')]"
                             ".find(l => l.innerText.trim() === 'Month').click()")
                await cdp.settle()
                await _no_exception(cdp, "history/month")
                await cdp.shot(OUT / "09_history_month_desktop.png")
    finally:
        close(proc, profile)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8503")
    asyncio.run(capture(ap.parse_args().url))
