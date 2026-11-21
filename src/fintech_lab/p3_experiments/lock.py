"""Protocol lock: SHA-256 of the preregistered files, verified before any analysis.

Hashes are computed on LF-normalised text so a Windows CRLF checkout does not break them.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from fintech_lab.p3_experiments.power import P3_ROOT

LOCKED_FILES = ("configs/protocol.yaml", "docs/protocol.md", "reports/sample_size.csv")
LOCK_PATH = P3_ROOT / "configs" / "protocol.lock.json"


class ProtocolLockError(RuntimeError):
    """Protocol missing, unlocked or changed since locking."""


def file_hash(path: Path) -> str:
    text = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(text).hexdigest()


def current_hashes(root: Path = P3_ROOT, files: tuple[str, ...] = LOCKED_FILES) -> dict[str, str]:
    missing = [f for f in files if not (root / f).exists()]
    if missing:
        raise ProtocolLockError(f"missing protocol files: {missing}")
    return {f: file_hash(root / f) for f in files}


def write_lock(
    root: Path = P3_ROOT,
    lock_path: Path = LOCK_PATH,
    amend_reason: str | None = None,
    files: tuple[str, ...] = LOCKED_FILES,
    now: datetime | None = None,
) -> dict:
    """Create the lock; changing an existing lock requires an explicit amendment reason."""
    hashes = current_hashes(root, files)
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if lock_path.exists():
        old = json.loads(lock_path.read_text(encoding="utf-8"))
        if old["files"] == hashes:
            return old
        if not amend_reason:
            raise ProtocolLockError(
                "protocol changed since locking; re-lock only with an amendment reason"
            )
        amendments = old.get("amendments", []) + [
            {"at": stamp, "reason": amend_reason, "previous_files": old["files"]}
        ]
        lock = {**old, "files": hashes, "amendments": amendments}
    else:
        lock = {"locked_at": stamp, "algorithm": "sha256-lf", "files": hashes, "amendments": []}
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock


def verify_lock(root: Path = P3_ROOT, lock_path: Path = LOCK_PATH) -> dict:
    """Raise ProtocolLockError unless every locked file matches its recorded hash."""
    if not lock_path.exists():
        raise ProtocolLockError("protocol is not locked; run `cli lock` before any analysis")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    actual = current_hashes(root, tuple(lock["files"]))
    changed = [f for f, h in lock["files"].items() if actual[f] != h]
    if changed:
        raise ProtocolLockError(f"protocol files changed since lock: {changed}")
    return lock
