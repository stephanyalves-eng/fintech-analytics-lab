"""Budget v1: fixed-by-date plan with a PURPOSEFUL growth/mix error (synthetic).

Two separate steps so the plan cannot drift with the realized data:
1. ``calibrate`` reads ONLY the calibration window (January) and freezes base level and take rate
   by country in ``configs/budget_v1.yaml`` (with a content hash).
2. ``build_budget`` reads only that frozen file plus the assumptions; ``verify`` rehashes it.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fintech_lab.p2_forecasting.config import DEFAULT_BUDGET, d

COLS = ["month", "country", "tpv_brl", "take_rate", "fee_brl", "net_revenue_brl",
        "contribution_brl"]


def calibrate(daily_merchant: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """Base daily TPV and take rate by country from the calibration window only."""
    lo, hi = (d(x) for x in cfg["budget"]["calibration_window"])
    dl = pd.to_datetime(daily_merchant["date_local"])
    df = daily_merchant[(dl >= pd.Timestamp(lo)) & (dl <= pd.Timestamp(hi))]
    n_days = (hi - lo).days + 1
    g = df.groupby("country")[["tpv_brl", "fee_brl"]].sum().astype(float)
    base = {c: round(float(r.tpv_brl) / n_days, 2) for c, r in g.iterrows()}
    take = {c: round(float(r.fee_brl) / float(r.tpv_brl), 4) for c, r in g.iterrows()}
    return {"base_daily_tpv_brl": base, "take_rate": take,
            "calibration_window": [str(lo), str(hi)], "calibration_rows": len(df)}


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def build_budget(frozen: dict[str, Any], cfg: dict[str, Any]) -> pd.DataFrame:
    b = cfg["budget"]
    year = d(cfg["window"]["start"]).year
    rows = []
    for country in sorted(frozen["base_daily_tpv_brl"]):
        base, take = frozen["base_daily_tpv_brl"][country], frozen["take_rate"][country]
        for m in range(1, 13):
            tpv = base * calendar.monthrange(year, m)[1] * (1 + b["monthly_growth"]) ** (m - 1)
            fee = tpv * take
            net = fee * (1 - b["refund_chargeback_share_of_fee"]) - tpv * cfg["incentive_rate"]
            contrib = net - tpv * b["processing_cost_share_of_tpv"] - tpv * cfg["var_cost_rate"]
            rows.append((pd.Timestamp(year, m, 1).date(), country, round(tpv, 2), take,
                         round(fee, 2), round(net, 2), round(contrib, 2)))
    df = pd.DataFrame(rows, columns=COLS)
    df["version"], df["as_of"] = b["version"], str(b["as_of"])
    return df


def freeze(frozen: dict[str, Any], cfg: dict[str, Any], path: str | Path = DEFAULT_BUDGET) -> dict:
    """Write the frozen budget parameters + table hash. Refuses to overwrite an existing file."""
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"{p} already exists: budget v1 is fixed; create v2 instead")
    table = build_budget(frozen, cfg)
    doc = {**frozen, "version": cfg["budget"]["version"], "as_of": str(cfg["budget"]["as_of"]),
           "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "table_hash": _hash({"p": frozen, "t": table.astype(str).values.tolist()})}
    p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")
    return doc


def load_frozen(path: str | Path = DEFAULT_BUDGET) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def verify(doc: dict[str, Any], cfg: dict[str, Any]) -> bool:
    """R10: the budget table still hashes to the value recorded when it was frozen."""
    frozen = {k: doc[k] for k in ("base_daily_tpv_brl", "take_rate", "calibration_window",
                                  "calibration_rows")}
    table = build_budget(frozen, cfg)
    return _hash({"p": frozen, "t": table.astype(str).values.tolist()}) == doc["table_hash"]
