"""Data service for the P2 dashboard and the one-pager: pure functions, no Streamlit imports."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fintech_lab.p2_forecasting import backtest as bt
from fintech_lab.p2_forecasting.closing import run_closing
from fintech_lab.p2_forecasting.config import load_assumptions

COMPONENTS = ["tpv_brl", "fee_brl", "refund_brl", "refund_fee_returned_brl", "chargeback_brl",
              "incentive_brl", "proc_cost_brl", "var_cost_brl", "n_payments", "n_succeeded"]
METRICS = {"TPV": "tpv_brl", "Net revenue": "net_revenue_brl",
           "Contribution margin": "contribution_brl", "Fee revenue": "fee_brl"}


def _num(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in [*COMPONENTS, "net_revenue_brl", "contribution_brl", "take_rate"]:
        if c in out:
            out[c] = out[c].astype(float)
    out["date_local"] = pd.to_datetime(out["date_local"])
    return out


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Contract F08/F11 on any additive frame (sum components first, then derive)."""
    out = df.copy()
    out["net_revenue_brl"] = (out["fee_brl"] - out["refund_fee_returned_brl"]
                              - out["chargeback_brl"] - out["incentive_brl"])
    out["contribution_brl"] = out["net_revenue_brl"] - out["proc_cost_brl"] - out["var_cost_brl"]
    out["take_rate"] = out["fee_brl"] / out["tpv_brl"].where(out["tpv_brl"] != 0)
    return out


def load_bundle(data_dir: str | Path, config_dir: str | Path, reports_tmp: str | Path | None = None
                ) -> dict[str, Any]:
    data, cfgd = Path(data_dir), Path(config_dir)
    load = lambda n: yaml.safe_load((cfgd / n).read_text(encoding="utf-8"))  # noqa: E731
    assumptions = load_assumptions(cfgd / "assumptions.yaml")
    bt_cfg, scen, alerts = bt.load_cfg(cfgd / "backtest.yaml"), load("scenarios.yaml"), \
        load("alerts.yaml")
    champs_doc = load("champions_b1.yaml")
    with tempfile.TemporaryDirectory() as tmp:
        o = run_closing(data, assumptions, bt_cfg, scen, alerts, cfgd / "champions_b1.yaml",
                        reports_tmp or tmp)
        tables = {}
        if reports_tmp is None:
            tables = {p.stem: pd.read_csv(p) for p in Path(tmp).glob("*.csv")}
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    rd = pd.read_parquet
    return {
        "o": o, "tables": tables, "assumptions": assumptions, "bt_cfg": bt_cfg, "scen_cfg": scen,
        "alert_cfg": alerts, "champions": champs_doc, "manifest": manifest,
        "total": _num(rd(data / "fct_daily_total.parquet")),
        "segment": _num(rd(data / "fct_daily_segment.parquet")),
        "merchant": _num(rd(data / "fct_daily_merchant.parquet")),
        "holdout": rd(data / "backtest" / "fct_holdout_forecast.parquet"),
        "bt_fc": rd(data / "backtest" / "fct_backtest_forecast.parquet"),
        "bt_metrics": rd(data / "backtest" / "fct_backtest_metrics.parquet"),
        "budget_v1": rd(data / "budget_v1.parquet"),
        "merchant_dim": rd(data / "fct_daily_merchant.parquet")[["merchant_id", "country",
                                                                 "size_tier"]].drop_duplicates(),
    }


def history(b: dict[str, Any], start, end, countries: list[str], methods: list[str],
            tiers: list[str], merchants: list[str]) -> pd.DataFrame:
    """Daily additive history under the sidebar filters (merchant filter uses the merchant table).

    Merchant data has no payment method, so method filters are ignored when merchants are chosen;
    the caller shows that in the UI.
    """
    if merchants:
        df = b["merchant"]
        df = df[df["merchant_id"].isin(merchants)]
    else:
        df = b["segment"]
        if methods:
            df = df[df["method_code"].isin(methods)]
    if countries:
        df = df[df["country"].isin(countries)]
    if tiers:
        df = df[df["size_tier"].isin(tiers)]
    df = df[(df["date_local"] >= pd.Timestamp(start)) & (df["date_local"] <= pd.Timestamp(end))]
    g = df.groupby("date_local")[[c for c in COMPONENTS if c in df]].sum().reset_index()
    return add_derived(g)


def regrain(df: pd.DataFrame, grain: str) -> pd.DataFrame:
    """Sum components at day/week/month, then derive ratios (never average daily ratios)."""
    if grain == "Day":
        return df
    rule = {"Week": "W-SUN", "Month": "MS"}[grain]
    cols = [c for c in COMPONENTS if c in df]
    g = df.set_index("date_local")[cols].resample(rule, label="left" if grain == "Month"
                                                   else "right", closed="left" if grain == "Month"
                                                   else "right").sum().reset_index()
    return add_derived(g)


def forecast_path(b: dict[str, Any], target: str, model: str) -> pd.DataFrame:
    h = b["holdout"]
    f = h[(h["target"] == target) & (h["model"] == model)].copy()
    f["date"] = pd.to_datetime(f["date"])
    return f.sort_values("date")

