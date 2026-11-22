from __future__ import annotations

import copy
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fintech_lab.p2_forecasting import budget
from fintech_lab.p2_forecasting.calendar import build_calendar
from fintech_lab.p2_forecasting.features import (
    CALENDAR_FEATURES,
    assign_split,
    make_features,
    validate_splits,
)


# ---- budget -------------------------------------------------------------------------------
def _merchant_df(later_scale=1.0):
    rows = []
    for c, b in (("BR", 1000.0), ("MX", 500.0)):
        for dt in pd.date_range("2025-01-01", "2025-03-31"):
            k = 1.0 if dt.month == 1 else later_scale
            rows.append((dt.date(), c, b * k, b * k * 0.02))
    return pd.DataFrame(rows, columns=["date_local", "country", "tpv_brl", "fee_brl"])


def test_calibration_uses_only_january(cfg):
    a = budget.calibrate(_merchant_df(), cfg)
    b = budget.calibrate(_merchant_df(later_scale=50.0), cfg)  # perturb everything after January
    assert a == b
    assert a["base_daily_tpv_brl"] == {"BR": 1000.0, "MX": 500.0}


def test_budget_growth_is_the_declared_error(cfg):
    t = budget.build_budget(budget.calibrate(_merchant_df(), cfg), cfg)
    br = t[t["country"] == "BR"].set_index("month")["tpv_brl"]
    per_day = np.array([br.iloc[i] / pd.Timestamp(br.index[i]).days_in_month for i in range(12)])
    assert np.allclose(per_day[1:] / per_day[:-1], 1.04, atol=1e-3)
    assert (t["version"] == "v1").all() and (t["as_of"] == "2024-12-31").all()


def test_budget_freeze_is_immutable_and_verifiable(cfg, tmp_path):
    frozen = budget.calibrate(_merchant_df(), cfg)
    p = tmp_path / "b.yaml"
    doc = budget.freeze(frozen, cfg, p)
    assert budget.verify(doc, cfg)
    with pytest.raises(FileExistsError):
        budget.freeze(frozen, cfg, p)
    changed = copy.deepcopy(cfg)
    changed["budget"]["monthly_growth"] = 0.10
    assert not budget.verify(doc, changed)  # R10 catches a silent edit


def test_committed_budget_still_verifies(cfg):
    from fintech_lab.p2_forecasting.config import DEFAULT_BUDGET

    if not DEFAULT_BUDGET.exists():
        pytest.skip("budget_v1.yaml not frozen yet (run the P2 build)")
    assert budget.verify(budget.load_frozen(), cfg)


# ---- splits -------------------------------------------------------------------------------
def test_splits_valid_and_chronological(cfg):
    validate_splits(cfg)
    dates = pd.Series(pd.date_range("2025-01-01", "2025-12-31").date)
    s = assign_split(dates, cfg)
    assert s.value_counts().to_dict() == {"train": 212, "validation": 61, "test": 92}
    assert s.map({"train": 0, "validation": 1, "test": 2}).is_monotonic_increasing
    assert dates[s == "validation"].max() == date.fromisoformat(cfg["as_of"])


def test_invalid_splits_rejected(cfg):
    bad = copy.deepcopy(cfg)
    bad["splits"]["test"] = ["2025-09-30", "2025-12-31"]  # overlaps validation
    with pytest.raises(ValueError):
        validate_splits(bad)
    bad2 = copy.deepcopy(cfg)
    bad2["splits"]["validation"] = ["2025-08-01", "2025-09-29"]  # gap, not ending at as_of
    with pytest.raises(ValueError):
        validate_splits(bad2)


# ---- anti-leakage -------------------------------------------------------------------------
@pytest.fixture(scope="module")
def series():
    rng = np.random.default_rng(0)
    days = pd.date_range("2025-01-01", "2025-12-31")
    df = pd.DataFrame({
        "date_local": days.date,
        "tpv": rng.random(len(days)) * 100,
        "active_merchants": np.arange(len(days)) % 40 + 100,
    })
    return df, build_calendar(date(2025, 1, 1), date(2025, 12, 31))


@pytest.mark.parametrize("h", [1, 7, 30, 90])
def test_features_never_see_the_future(series, h):
    df, cal = series
    lags = (max(h, 7), max(h, 14))
    base = make_features(df, cal, "tpv", h, lags=lags)
    t = 200  # first perturbed day index
    pert = df.copy()
    pert.loc[t:, "tpv"] *= 1000
    pert.loc[t:, "active_merchants"] += 999
    alt = make_features(pert, cal, "tpv", h, lags=lags)
    feats = [c for c in base.columns if c not in ("date_local", "y", "horizon")]
    # row r uses only data at index <= r - h, so every row r < t + h must be identical
    pd.testing.assert_frame_equal(base.loc[: t + h - 1, feats], alt.loc[: t + h - 1, feats])
    assert not base.loc[t + h :, feats].equals(alt.loc[t + h :, feats])  # the test is sensitive


def test_calendar_features_do_not_depend_on_target(series):
    df, cal = series
    a = make_features(df, cal, "tpv", 7)
    b = make_features(df.assign(tpv=df["tpv"] * 7), cal, "tpv", 7)
    pd.testing.assert_frame_equal(a[CALENDAR_FEATURES], b[CALENDAR_FEATURES])


def test_short_lag_and_gappy_series_rejected(series):
    df, cal = series
    with pytest.raises(ValueError, match="leakage"):
        make_features(df, cal, "tpv", 14, lags=(7,))
    with pytest.raises(ValueError, match="gap-free"):
        make_features(df.drop(index=10), cal, "tpv", 7)
    with pytest.raises(ValueError, match="duplicate"):
        make_features(pd.concat([df, df.iloc[[3]]]), cal, "tpv", 7)


def test_seasonal_lag_is_same_weekday_and_available(series):
    df, cal = series
    f = make_features(df, cal, "tpv", 10)
    assert f.loc[100, "lag_seasonal"] == df.loc[86, "tpv"]  # 7 * ceil(10/7) = 14 >= h
