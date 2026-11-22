"""Capture real screenshots of the RUNNING dashboard (P1.5.e) via headless Edge/Chrome + CDP.

Usage (app already running on :8501, e.g. ``python -m fintech_lab.p1_payments.cli dashboard``)::

    python projects/01-payment-intelligence/app/capture_screenshots.py [--url URL]

Writes PNGs to ``projects/01-payment-intelligence/assets/screenshots/``. Nothing is mocked:
if the app is not reachable the script fails.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fintech_lab.shared.browser_cdp import CDP, close, open_page  # noqa: E402,F401

OUT = Path(__file__).resolve().parents[1] / "assets" / "screenshots"
TABS = [
    "executive_overview",
    "authorization_declines",
    "acquirer_performance",
    "retry_recovery",
    "scenario_simulator",
    "about_the_data",
]
PORT = 9333



async def capture(url: str) -> None:
    proc, profile, cdp = await open_page(PORT, "p1shots")
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        for label, w, h, mobile in (("desktop", 1440, 2300, False), ("mobile", 390, 3200, True)):
            await cdp(
                "Emulation.setDeviceMetricsOverride",
                width=w, height=h, deviceScaleFactor=1, mobile=mobile,
            )  # fmt: skip
            await cdp("Page.navigate", url=url)
            await cdp.settle()
            tabs = TABS if label == "desktop" else TABS[:1]
            for i, name in enumerate(tabs):
                tab = f"document.querySelectorAll('[role=\"tab\"]')[{i}]"
                await cdp.js(f"{tab}.click()")
                await cdp.settle()
                if await cdp.js(f"{tab}.getAttribute('aria-selected')") != "true":
                    raise RuntimeError(f"tab {name} was not selected")
                if await cdp.js("!!document.querySelector('[data-testid=\"stException\"]')"):
                    raise RuntimeError(f"app shows an exception on tab {name}; not capturing")
                await cdp.shot(OUT / f"{i + 1:02d}_{name}_{label}.png")
    finally:
        close(proc, profile)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    asyncio.run(capture(ap.parse_args().url))
