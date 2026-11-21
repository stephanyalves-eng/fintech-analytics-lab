"""Deterministic, sticky user -> arm assignment from the locked protocol (SHA-256 buckets)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

import numpy as np


def bucket(user_id: str, salt: str, buckets: int = 10_000) -> int:
    digest = hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()
    return int(digest[:15], 16) % buckets


def arm_for_bucket(b: int, protocol: dict[str, Any]) -> str:
    a = protocol["assignment"]
    lo, hi = a["arm_A_buckets"]
    if lo <= b <= hi:
        return "A"
    lo, hi = a["arm_B_buckets"]
    if lo <= b <= hi:
        return "B"
    raise ValueError(f"bucket {b} outside protocol ranges")


def assign(user_ids: Iterable[str], protocol: dict[str, Any]) -> np.ndarray:
    a = protocol["assignment"]
    salt, n = a["salt"], a["buckets"]
    return np.array([arm_for_bucket(bucket(u, salt, n), protocol) for u in user_ids])
