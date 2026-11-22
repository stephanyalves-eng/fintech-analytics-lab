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
from datetime import UTC, datetime, timedelta
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


# ---- budget v2: run-rate reforecast at the as-of date ---------------------------------------
def calibrate_v2(monthly: pd.DataFrame, segment: pd.DataFrame, rules: dict[str, Any]
                 ) -> dict[str, Any]:
    """Level, growth and ratios by country from data dated <= as_of ONLY (inputs are filtered)."""
    from fintech_lab.p2_forecasting import pnl

    as_of = d(rules["as_of"])
    m = monthly[pd.to_datetime(monthly["month"]) <= pd.Timestamp(as_of)]
    s = segment[pd.to_datetime(segment["date_local"]) <= pd.Timestamp(as_of)]
    g0, g1 = (pd.Timestamp(d(x)) for x in rules["growth_months"])
    anchor = pd.Timestamp(d(rules["anchor_month"]))
    tpv = (m.assign(month=pd.to_datetime(m["month"]), tpv_brl=m["tpv_brl"].astype(float))
           .pivot_table(index="month", columns="country", values="tpv_brl", aggfunc="sum"))
    n_intervals = (g1.year - g0.year) * 12 + g1.month - g0.month
    growth = {c: float((tpv.loc[g1, c] / tpv.loc[g0, c]) ** (1 / n_intervals) - 1)
              for c in tpv.columns}
    base_daily = {c: float(tpv.loc[anchor, c]) / anchor.days_in_month for c in tpv.columns}
    start = as_of - timedelta(days=int(rules["ratios_window_days"]) - 1)
    r = pnl.ratios(pnl.window_pl(s, start, as_of))
    return {"base_daily_tpv_brl": {c: round(v, 2) for c, v in base_daily.items()},
            "monthly_growth": {c: round(v, 6) for c, v in growth.items()},
            "take_rate": {c: round(float(r.loc[c, "take"]), 6) for c in r.index},
            "rc_share": {c: round(float(r.loc[c, "rc_share"]), 6) for c in r.index},
            "proc_share": {c: round(float(r.loc[c, "proc"]), 6) for c in r.index},
            "rules_version": rules["version"], "data_cutoff": str(as_of)}


def build_budget_v2(frozen: dict[str, Any], rules: dict[str, Any], assumptions: dict[str, Any]
                    ) -> pd.DataFrame:
    anchor = pd.Timestamp(d(rules["anchor_month"]))
    rows = []
    for c in sorted(frozen["base_daily_tpv_brl"]):
        for mth in rules["months"]:
            t = pd.Timestamp(d(mth))
            k = (t.year - anchor.year) * 12 + t.month - anchor.month
            tpv = frozen["base_daily_tpv_brl"][c] * t.days_in_month \
                * (1 + frozen["monthly_growth"][c]) ** k
            fee = tpv * frozen["take_rate"][c]
            rc, inc = fee * frozen["rc_share"][c], tpv * assumptions["incentive_rate"]
            proc, var = tpv * frozen["proc_share"][c], tpv * assumptions["var_cost_rate"]
            net = fee - rc - inc
            rows.append((t.date(), c, tpv, frozen["take_rate"][c], fee, rc, inc, proc, var, net,
                         net - proc - var))
    df = pd.DataFrame(rows, columns=["month", "country", "tpv_brl", "take_rate", "fee_brl",
                                     "rc_brl", "inc_brl", "proc_brl", "var_brl",
                                     "net_revenue_brl", "contribution_brl"])
    df[df.columns[2:]] = df[df.columns[2:]].round(4)
    df["version"], df["as_of"] = rules["version"], str(rules["as_of"])
    return df


def freeze_v2(frozen: dict[str, Any], rules: dict[str, Any], assumptions: dict[str, Any],
              path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"{p} exists: budget v2 is frozen; create v3 instead")
    table = build_budget_v2(frozen, rules, assumptions)
    doc = {**frozen, "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "table_hash": _hash({"p": frozen, "t": table.astype(str).values.tolist()})}
    p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")
    return doc


def verify_v2(doc: dict[str, Any], rules: dict[str, Any], assumptions: dict[str, Any]) -> bool:
    keys = ("base_daily_tpv_brl", "monthly_growth", "take_rate", "rc_share", "proc_share",
            "rules_version", "data_cutoff")
    frozen = {k: doc[k] for k in keys}
    table = build_budget_v2(frozen, rules, assumptions)
    return _hash({"p": frozen, "t": table.astype(str).values.tolist()}) == doc["table_hash"]
