"""Time-safe features and chronological splits.

Convention: for a target date ``t`` and horizon ``h`` the forecast origin is ``o = t - h``.
Every history-based feature of row ``t`` uses only values dated ``<= o``. Calendar columns are
known in advance and may use ``t`` itself.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from fintech_lab.p2_forecasting.config import d

CALENDAR_FEATURES = ["dow", "is_weekend", "is_month_start", "is_month_end", "n_holiday_countries",
                     "is_black_friday", "is_cyber_monday"]


def assign_split(dates: pd.Series, cfg: dict[str, Any]) -> pd.Series:
    """train / validation / test by date; raises on dates outside every split."""
    bounds = {k: (d(v[0]), d(v[1])) for k, v in cfg["splits"].items()}
    out = pd.Series(index=dates.index, dtype=object)
    for name, (lo, hi) in bounds.items():
        out[(dates >= lo) & (dates <= hi)] = name
    if out.isna().any():
        raise ValueError("dates outside the configured splits")
    return out


def validate_splits(cfg: dict[str, Any]) -> None:
    """Contiguous, disjoint, chronological; test starts after the as-of cut-off."""
    names = ["train", "validation", "test"]
    iv = [(d(cfg["splits"][n][0]), d(cfg["splits"][n][1])) for n in names]
    for (lo, hi), n in zip(iv, names, strict=True):
        if lo > hi:
            raise ValueError(f"{n}: start after end")
    for (_, prev_hi), (nxt_lo, _) in zip(iv, iv[1:], strict=False):
        if (nxt_lo - prev_hi).days != 1:
            raise ValueError("splits must be contiguous and disjoint")
    if iv[1][1] != d(cfg["as_of"]) or iv[2][0] <= d(cfg["as_of"]):
        raise ValueError("validation must end at as_of and test must start after it")


def make_features(
    daily: pd.DataFrame, calendar_df: pd.DataFrame, target: str, horizon: int,
    lags: tuple[int, ...] | None = None, windows: tuple[int, ...] = (7, 28),
    history_cols: tuple[str, ...] = ("active_merchants",),
) -> pd.DataFrame:
    """Direct-forecast design matrix for one target and one horizon.

    ``lag_L`` = y[t-L] requires L >= horizon; ``lag_seasonal`` = y[t - 7*ceil(h/7)] (same weekday,
    most recent one available at the origin); ``roll_mean_w``/``roll_std_w`` cover y[o-w+1..o].
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if lags is None:  # default weekly lags, pushed out to the first multiple of 7 >= horizon
        step = 7 * math.ceil(horizon / 7)
        lags = tuple(sorted({max(lag, step) for lag in (7, 14, 28)}))
    bad = [lag for lag in lags if lag < horizon]
    if bad:
        raise ValueError(f"lags {bad} are shorter than horizon {horizon}: future leakage")
    df = daily.sort_values("date_local").reset_index(drop=True)
    idx = pd.to_datetime(df["date_local"])
    if idx.duplicated().any():
        raise ValueError("duplicate dates")
    if (idx.diff().dropna() != pd.Timedelta(days=1)).any():
        raise ValueError("daily series must be gap-free")
    y = df[target].astype(float)
    out = pd.DataFrame({"date_local": df["date_local"], "y": y})
    for lag in lags:
        out[f"lag_{lag}"] = y.shift(lag)
    out["lag_seasonal"] = y.shift(7 * math.ceil(horizon / 7))
    base = y.shift(horizon)
    for w in windows:
        out[f"roll_mean_{w}"] = base.rolling(w, min_periods=w).mean()
        out[f"roll_std_{w}"] = base.rolling(w, min_periods=w).std()
    for c in history_cols:
        out[f"{c}_h{horizon}"] = df[c].astype(float).shift(horizon)
    cal = calendar_df.set_index("date_local")[CALENDAR_FEATURES]
    out = out.join(cal, on="date_local")
    out["horizon"] = horizon
    return out


def origin_date(target_date: date, horizon: int) -> date:
    return (pd.Timestamp(target_date) - pd.Timedelta(days=horizon)).date()
