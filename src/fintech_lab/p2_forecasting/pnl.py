"""Country-level P&L frames (BRL) used by the bridge and the scenario engine.

Columns: tpv, fee, rc (refund fee returned + chargeback), inc (incentives), proc (processing cost),
var (other variable cost). net = fee - rc - inc; contribution = net - proc - var (contract F08/F11).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

LINES = ["tpv", "fee", "rc", "inc", "proc", "var"]
COUNTRIES = ["BR", "CL", "MX"]


def with_derived(pl: pd.DataFrame) -> pd.DataFrame:
    out = pl.copy()
    out["net"] = out["fee"] - out["rc"] - out["inc"]
    out["contribution"] = out["net"] - out["proc"] - out["var"]
    return out


def _agg(df: pd.DataFrame) -> pd.DataFrame:
    g = df.assign(
        rc=df["refund_fee_returned_brl"].astype(float) + df["chargeback_brl"].astype(float)
    ).rename(columns={"tpv_brl": "tpv", "fee_brl": "fee", "incentive_brl": "inc",
                      "proc_cost_brl": "proc", "var_cost_brl": "var"})
    g = g.assign(**{c: g[c].astype(float) for c in ("tpv", "fee", "inc", "proc", "var")})
    return g.groupby("country")[LINES].sum().reindex(COUNTRIES)


def actual_pl(monthly: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    m = pd.to_datetime(monthly["month"])
    return with_derived(_agg(monthly[(m >= pd.Timestamp(start)) & (m <= pd.Timestamp(end))]))


def window_pl(segment: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Daily-segment data summed per country over [start, end] (local dates)."""
    dl = pd.to_datetime(segment["date_local"])
    return with_derived(_agg(segment[(dl >= pd.Timestamp(start)) & (dl <= pd.Timestamp(end))]))


def budget_pl(budget: pd.DataFrame, assumptions: dict[str, Any], start: date, end: date
              ) -> pd.DataFrame:
    """Budget lines rebuilt from tpv and fee with the budget's own ratios (assumptions.yaml)."""
    m = pd.to_datetime(budget["month"])
    b = budget[(m >= pd.Timestamp(start)) & (m <= pd.Timestamp(end))]
    g = b.groupby("country")[["tpv_brl", "fee_brl"]].sum().reindex(COUNTRIES)
    bud = assumptions["budget"]
    pl = pd.DataFrame({
        "tpv": g["tpv_brl"], "fee": g["fee_brl"],
        "rc": g["fee_brl"] * bud["refund_chargeback_share_of_fee"],
        "inc": g["tpv_brl"] * assumptions["incentive_rate"],
        "proc": g["tpv_brl"] * bud["processing_cost_share_of_tpv"],
        "var": g["tpv_brl"] * assumptions["var_cost_rate"],
    })
    return with_derived(pl)


def ratios(pl: pd.DataFrame) -> pd.DataFrame:
    """Driver ratios per country: take, rc_share (of fee), inc, proc, var (of TPV)."""
    return pd.DataFrame({
        "take": pl["fee"] / pl["tpv"], "rc_share": pl["rc"] / pl["fee"],
        "inc": pl["inc"] / pl["tpv"], "proc": pl["proc"] / pl["tpv"], "var": pl["var"] / pl["tpv"],
    })


def pl_from_ratios(tpv: pd.Series, r: pd.DataFrame) -> pd.DataFrame:
    fee = tpv * r["take"]
    return with_derived(pd.DataFrame({
        "tpv": tpv, "fee": fee, "rc": fee * r["rc_share"], "inc": tpv * r["inc"],
        "proc": tpv * r["proc"], "var": tpv * r["var"]}))


def trailing_window(as_of: date, days: int) -> tuple[date, date]:
    return as_of - timedelta(days=days - 1), as_of
