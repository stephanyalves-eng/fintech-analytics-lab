"""T4 holdout: runs once, AFTER champions are frozen. Nothing here feeds back into selection."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from fintech_lab.p2_forecasting import metrics as M
from fintech_lab.p2_forecasting.backtest import cfg_hash
from fintech_lab.p2_forecasting.config import d
from fintech_lab.p2_forecasting.models import forecast

BUDGET_COL = {"tpv_total": "tpv_brl", "net_revenue_total": "net_revenue_brl",
              "contribution_total": "contribution_brl"}


def run_holdout(
    full_series: dict[str, pd.Series], cfg: dict[str, Any], champions_path: str | Path,
    budget: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """-> (daily forecast rows for every model, per-target T4 summary incl. budget variance)."""
    doc = yaml.safe_load(Path(champions_path).read_text(encoding="utf-8"))
    if doc["config_hash"] != cfg_hash(cfg):
        raise ValueError("backtest config changed after the champions were frozen")
    as_of = pd.Timestamp(d(cfg["as_of"]))
    h = int(cfg["max_horizon"])
    rows, summ = [], []
    bud = budget.assign(month=pd.to_datetime(budget["month"]))
    lo, hi = as_of + timedelta(days=1), as_of + timedelta(days=h)
    t4 = bud[(bud["month"] >= lo) & (bud["month"] <= hi)]
    for tgt, y in full_series.items():
        train = y[y.index <= as_of]
        actual = y[y.index > as_of].iloc[:h]
        if len(actual) < h:
            raise ValueError(f"{tgt}: fewer than {h} actual days after as_of")
        for name in cfg["models"]:
            f, _ = forecast(name, train, h, cfg)
            f = f.copy()
            f["date"], f["actual"] = actual.index, actual.to_numpy(float)
            f["target"], f["model"], f["origin"] = tgt, name, as_of
            rows.append(f.reset_index())
        champ = doc["champions"][tgt]["model"]
        fc = pd.concat(rows[-len(cfg["models"]):], ignore_index=True)
        c = fc[fc["model"] == champ]
        if tgt in BUDGET_COL:
            budget_t4 = float(t4[BUDGET_COL[tgt]].sum())
        else:
            budget_t4 = float(t4.loc[t4["country"] == tgt.split("_")[1], "tpv_brl"].sum())
        a_sum = float(actual.sum())
        summ.append({
            "target": tgt, "champion": champ,
            "actual_t4": a_sum, "forecast_t4": float(c["yhat"].sum()), "budget_t4": budget_t4,
            "forecast_err_pct": (c["yhat"].sum() - a_sum) / a_sum,
            "budget_err_pct": (budget_t4 - a_sum) / a_sum,
            "wape_daily": M.wape(c["actual"], c["yhat"]), "bias": M.bias(c["actual"], c["yhat"]),
            "cov80": M.coverage(c["actual"], c["lo80"], c["hi80"]),
            "cov95": M.coverage(c["actual"], c["lo95"], c["hi95"]),
            **{f"wape_h{k}": M.wape(c["actual"].iloc[:k], c["yhat"].iloc[:k])
               for k in cfg["horizons"]},
        })
    out = pd.concat(rows, ignore_index=True)
    return out, pd.DataFrame(summ).replace({np.inf: np.nan})

