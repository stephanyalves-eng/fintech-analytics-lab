"""Risk alerts with transparent, configurable thresholds."""

from __future__ import annotations

from typing import Any

import pandas as pd

COLUMNS = ["alert", "scope", "value", "amber", "red", "severity", "evidence"]


def _sev(value: float, amber: float, red: float, lower_is_worse: bool = False) -> str:
    if value != value:  # NaN
        return "n/a"
    v = value if lower_is_worse else abs(value)
    if lower_is_worse:
        return "red" if v <= red else "amber" if v <= amber else "ok"
    return "red" if v >= red else "amber" if v >= amber else "ok"


def evaluate(items: list[dict[str, Any]], rules: dict[str, dict[str, float]]) -> pd.DataFrame:
    """items: {alert, scope, value, evidence[, lower_is_worse]} -> table with severities."""
    rows = []
    for it in items:
        r = rules[it["alert"]]
        low = bool(it.get("lower_is_worse", False))
        rows.append({"alert": it["alert"], "scope": it["scope"], "value": it["value"],
                     "amber": r["amber"], "red": r["red"],
                     "severity": _sev(it["value"], r["amber"], r["red"], low),
                     "evidence": it["evidence"]})
    return pd.DataFrame(rows, columns=COLUMNS)


def rel(x: float, ref: float) -> float:
    return (x - ref) / ref if ref else float("nan")
