"""Headless Chromium/Edge driver over the DevTools protocol, shared by the dashboards' QA scripts.

Used by the screenshot, axe-core and keyboard-smoke scripts of P1/P2/P3. Nothing is mocked: callers
fail if the app is unreachable. The browser is found by (in order) the ``FAL_BROWSER`` environment
variable, then well-known install paths for Windows/macOS/Linux, then executable names on ``PATH``.
Only the Windows paths were exercised by the authors; Linux/macOS discovery is untested [TO VERIFY].
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets  # transitive dependency of streamlit

KNOWN_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/microsoft-edge",
]
NAMES = ["msedge", "microsoft-edge", "microsoft-edge-stable", "google-chrome",
         "google-chrome-stable", "chromium", "chromium-browser", "chrome"]


def find_browser() -> str | None:
    env = os.environ.get("FAL_BROWSER")
    if env and (Path(env).exists() or shutil.which(env)):
        return env
    for p in KNOWN_PATHS:
        if Path(p).exists():
            return p
    for n in NAMES:
        found = shutil.which(n)
        if found:
            return found
    return None


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

    async def press(self, key: str, code: str, vk: int, shift: bool = False) -> None:
        mod = 8 if shift else 0
        for typ in ("rawKeyDown", "keyUp"):
            await self("Input.dispatchKeyEvent", type=typ, key=key, code=code,
                       windowsVirtualKeyCode=vk, modifiers=mod)


async def open_page(port: int, tag: str):
    """Start a headless browser and return (proc, profile_dir, CDP). Caller must call ``close``."""
    exe = find_browser()
    if exe is None:
        raise SystemExit("No Edge/Chrome/Chromium found (set FAL_BROWSER to its path)")
    profile = tempfile.mkdtemp(prefix=f"{tag}_")
    extra = []
    if os.environ.get("CI") or os.environ.get("FAL_NO_SANDBOX"):  # containers/CI runners
        extra = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    log = Path(profile) / "browser.log"
    with open(log, "wb") as fh:
        proc = subprocess.Popen(
            [exe, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
             "--hide-scrollbars", "--force-color-profile=srgb", *extra, "about:blank"],
            stdout=fh, stderr=subprocess.STDOUT)
    for _ in range(150):  # up to ~30 s: cold starts on shared runners can be slow
        try:
            pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
            ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
            break
        except Exception:
            if proc.poll() is not None:
                break
            time.sleep(0.2)
    else:
        ws_url = None
    if ws_url is None:
        tail = log.read_text(errors="ignore")[-1500:] if log.exists() else ""
        code = proc.poll()
        close(proc, profile)
        raise SystemExit(f"browser did not start (exe={exe}, exit={code}):\n{tail}")
    return proc, profile, CDP(await websockets.connect(ws_url, max_size=None))


def close(proc: subprocess.Popen, profile: str) -> None:
    """Edge/Chrome spawn child processes: kill the whole tree."""
    if sys.platform == "win32":
        subprocess.call(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()
    shutil.rmtree(profile, ignore_errors=True)
