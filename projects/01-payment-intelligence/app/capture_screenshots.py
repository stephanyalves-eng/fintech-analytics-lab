"""Capture real screenshots of the RUNNING dashboard (P1.5.e) via headless Edge/Chrome + CDP.

Usage (app already running on :8501, e.g. ``python -m fintech_lab.p1_payments.cli dashboard``)::

    python projects/01-payment-intelligence/app/capture_screenshots.py [--url URL]

Writes PNGs to ``projects/01-payment-intelligence/assets/screenshots/``. Nothing is mocked:
if the app is not reachable the script fails.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets  # transitive dependency of streamlit (uvicorn)

OUT = Path(__file__).resolve().parents[1] / "assets" / "screenshots"
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
]
TABS = [
    "executive_overview",
    "authorization_declines",
    "acquirer_performance",
    "retry_recovery",
    "scenario_simulator",
    "about_the_data",
]
PORT = 9333


class CDP:
    def __init__(self, ws):
        self.ws, self.i = ws, 0

    async def __call__(self, method: str, **params):
        self.i += 1
        await self.ws.send(json.dumps({"id": self.i, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.i:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    async def js(self, expr: str):
        r = await self("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    async def settle(self, timeout: float = 90) -> None:
        """Wait until Streamlit stops running and plots have rendered."""
        t0 = time.time()
        await asyncio.sleep(1.5)
        while time.time() - t0 < timeout:
            ready = await self.js(
                "document.querySelector('[data-testid=\"stApp\"]')"
                "?.getAttribute('data-test-script-state') === 'notRunning' && "
                "document.querySelectorAll('[role=\"tab\"]').length > 0 && "
                "document.querySelectorAll('[data-testid=\"stSkeleton\"]').length === 0"
            )
            if ready:
                await asyncio.sleep(1.5)
                return
            await asyncio.sleep(0.5)
        state = await self.js(
            "JSON.stringify([location.href, document.title, "
            "document.querySelector('[data-testid=\"stApp\"]')"
            "?.getAttribute('data-test-script-state'), "
            "document.querySelectorAll('[role=\"tab\"]').length, "
            "document.querySelectorAll('[data-testid=\"stSkeleton\"]').length])"
        )
        raise TimeoutError(f"app did not settle: {state}")

    async def shot(self, path: Path) -> None:
        r = await self("Page.captureScreenshot", format="png")
        path.write_bytes(base64.b64decode(r["data"]))
        print(f"wrote {path}")


async def capture(url: str) -> None:
    exe = next((b for b in BROWSERS if Path(b).exists() or shutil.which(b)), None)
    if exe is None:
        raise SystemExit("No Edge/Chrome found")
    profile = tempfile.mkdtemp(prefix="p1shots_")
    proc = subprocess.Popen(
        [exe, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
                ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("browser did not start")
        cdp = CDP(await websockets.connect(ws_url, max_size=None))
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
        # Edge/Chrome spawn child processes: kill the whole tree.
        if sys.platform == "win32":
            subprocess.call(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )  # fmt: skip
        else:
            proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    asyncio.run(capture(ap.parse_args().url))
