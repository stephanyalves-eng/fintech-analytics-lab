from __future__ import annotations

import copy
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fintech_lab.p2_forecasting import backtest as bt
from fintech_lab.p2_forecasting import metrics as M
from fintech_lab.p2_forecasting.config import DEFAULT_BACKTEST
from fintech_lab.p2_forecasting.holdout import run_holdout
from fintech_lab.p2_forecasting.models import forecast
from fintech_lab.p2_forecasting.series import load_targets


@pytest.fixture(scope="module")
def bcfg():
    return bt.load_cfg(DEFAULT_BACKTEST)


def _series(n=150, start="2025-01-01", seed=0):
    idx = pd.date_range(start, periods=n, freq="D")
    rng = np.random.default_rng(seed)
    weekly = 100 * np.sin(2 * np.pi * idx.day_of_week / 7)
    y = 1000 + 3 * np.arange(n) + weekly + rng.normal(0, 10, n)
    return pd.Series(y, index=idx)


# ---- metrics ------------------------------------------------------------------------------
def test_metric_known_values_and_signs():
    a, f = [100, 200, 0], [110, 180, 0]
    assert M.mae(a, f) == pytest.approx(10.0)
    assert M.rmse(a, f) == pytest.approx(np.sqrt((100 + 400) / 3))
    assert M.wape(a, f) == pytest.approx(30 / 300)
    assert M.bias(a, f) == pytest.approx((10 - 20) / 300)  # Σ(f-a) / Σa
    assert M.bias([100], [120]) == pytest.approx(0.2)  # over-forecast is positive


def test_zero_denominators_are_undefined_not_zero():
    assert np.isnan(M.wape([0, 0], [1, 2])) and np.isnan(M.bias([0, 0], [1, 2]))
    assert np.isnan(M.coverage([1.0], [np.nan], [np.nan]))
    assert M.coverage([1, 5], [0, 0], [2, 2]) == 0.5


# ---- baselines ----------------------------------------------------------------------------
def test_baseline_points_and_weekday_alignment(bcfg):
    y = _series(60)
    n = len(y)
    nv, _ = forecast("naive", y, 10, bcfg)
    assert (nv["yhat"] == y.iloc[-1]).all()
    sn, _ = forecast("snaive", y, 14, bcfg)
    for k in range(1, 15):
        target_day = y.index[-1] + pd.Timedelta(days=k)
        src = sn.index  # step k uses the latest same-weekday value inside the history
        ref = y.iloc[n + k - 1 - 7 * int(np.ceil(k / 7))]
        assert sn.loc[k, "yhat"] == ref
        assert y.index[n + k - 1 - 7 * int(np.ceil(k / 7))].day_of_week == target_day.day_of_week
        assert len(src) == 14
    ma, _ = forecast("ma7", y, 5, bcfg)
    assert (ma["yhat"] == y.iloc[-7:].mean()).all()


def test_empirical_intervals_need_enough_residuals(bcfg):
    y = _series(40)
    f, info = forecast("naive", y, 30, bcfg)
    assert f["lo95"].iloc[0] < f["yhat"].iloc[0] < f["hi95"].iloc[0]
    assert f["lo95"].iloc[-1:].isna().all() and info["n_residuals_min"] < 20  # step 30: 10 errors


# ---- leakage ------------------------------------------------------------------------------
def test_forecast_ignores_actuals_after_origin(bcfg):
    cfg = copy.deepcopy(bcfg)
    cfg.update(models=["naive", "snaive", "ma7", "ets"], max_horizon=14)
    y = _series(120)
    train, fut = y.iloc[:100], y.iloc[100:]
    r1, _ = bt._task(("t", train, fut, date(2025, 4, 10), cfg))
    r2, _ = bt._task(("t", train, fut * 1000 + 7, date(2025, 4, 10), cfg))
    for a, b in zip(r1, r2, strict=True):
        pd.testing.assert_series_equal(a["yhat"], b["yhat"])
        assert not a["actual"].equals(b["actual"])


def test_backtest_rejects_series_past_as_of(bcfg):
    cfg = copy.deepcopy(bcfg)
    cfg["as_of"] = "2025-04-30"
    with pytest.raises(ValueError, match="past as_of"):
        bt.run_backtest({"x": _series(150)}, cfg)


def test_load_targets_truncates(tmp_path):
    days = pd.date_range("2025-01-01", periods=10)
    tot = pd.DataFrame({"date_local": days.date, "tpv_brl": 1.0, "net_revenue_brl": 1.0,
                        "contribution_brl": 1.0})
    seg = pd.DataFrame([(dd.date(), "BR", 2.0) for dd in days],
                       columns=["date_local", "country", "tpv_brl"])
    tot.to_parquet(tmp_path / "fct_daily_total.parquet")
    seg.to_parquet(tmp_path / "fct_daily_segment.parquet")
    s = load_targets(tmp_path, ["BR"], date(2025, 1, 6))
    assert s["tpv_total"].index.max() == pd.Timestamp("2025-01-06") and len(s["tpv_BR"]) == 6


# ---- end-to-end (small) -------------------------------------------------------------------
@pytest.fixture(scope="module")
def small_cfg(bcfg):
    cfg = copy.deepcopy(bcfg)
    cfg.update(models=["naive", "snaive", "ma7", "ets"], max_horizon=14, horizons=[7],
               as_of="2025-05-31")
    cfg["origins"] = {"first": "2025-03-31", "step_days": 7, "last": "2025-05-19"}
    return cfg


def test_end_to_end_deterministic_and_complete(small_cfg):
    y = _series(151)  # 2025-01-01 .. 2025-05-31
    fc1, lg1 = bt.run_backtest({"t": y}, small_cfg)
    fc2, _ = bt.run_backtest({"t": y}, small_cfg)
    pd.testing.assert_frame_equal(fc1, fc2)
    assert not lg1["failed"].any()
    s = bt.summarize(fc1, lg1, small_cfg)
    assert set(s["model"]) == set(small_cfg["models"]) and (s["n_origins"] > 0).all()
    assert s["wape"].between(0, 1).all()
    assert fc1["date"].max() <= pd.Timestamp("2025-05-31")  # nothing evaluated after as_of


# ---- selection and freezing ---------------------------------------------------------------
def _synthetic_fc(delta_pattern, cfg):
    """baseline error ~10; complex error = 10 + delta per origin; actual = 100."""
    rows = []
    origins = pd.date_range("2025-04-01", "2025-09-23", freq="7D")
    for i, o in enumerate(origins):
        for mdl, err in (("naive", 10.0), ("ets", 10.0 + delta_pattern(i))):
            for step in range(1, 8):
                rows.append({"target": "x", "model": mdl, "origin": o, "step": step,
                             "date": o + pd.Timedelta(days=step), "actual": 100.0,
                             "yhat": 100.0 + err, "lo80": np.nan, "hi80": np.nan,
                             "lo95": np.nan, "hi95": np.nan})
    return pd.DataFrame(rows)


def _select(fc, cfg):
    cfg = copy.deepcopy(cfg)
    cfg.update(horizons=[7], baselines=["naive"])
    cfg["selection"]["complex"] = ["ets"]
    logs = pd.DataFrame([{"target": "x", "model": m, "origin": None, "seconds": 0.1,
                          "failed": False} for m in ("naive", "ets")])
    return bt.select_champions(fc, bt.summarize(fc, logs, cfg), cfg).iloc[0]


def test_complex_model_wins_only_with_a_clear_margin(bcfg):
    clear = _select(_synthetic_fc(lambda i: -3.0 + (0.2 if i % 2 else -0.2), bcfg), bcfg)
    assert clear["champion"] == "ets"
    noisy = _select(_synthetic_fc(lambda i: (-0.2 if i % 2 else 0.1) + (6 if i % 2 else -6), bcfg),
                    bcfg)
    assert noisy["best_complex"] == "ets" and noisy["champion"] == "naive"
    assert "noise" in noisy["reason"]


def test_champions_freeze_once_and_holdout_checks_config(bcfg, tmp_path):
    champs = pd.DataFrame([{"target": "tpv_total", "champion": "naive", "reason": "r",
                            "composite_wape": 0.1}])
    p = tmp_path / "c.yaml"
    bt.freeze_champions(champs, bcfg, "hash", p)
    with pytest.raises(FileExistsError):
        bt.freeze_champions(champs, bcfg, "hash", p)
    changed = copy.deepcopy(bcfg)
    changed["horizons"] = [7]
    with pytest.raises(ValueError, match="config changed"):
        run_holdout({}, changed, p, pd.DataFrame())
