"""Load the daily target series (BRL) from the P2 mart export, optionally truncated at a date."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

TOTAL_COLUMNS = {
    "tpv_total": "tpv_brl",
    "net_revenue_total": "net_revenue_brl",
    "contribution_total": "contribution_brl",
}


def load_targets(
    data_dir: str | Path, countries: list[str], max_date: date | None = None,
) -> dict[str, pd.Series]:
    """{target: daily float Series with a DatetimeIndex (freq D)}. ``max_date`` is inclusive."""
    base = Path(data_dir)
    tot = pd.read_parquet(base / "fct_daily_total.parquet")
    seg = pd.read_parquet(base / "fct_daily_segment.parquet")
    out: dict[str, pd.Series] = {}
    tot["date_local"] = pd.to_datetime(tot["date_local"])
    tot = tot.sort_values("date_local").set_index("date_local")
    for name, col in TOTAL_COLUMNS.items():
        out[name] = tot[col].astype(float)
    seg["date_local"] = pd.to_datetime(seg["date_local"])
    by_c = seg.assign(tpv_brl=seg["tpv_brl"].astype(float)).groupby(
        ["date_local", "country"])["tpv_brl"].sum().unstack("country").sort_index()
    for c in countries:
        out[f"tpv_{c}"] = by_c[c]
    for k, s in out.items():
        if max_date is not None:
            s = s[s.index <= pd.Timestamp(max_date)]
        s = s.asfreq("D")
        if s.isna().any():
            raise ValueError(f"{k}: gaps in the daily series")
        s.name = k
        out[k] = s
    return out
