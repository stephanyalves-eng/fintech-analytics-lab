"""Business scenario engine (assumptions) and the separate statistical band (backtest errors).

A scenario changes drivers by relative amounts: TPV = merchants x volume/merchant x ticket, then
take rate, refund+chargeback share of fee, processing and variable cost per TPV. Scenarios are
assumptions about the business, NOT prediction intervals; the statistical band is computed apart,
from the backtest errors of the frozen champion.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from fintech_lab.p2_forecasting.pnl import pl_from_ratios

DRIVERS = ["merchants", "volume_per_merchant", "ticket", "take_rate", "refund_cb", "proc_cost",
           "var_cost"]
ZERO = dict.fromkeys(DRIVERS, 0.0)


def apply_scenario(base_tpv: pd.Series, base_ratios: pd.DataFrame, adj: dict[str, float]
                   ) -> pd.DataFrame:
    unknown = set(adj) - set(DRIVERS)
    if unknown:
        raise ValueError(f"unknown scenario drivers: {sorted(unknown)}")
    a = {**ZERO, **adj}
    mult = (1 + a["merchants"]) * (1 + a["volume_per_merchant"]) * (1 + a["ticket"])
    r = base_ratios.copy()
    r["take"] *= 1 + a["take_rate"]
    r["rc_share"] *= 1 + a["refund_cb"]
    r["proc"] *= 1 + a["proc_cost"]
    r["var"] *= 1 + a["var_cost"]
    return pl_from_ratios(base_tpv * mult, r)


def scenario_table(base_tpv: pd.Series, base_ratios: pd.DataFrame, scen: dict[str, dict]
                   ) -> pd.DataFrame:
    rows = []
    for name, adj in scen.items():
        pl = apply_scenario(base_tpv, base_ratios, adj)
        t = pl[["tpv", "fee", "rc", "inc", "proc", "var", "net", "contribution"]].sum()
        rows.append({"scenario": name, **t.to_dict()})
    return pd.DataFrame(rows)


def sensitivity(base_tpv: pd.Series, base_ratios: pd.DataFrame, step: float,
                joint: dict[str, float] | None = None) -> pd.DataFrame:
    """One-at-a-time +/- step on each driver (effect on TPV, net revenue, contribution)."""
    base = apply_scenario(base_tpv, base_ratios, {})[["tpv", "net", "contribution"]].sum()
    rows = []
    for dr in DRIVERS:
        for sign in (-1, 1):
            t = apply_scenario(base_tpv, base_ratios, {dr: sign * step})[
                ["tpv", "net", "contribution"]].sum()
            rows.append({"driver": dr, "change": sign * step, **{f"d_{k}": t[k] - base[k]
                                                                 for k in base.index}})
    out = pd.DataFrame(rows)
    if joint is not None:  # interaction = joint effect - sum of one-at-a-time effects
        tj = apply_scenario(base_tpv, base_ratios, joint)[["tpv", "net", "contribution"]].sum()
        solo = {k: sum(apply_scenario(base_tpv, base_ratios, {d: v})[[k]].sum().iloc[0] - base[k]
                       for d, v in joint.items()) for k in base.index}
        out.attrs["interaction"] = {k: float(tj[k] - base[k] - solo[k]) for k in base.index}
    return out


def statistical_band(backtest_fc: pd.DataFrame, target: str, model: str, as_of: date,
                     horizon: int, point_total: float, lo_q: float = 0.10, hi_q: float = 0.90
                     ) -> dict[str, float]:
    """Empirical band for a window-total forecast from backtest relative window-sum errors.

    e_o = (sum forecast - sum actual) / sum actual per origin; the implied actual range for a new
    point forecast P is P / (1 + e). Origins overlap, so n is an upper bound on information.
    """
    g = backtest_fc[(backtest_fc["target"] == target) & (backtest_fc["model"] == model)]
    ok = (g["origin"] + pd.Timedelta(days=horizon) <= pd.Timestamp(as_of)) & (g["step"] <= horizon)
    g = g[ok]
    e = g.groupby("origin").apply(
        lambda x: (x["yhat"].sum() - x["actual"].sum()) / x["actual"].sum(), include_groups=False)
    q_lo, q_hi = np.quantile(e, [lo_q, hi_q])
    return {"n_origins": int(len(e)), "err_q_lo": float(q_lo), "err_q_hi": float(q_hi),
            "err_min": float(e.min()), "err_max": float(e.max()),
            "implied_lo": point_total / (1 + float(q_hi)),
            "implied_hi": point_total / (1 + float(q_lo)),
            "point": point_total}


def scenarios_from_config(cfg: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {k: dict(v) for k, v in cfg["scenarios"].items()}
