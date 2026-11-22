"""Independent audit of P2 (P2.5.e): recompute key numbers from the RAW P1 Parquet with plain pandas
(no DuckDB, no P2 SQL) and compare with the exported artifacts. Findings are reported, never fixed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from fintech_lab.p2_forecasting import metrics as M

Check = tuple[str, bool, str]


def _f(x: pd.Series) -> pd.Series:
    return x.astype(float)


def raw_daily(p1_data: str | Path, start: str, end: str) -> pd.DataFrame:
    """Per payment (succeeded, local date in window): tpv_brl, fee_brl; plus attempt cost by date."""
    p1 = Path(p1_data)
    pay = pd.read_parquet(p1 / "fact_payment.parquet")
    mer = pd.read_parquet(p1 / "dim_merchant.parquet")[["merchant_id", "country", "timezone"]]
    fx = pd.read_parquet(p1 / "dim_fx_rate.parquet")
    st = pd.read_parquet(p1 / "fact_settlement.parquet")[["payment_id", "fee"]]
    att = pd.read_parquet(p1 / "fact_attempt.parquet")[["payment_id", "processing_cost"]]
    pay = pay.merge(mer, on="merchant_id")
    parts = []
    for tz, g in pay.groupby("timezone"):
        g = g.copy()
        g["local"] = g["created_at_utc"].dt.tz_localize("UTC").dt.tz_convert(tz).dt.tz_localize(None)
        parts.append(g)
    pay = pd.concat(parts)
    pay["date_local"] = pay["local"].dt.normalize()
    fx = fx.assign(date_local=pd.to_datetime(fx["rate_date"]), rate=_f(fx["rate_to_brl"]))
    pay = pay.merge(fx[["date_local", "currency", "rate"]], on=["date_local", "currency"],
                    how="left")
    pay["tpv_brl"] = _f(pay["amount"]) * pay["rate"]
    pay = pay.merge(st, on="payment_id", how="left")
    pay["fee_brl"] = _f(pay["fee"].fillna(0)) * pay["rate"]
    cost = att.assign(c=_f(att["processing_cost"])).groupby("payment_id")["c"].sum()
    pay["proc_brl"] = pay["payment_id"].map(cost).fillna(0) * pay["rate"]
    inw = (pay["date_local"] >= pd.Timestamp(start)) & (pay["date_local"] <= pd.Timestamp(end))
    pay = pay[inw]
    ok = pay["final_status"] == "succeeded"
    pay["tpv_brl"] = pay["tpv_brl"].where(ok, 0.0)
    pay["fee_brl"] = pay["fee_brl"].where(ok, 0.0)
    return pay


def run_audit(p1_data: str | Path, data_dir: str | Path, config_dir: str | Path,
              reports_dir: str | Path | None = None) -> list[Check]:
    data, cfgd = Path(data_dir), Path(config_dir)
    load = lambda n: yaml.safe_load((cfgd / n).read_text(encoding="utf-8"))  # noqa: E731
    cfg, bt, champs_doc = load("assumptions.yaml"), load("backtest.yaml"), load("champions_b1.yaml")
    man = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    as_of = pd.Timestamp(bt["as_of"])
    w0, w1 = cfg["window"]["start"], cfg["window"]["end"]
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, bool(ok), detail))

    # A1 raw P1 -> mart totals --------------------------------------------------------------
    raw = raw_daily(p1_data, w0, w1)
    tot = pd.read_parquet(data / "fct_daily_total.parquet")
    for name, col, rcol in (("A1a TPV", "tpv_brl", "tpv_brl"), ("A1b fee", "fee_brl", "fee_brl")):
        a, b = float(_f(tot[col]).sum()), float(raw[rcol].sum())
        add(f"{name}: raw pandas vs mart (year)", abs(a - b) <= 1e-6 * max(1, abs(b)),
            f"mart {a:,.2f} vs raw {b:,.2f}")
    a, b = float(_f(tot["proc_cost_brl"]).sum()), float(raw["proc_brl"].sum())
    add("A1c processing cost: raw vs mart (year)", abs(a - b) <= 1e-4 * max(1, b),
        f"mart {a:,.2f} vs raw {b:,.2f}")
    t4 = raw[(raw["date_local"] > as_of)]
    t4m = tot[pd.to_datetime(tot["date_local"]) > as_of]
    add("A1d TPV T4: raw vs mart", abs(float(t4["tpv_brl"].sum()) - float(_f(t4m["tpv_brl"]).sum()))
        <= 1e-6 * float(t4["tpv_brl"].sum()), f"raw {t4['tpv_brl'].sum():,.2f}")
    byc = raw.groupby("country")["tpv_brl"].sum()
    seg = pd.read_parquet(data / "fct_daily_segment.parquet")
    segc = _f(seg["tpv_brl"]).groupby(seg["country"]).sum()
    add("A1e TPV by country: raw vs mart",
        all(abs(byc[c] - segc[c]) <= 1e-6 * byc[c] for c in byc.index),
        ", ".join(f"{c} {byc[c]:,.0f}" for c in byc.index))

    # A2/A3 budgets recomputed from raw data -----------------------------------------------
    b1 = load("budget_v1.yaml")
    jan = raw[(raw["date_local"] >= "2025-01-01") & (raw["date_local"] <= "2025-01-31")]
    base = jan.groupby("country")["tpv_brl"].sum() / 31
    take = jan.groupby("country")["fee_brl"].sum() / jan.groupby("country")["tpv_brl"].sum()
    # the mart rounds each payment's BRL amount to cents (P1 contract) while raw floats are not, so
    # the sums may differ by at most half a cent per payment (plus a cent for the stored rounding)
    n_jan = jan[jan["tpv_brl"] > 0].groupby("country").size()
    add("A2a budget v1 base level = raw January mean daily TPV (cent-rounding bound)",
        all(abs(base[c] - b1["base_daily_tpv_brl"][c]) <= 0.005 * n_jan[c] / 31 + 0.011
            for c in base.index),
        str({c: round(float(base[c]), 2) for c in base.index}))
    add("A2b budget v1 take rate = raw January fee/TPV (4 d.p.)",
        all(abs(round(float(take[c]), 4) - b1["take_rate"][c]) < 1e-9 for c in take.index), "")
    b2 = load("budget_v2.yaml")
    sep = raw[(raw["date_local"] >= "2025-09-01") & (raw["date_local"] <= "2025-09-30")]
    apr = raw[(raw["date_local"] >= "2025-04-01") & (raw["date_local"] <= "2025-04-30")]
    g = {c: (float(sep.loc[sep.country == c, "tpv_brl"].sum()) /
             float(apr.loc[apr.country == c, "tpv_brl"].sum())) ** (1 / 5) - 1 for c in ("BR", "CL", "MX")}
    add("A3a budget v2 growth = raw Apr->Sep compound monthly growth",
        all(abs(g[c] - b2["monthly_growth"][c]) < 1e-5 for c in g), str({k: round(v, 4)
                                                                         for k, v in g.items()}))
    add("A3b budget v2 uses only data <= as-of", b2["data_cutoff"] == str(as_of.date()), "")

    # A4 backtest/holdout integrity ----------------------------------------------------------
    btf = pd.read_parquet(data / "backtest" / "fct_backtest_forecast.parquet")
    add("A4a backtest never evaluates dates after as-of",
        pd.to_datetime(btf["date"]).max() <= as_of, f"max date {pd.to_datetime(btf['date']).max()}")
    add("A4b backtest origins <= last configured origin and < as-of",
        pd.to_datetime(btf["origin"]).max() <= pd.Timestamp(bt["origins"]["last"]), "")
    mt = pd.read_parquet(data / "backtest" / "fct_backtest_metrics.parquet")
    comp = mt.pivot_table(index=["target", "model"], columns="horizon", values="wape").mean(axis=1)
    ok = True
    for tgt, rec in champs_doc["champions"].items():
        sub = comp.loc[tgt]
        base_m = sub[bt["baselines"]].idxmin()
        ok &= rec["model"] in (base_m, sub[bt["selection"]["complex"]].idxmin())
        ok &= abs(float(sub[rec["model"]]) - rec["composite_wape"]) < 1e-5
    add("A4c champions are explained by the validation composite WAPE (recomputed)", ok, "")
    ho = pd.read_parquet(data / "backtest" / "fct_holdout_forecast.parquet")
    rp = Path(reports_dir) / "holdout_t4.csv" if reports_dir else None
    rep = pd.read_csv(rp) if rp is not None and rp.exists() else None
    if rep is not None and len(rep) == len(champs_doc["champions"]):
        ok = True
        for r in rep.itertuples():
            c = ho[(ho["target"] == r.target) & (ho["model"] == champs_doc["champions"][r.target]
                                                 ["model"])]
            ok &= abs(M.wape(c["actual"], c["yhat"]) - r.wape_daily) < 1e-9
        add("A4d holdout WAPE of champions recomputed from daily rows", ok, "")
    ho_actual = ho[ho["target"] == "tpv_total"].drop_duplicates("date")["actual"].sum()
    add("A4e holdout actual TPV = raw T4 TPV", abs(ho_actual - float(t4["tpv_brl"].sum()))
        <= 1e-6 * ho_actual, f"{ho_actual:,.0f}")

    # A5 labels and determinism --------------------------------------------------------------
    origins = {t["data_origin"] for t in man["tables"].values()}
    add("A5a no table is labelled 'observed'", "observed" not in origins, str(sorted(origins)))
    add("A5b mart checks recorded as passing", all(v == 0 for v in man["checks"].values()),
        f"{len(man['checks'])} checks")
    rr = np.array([float(x) for x in pd.read_parquet(data / "fct_daily_total.parquet")
                   ["tpv_brl"]])
    add("A5c daily total has no gaps and no negative TPV", len(rr) == 365 and (rr >= 0).all(),
        f"{len(rr)} days")
    return checks


def write_report(checks: list[Check], path: str | Path) -> None:
    lines = ["# P2 independent audit", "",
             "Recomputed from the raw P1 Parquet with plain pandas (no DuckDB/SQL of P2). "
             "Findings are reported, not fixed.", "", "| check | result | detail |", "|---|---|---|"]
    lines += [f"| {n} | {'PASS' if ok else 'FAIL'} | {d} |" for n, ok, d in checks]
    lines += ["", f"**{sum(ok for _, ok, _ in checks)}/{len(checks)} passed.**"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

