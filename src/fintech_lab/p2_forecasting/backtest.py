"""Rolling-origin backtest (validation only), summary metrics and champion selection.

Leakage rules: actuals are loaded truncated at ``as_of`` (T4 is never read here); at each origin a
model receives only ``y[:origin]``; the future actuals are joined AFTER forecasting.
"""

from __future__ import annotations

import hashlib
import math
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from fintech_lab.p2_forecasting import metrics as M
from fintech_lab.p2_forecasting.config import d
from fintech_lab.p2_forecasting.models import forecast


def load_cfg(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def cfg_hash(cfg: dict[str, Any]) -> str:
    return hashlib.sha256(yaml.safe_dump(cfg, sort_keys=True).encode()).hexdigest()


def origin_dates(cfg: dict[str, Any]) -> list[date]:
    o, last = d(cfg["origins"]["first"]), d(cfg["origins"]["last"])
    out = []
    while o <= last:
        out.append(o)
        o += timedelta(days=int(cfg["origins"]["step_days"]))
    return out


def _task(payload: tuple) -> tuple[list[pd.DataFrame], list[dict]]:
    """One (target, origin): fit every model on y[:origin], then attach actuals up to as_of."""
    target, y_train, actual_future, origin, cfg = payload
    rows, logs = [], []
    n_eval = min(len(actual_future), int(cfg["max_horizon"]))
    for name in cfg["models"]:
        t0 = time.perf_counter()
        try:
            f, info = forecast(name, y_train, int(cfg["max_horizon"]), cfg)
            err = ""
        except Exception as e:  # recorded, never silently replaced by another model
            f, info, err = None, {}, f"{type(e).__name__}: {e}"
        sec = time.perf_counter() - t0
        logs.append({"target": target, "model": name, "origin": origin, "seconds": sec,
                     "failed": f is None, "error": err,
                     "info": {k: v for k, v in info.items() if k != "params"}})
        if f is None or n_eval == 0:
            continue
        f = f.iloc[:n_eval].copy()
        f["date"] = actual_future.index[:n_eval]
        f["actual"] = actual_future.to_numpy(float)[:n_eval]
        f["target"], f["model"], f["origin"] = target, name, origin
        rows.append(f.reset_index())
    return rows, logs


def run_backtest(
    series: dict[str, pd.Series], cfg: dict[str, Any], workers: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """-> (forecast rows with actuals, fit log). ``series`` must already end at as_of."""
    as_of = pd.Timestamp(d(cfg["as_of"]))
    tasks = []
    for target, y in series.items():
        if y.index.max() > as_of:
            raise ValueError(f"{target}: series extends past as_of (holdout leakage)")
        for o in origin_dates(cfg):
            ts = pd.Timestamp(o)
            tasks.append((target, y[y.index <= ts], y[y.index > ts], o, cfg))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_task, tasks, chunksize=2))
    else:
        results = [_task(t) for t in tasks]
    rows = [df for r, _ in results for df in r]
    logs = [lg for _, lg_list in results for lg in lg_list]
    fc = pd.concat(rows, ignore_index=True)
    fc["origin"] = pd.to_datetime(fc["origin"])
    fc = fc.sort_values(["target", "model", "origin", "step"]).reset_index(drop=True)
    return fc, pd.DataFrame(logs)


def _full_windows(fc: pd.DataFrame, h: int, as_of: date) -> pd.DataFrame:
    ok = fc["origin"] + pd.Timedelta(days=h) <= pd.Timestamp(as_of)
    return fc[ok & (fc["step"] <= h)]


def summarize(fc: pd.DataFrame, logs: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Pooled metrics per (target, model, horizon) over FULL windows only."""
    as_of = d(cfg["as_of"])
    rows = []
    for h in cfg["horizons"]:
        sub = _full_windows(fc, h, as_of)
        for (tgt, mdl), g in sub.groupby(["target", "model"]):
            per_origin = g.groupby("origin").apply(
                lambda x: M.wape(x["actual"], x["yhat"]), include_groups=False)
            agg_err = g.groupby("origin").apply(
                lambda x: abs(x["yhat"].sum() - x["actual"].sum()) / abs(x["actual"].sum()),
                include_groups=False)
            lg = logs[(logs["target"] == tgt) & (logs["model"] == mdl)]
            rows.append({
                "target": tgt, "model": mdl, "horizon": h,
                "n_origins": g["origin"].nunique(), "n_points": len(g),
                "mae": M.mae(g["actual"], g["yhat"]), "rmse": M.rmse(g["actual"], g["yhat"]),
                "wape": M.wape(g["actual"], g["yhat"]), "bias": M.bias(g["actual"], g["yhat"]),
                "wape_sd_origins": float(per_origin.std(ddof=1)) if len(per_origin) > 1 else np.nan,
                "window_sum_ape": float(agg_err.mean()),
                "cov80": M.coverage(g["actual"], g["lo80"], g["hi80"]),
                "cov95": M.coverage(g["actual"], g["lo95"], g["hi95"]),
                "width80": M.mean_width(g["lo80"], g["hi80"]),
                "width95": M.mean_width(g["lo95"], g["hi95"]),
                "sec_per_fit": float(lg["seconds"].mean()),
                "n_failed_fits": int(lg["failed"].sum()),
            })
    return pd.DataFrame(rows)


def _per_origin_wape(fc: pd.DataFrame, tgt: str, mdl: str, h: int, as_of: date) -> pd.Series:
    g = _full_windows(fc[(fc["target"] == tgt) & (fc["model"] == mdl)], h, as_of)
    return g.groupby("origin").apply(lambda x: M.wape(x["actual"], x["yhat"]), include_groups=False)


def select_champions(fc: pd.DataFrame, summary: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Per target: composite = mean WAPE over horizons; parsimony rule vs the best baseline."""
    as_of, hs = d(cfg["as_of"]), cfg["horizons"]
    base, cplx = cfg["baselines"], cfg["selection"]["complex"]
    mult = float(cfg["selection"]["se_multiplier"])
    comp = summary.pivot_table(index=["target", "model"], columns="horizon", values="wape")
    comp["composite"] = comp[hs].mean(axis=1, skipna=False)
    out = []
    for tgt, g in comp.groupby(level="target"):
        g = g.droplevel("target")["composite"].dropna()
        best_base = g[[m for m in base if m in g.index]].idxmin()
        cands = [m for m in cplx if m in g.index]
        best_cplx = g[cands].idxmin() if cands else None
        champion, reason, delta, se = best_base, "best baseline", np.nan, np.nan
        if best_cplx is not None and g[best_cplx] < g[best_base]:
            ds, ses = [], []
            for h in hs:
                a = _per_origin_wape(fc, tgt, best_cplx, h, as_of)
                b = _per_origin_wape(fc, tgt, best_base, h, as_of)
                dd = (a - b).dropna()
                ds.append(dd.mean())
                ses.append(dd.std(ddof=1) / math.sqrt(len(dd)) if len(dd) > 1 else np.nan)
            delta = float(np.mean(ds))
            se = float(math.sqrt(np.nansum(np.square(ses))) / len(hs))
            if delta < -mult * se:
                champion, reason = best_cplx, "beats best baseline by more than 1 paired SE"
            else:
                reason = f"{best_cplx} better but within noise; parsimony keeps the baseline"
        out.append({"target": tgt, "champion": champion, "reason": reason,
                    "composite_wape": float(g[champion]), "best_baseline": best_base,
                    "composite_best_baseline": float(g[best_base]),
                    "best_complex": best_cplx,
                    "composite_best_complex": float(g[best_cplx]) if best_cplx else np.nan,
                    "paired_delta_complex_minus_baseline": delta, "paired_se": se})
    return pd.DataFrame(out)


def freeze_champions(champions: pd.DataFrame, cfg: dict[str, Any], data_hash: str,
                     path: str | Path) -> dict[str, Any]:
    """Write the champion file once. Refuses to overwrite (a new choice needs a new version)."""
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"{p} exists: champions are frozen for backtest {cfg['version']}")
    doc = {
        "backtest_version": cfg["version"], "config_hash": cfg_hash(cfg), "data_hash": data_hash,
        "selection_rule": "composite WAPE (7/30/90), validation only; parsimony vs best baseline",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "champions": {r.target: {"model": r.champion, "reason": r.reason,
                                 "composite_wape": round(r.composite_wape, 6)}
                      for r in champions.itertuples()},
    }
    p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return doc
