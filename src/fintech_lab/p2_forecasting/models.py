"""Forecast models. Every model sees ONLY the history ``y`` (index <= origin) and returns a path.

``forecast(name, y, horizon, cfg)`` -> (DataFrame indexed by step 1..horizon with columns
yhat, lo80, hi80, lo95, hi95, info dict). No randomness is used, so results are reproducible
given the same data and library versions.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd

LEVELS = {"80": 0.80, "95": 0.95}


def _frame(steps: int, yhat, bounds: dict[str, tuple]) -> pd.DataFrame:
    idx = pd.RangeIndex(1, steps + 1, name="step")
    df = pd.DataFrame({"yhat": np.asarray(yhat, float)}, index=idx)
    for k, (lo, hi) in bounds.items():
        df[f"lo{k}"], df[f"hi{k}"] = np.asarray(lo, float), np.asarray(hi, float)
    return df


# ---- baselines + empirical-residual intervals ------------------------------------------------
def _point(name: str, y: np.ndarray, horizon: int) -> np.ndarray:
    n = len(y)
    if name == "naive":
        return np.full(horizon, y[-1])
    if name == "snaive":
        return np.array([y[n + k - 1 - 7 * math.ceil(k / 7)] for k in range(1, horizon + 1)])
    if name in ("ma7", "ma28"):
        w = int(name[2:])
        return np.full(horizon, y[-w:].mean())
    raise KeyError(name)


def _residuals(name: str, y: np.ndarray, k: int) -> np.ndarray:
    """In-sample k-step-ahead errors (actual − forecast) using only the history ``y``."""
    n = len(y)
    if name == "naive":
        return y[k:] - y[:-k] if n > k else np.array([])
    if name == "snaive":
        lag = 7 * math.ceil(k / 7)
        return y[lag:] - y[: n - lag] if n > lag else np.array([])
    w = int(name[2:])
    if n < w + k:
        return np.array([])
    cs = np.concatenate([[0.0], np.cumsum(y)])
    level = (cs[w:] - cs[:-w]) / w          # level[i] = mean(y[i..i+w-1]) known at t = i+w-1
    t = np.arange(w - 1, n - k)
    return y[t + k] - level[t - (w - 1)]


def baseline(name: str, y: pd.Series, horizon: int, min_resid: int) -> tuple[pd.DataFrame, dict]:
    arr = y.to_numpy(float)
    yhat = _point(name, arr, horizon)
    bounds: dict[str, tuple[list, list]] = {"80": ([], []), "95": ([], [])}
    n_res = []
    for k in range(1, horizon + 1):
        r = _residuals(name, arr, k)
        n_res.append(len(r))
        for key, lvl in LEVELS.items():
            if len(r) >= min_resid:
                a = (1 - lvl) / 2
                lo, hi = np.quantile(r, [a, 1 - a])
            else:
                lo = hi = np.nan
            bounds[key][0].append(yhat[k - 1] + lo)
            bounds[key][1].append(yhat[k - 1] + hi)
    info = {"n_residuals_min": int(min(n_res)), "interval": "empirical"}
    return _frame(horizon, yhat, bounds), info


# ---- ETS / SARIMA ------------------------------------------------------------------------------
def _scaled(y: pd.Series) -> tuple[pd.Series, float]:
    scale = float(np.abs(y).mean()) or 1.0
    return y / scale, scale


def ets(y: pd.Series, horizon: int, spec: dict[str, Any]) -> tuple[pd.DataFrame, dict]:
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    ys, scale = _scaled(y)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = ETSModel(ys, error=spec["error"], trend=spec["trend"],
                       damped_trend=spec["damped_trend"], seasonal=spec["seasonal"],
                       seasonal_periods=spec["seasonal_periods"]).fit(disp=False, maxiter=500)
        pred = res.get_prediction(start=len(ys), end=len(ys) + horizon - 1)
        b = {}
        for key, lvl in LEVELS.items():
            sf = pred.summary_frame(alpha=1 - lvl)
            b[key] = (sf["pi_lower"] * scale, sf["pi_upper"] * scale)
        yhat = pred.summary_frame(alpha=0.05)["mean"] * scale
    params = {k: float(v) for k, v in zip(res.param_names, res.params, strict=True)}
    return _frame(horizon, yhat, {k: (v[0], v[1]) for k, v in b.items()}), {
        "aic": float(res.aic),
        "params": params, "interval": "model"}


def sarima(y: pd.Series, horizon: int, spec: dict[str, Any]) -> tuple[pd.DataFrame, dict]:
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    ys, scale = _scaled(y)
    best = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for order in spec["order_grid"]:
            try:
                res = SARIMAX(ys, order=tuple(order), seasonal_order=tuple(spec["seasonal_order"]),
                              enforce_stationarity=False, enforce_invertibility=False
                              ).fit(disp=False, maxiter=200)
            except Exception:  # a failed candidate is skipped; all failing raises below
                continue
            if np.isfinite(res.aic) and (best is None or res.aic < best[0]):
                best = (float(res.aic), tuple(order), res)
        if best is None:
            raise RuntimeError("no SARIMA candidate converged")
        aic, order, res = best
        fc = res.get_forecast(horizon)
        b = {}
        for key, lvl in LEVELS.items():
            ci = fc.conf_int(alpha=1 - lvl)
            b[key] = (np.asarray(ci)[:, 0] * scale, np.asarray(ci)[:, 1] * scale)
        yhat = np.asarray(fc.predicted_mean) * scale
    return _frame(horizon, yhat, b), {"aic": aic, "order": list(order), "interval": "model"}


def forecast(
    name: str, y: pd.Series, horizon: int, cfg: dict[str, Any]
) -> tuple[pd.DataFrame, dict]:
    if name in ("naive", "snaive", "ma7", "ma28"):
        return baseline(name, y, horizon, cfg["intervals"]["min_residuals_baseline"])
    if name == "ets":
        return ets(y, horizon, cfg["ets"])
    if name == "sarima":
        return sarima(y, horizon, cfg["sarima"])
    raise KeyError(name)
