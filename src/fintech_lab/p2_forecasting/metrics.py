"""Forecast error metrics (contract E01–E05). Sign convention: Bias > 0 = over-forecast."""

from __future__ import annotations

import numpy as np


def _arr(a, f):
    a, f = np.asarray(a, float), np.asarray(f, float)
    if a.shape != f.shape:
        raise ValueError("actual and forecast must have the same shape")
    return a, f


def mae(actual, forecast) -> float:
    a, f = _arr(actual, forecast)
    return float(np.mean(np.abs(a - f))) if a.size else float("nan")


def rmse(actual, forecast) -> float:
    a, f = _arr(actual, forecast)
    return float(np.sqrt(np.mean((a - f) ** 2))) if a.size else float("nan")


def wape(actual, forecast) -> float:
    """Σ|a−f| / Σ|a|; NaN (undefined) when the denominator is 0."""
    a, f = _arr(actual, forecast)
    den = np.abs(a).sum()
    return float(np.abs(a - f).sum() / den) if den > 0 else float("nan")


def bias(actual, forecast) -> float:
    """Σ(f−a) / Σa; positive = over-forecast; NaN when Σa = 0."""
    a, f = _arr(actual, forecast)
    den = a.sum()
    return float((f - a).sum() / den) if den != 0 else float("nan")


def coverage(actual, lo, hi) -> float:
    """Share of actuals inside [lo, hi]; points with NaN bounds are ignored (NaN if none left)."""
    a = np.asarray(actual, float)
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    ok = ~(np.isnan(lo) | np.isnan(hi))
    return float(np.mean((a[ok] >= lo[ok]) & (a[ok] <= hi[ok]))) if ok.any() else float("nan")


def mean_width(lo, hi) -> float:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    ok = ~(np.isnan(lo) | np.isnan(hi))
    return float(np.mean(hi[ok] - lo[ok])) if ok.any() else float("nan")
