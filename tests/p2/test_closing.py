from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest
import yaml

from fintech_lab.p2_forecasting import alerts as AL
from fintech_lab.p2_forecasting import pnl, scenarios
from fintech_lab.p2_forecasting.bridge import contribution_bridge, fee_bridge, lmdi
from fintech_lab.p2_forecasting.config import DEFAULT_ALERTS, DEFAULT_SCENARIOS, REPO_ROOT

C = ["BR", "CL", "MX"]


def _pl(tpv, take, rc=0.02, inc=0.0005, proc=0.01, var=0.001):
    tpv = pd.Series(tpv, index=C, dtype=float)
    r = pd.DataFrame({"take": take, "rc_share": rc, "inc": inc, "proc": proc, "var": var}, index=C)
    return pnl.pl_from_ratios(tpv, r)


# ---- bridge -------------------------------------------------------------------------------
def test_fee_bridge_pure_volume_has_no_mix_rate_or_interaction():
    b = _pl([100.0, 50.0, 50.0], [0.02, 0.03, 0.025])
    a = _pl([200.0, 100.0, 100.0], [0.02, 0.03, 0.025])  # everything doubles
    p = fee_bridge(b, a)
    assert p["mix"] == pytest.approx(0) and p["rate"] == pytest.approx(0)
    assert p["interaction"] == pytest.approx(0)
    assert p["volume"] == pytest.approx(a["fee"].sum() - b["fee"].sum())


def test_fee_bridge_hand_computed_case():
    b = _pl([100.0, 100.0, 0.0001], [0.02, 0.04, 0.03])
    a = _pl([150.0, 50.0, 0.0001], [0.02, 0.04, 0.03])  # same total; share moves to low rate
    p = fee_bridge(b, a)
    assert p["volume"] == pytest.approx(0, abs=1e-4)
    assert p["mix"] == pytest.approx(-1.0, abs=1e-3)  # 50 TPV moves from 4% to 2%
    assert p["rate"] == pytest.approx(0) and p["interaction"] == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize("seed", range(5))
def test_bridges_close_exactly_on_random_states(seed):
    rng = np.random.default_rng(seed)
    mk = lambda: _pl(rng.uniform(10, 1000, 3), rng.uniform(0.01, 0.04, 3),  # noqa: E731
                     rc=rng.uniform(0.01, 0.1), proc=rng.uniform(0.003, 0.02))
    b, a = mk(), mk()
    parts = fee_bridge(b, a)
    assert sum(parts.values()) == pytest.approx(a["fee"].sum() - b["fee"].sum(), rel=1e-9)
    br = contribution_bridge(b, a)
    steps = br.set_index("step")["effect"]
    assert abs(steps["Residual"]) < 1e-6
    middle = br[~br["kind"].isin(["start", "end"])]["effect"].sum()
    assert steps["Contribution (reference)"] + middle == pytest.approx(
        steps["Contribution (compared)"], rel=1e-9)


def test_lmdi_closes_and_is_symmetric():
    out = lmdi({"x": 10.0, "y": 5.0, "z": 2.0}, {"x": 12.0, "y": 5.0, "z": 3.0})
    assert out["effect"].sum() == pytest.approx(12 * 5 * 3 - 10 * 5 * 2)
    assert out.set_index("driver").loc["y", "effect"] == pytest.approx(0)
    same = lmdi({"x": 2.0, "y": 3.0}, {"x": 2.0, "y": 3.0})
    assert same["effect"].abs().sum() == pytest.approx(0)
    sym = lmdi({"a": 1.0, "b": 1.0}, {"a": 2.0, "b": 2.0})
    assert sym["effect"].iloc[0] == pytest.approx(sym["effect"].iloc[1])


# ---- scenarios ----------------------------------------------------------------------------
def _base():
    tpv = pd.Series([1000.0, 400.0, 600.0], index=C)
    r = pd.DataFrame({"take": 0.02, "rc_share": 0.05, "inc": 0.0005, "proc": 0.01, "var": 0.001},
                     index=C)
    return tpv, r


def test_base_scenario_is_identity_and_tpv_is_multiplicative():
    tpv, r = _base()
    base = scenarios.apply_scenario(tpv, r, {})
    pd.testing.assert_frame_equal(base, pnl.pl_from_ratios(tpv, r))
    s = scenarios.apply_scenario(tpv, r, {"merchants": 0.1, "volume_per_merchant": 0.1,
                                          "ticket": 0.1})
    assert s["tpv"].sum() == pytest.approx(tpv.sum() * 1.1**3)  # not +30%: interaction is explicit
    with pytest.raises(ValueError, match="unknown"):
        scenarios.apply_scenario(tpv, r, {"nonsense": 1.0})


def test_configured_scenarios_are_ordered_and_reproducible():
    cfg = yaml.safe_load(DEFAULT_SCENARIOS.read_text(encoding="utf-8"))
    tpv, r = _base()
    t1 = scenarios.scenario_table(tpv, r, scenarios.scenarios_from_config(cfg))
    t2 = scenarios.scenario_table(tpv, r, scenarios.scenarios_from_config(cfg))
    pd.testing.assert_frame_equal(t1, t2)
    c = t1.set_index("scenario")["contribution"]
    assert c["conservative"] < c["base"] < c["optimistic"]


def test_sensitivity_interaction_is_joint_minus_sum_of_solo_effects():
    tpv, r = _base()
    joint = {"merchants": -0.1, "take_rate": -0.1}
    s = scenarios.sensitivity(tpv, r, 0.1, joint=joint)
    base = scenarios.apply_scenario(tpv, r, {})["contribution"].sum()
    solo = sum(scenarios.apply_scenario(tpv, r, {k: v})["contribution"].sum() - base
               for k, v in joint.items())
    both = scenarios.apply_scenario(tpv, r, joint)["contribution"].sum() - base
    assert s.attrs["interaction"]["contribution"] == pytest.approx(both - solo)
    assert abs(s.attrs["interaction"]["contribution"]) > 0       # merchants x take rate interact
    row = s[(s["driver"] == "take_rate") & (s["change"] == 0.1)].iloc[0]
    assert row["d_tpv"] == 0 and row["d_net"] > 0


def test_statistical_band_uses_only_backtest_errors():
    rows = []
    for o in pd.date_range("2025-04-01", "2025-06-30", freq="7D"):
        for step in range(1, 91):
            rows.append({"target": "t", "model": "m", "origin": o, "step": step,
                         "actual": 100.0, "yhat": 110.0})
    fc = pd.DataFrame(rows)
    b = scenarios.statistical_band(fc, "t", "m", date(2025, 9, 30), 90, point_total=1100.0)
    assert b["err_q_lo"] == pytest.approx(0.1) and b["err_q_hi"] == pytest.approx(0.1)
    assert b["implied_lo"] == pytest.approx(1000.0) and b["implied_hi"] == pytest.approx(1000.0)
    assert b["n_origins"] > 5


# ---- alerts -------------------------------------------------------------------------------
def test_alert_severity_thresholds_and_direction():
    rules = yaml.safe_load(DEFAULT_ALERTS.read_text(encoding="utf-8"))["rules"]
    items = [
        {"alert": "forecast_vs_budget", "scope": "a", "value": 0.05, "evidence": ""},
        {"alert": "forecast_vs_budget", "scope": "b", "value": -0.10, "evidence": ""},
        {"alert": "forecast_vs_budget", "scope": "c", "value": -0.25, "evidence": ""},
        {"alert": "interval_coverage_80", "scope": "d", "value": 0.45, "lower_is_worse": True,
         "evidence": ""},
        {"alert": "interval_coverage_80", "scope": "e", "value": 0.80, "lower_is_worse": True,
         "evidence": ""},
        {"alert": "forecast_vs_budget", "scope": "f", "value": float("nan"), "evidence": ""},
    ]
    sev = AL.evaluate(items, rules).set_index("scope")["severity"].to_dict()
    assert sev == {"a": "ok", "b": "amber", "c": "red", "d": "red", "e": "ok", "f": "n/a"}
    assert math.isnan(AL.rel(1.0, 0.0))


# ---- integration on the real exports (skipped when they were not built) -------------------
DATA = REPO_ROOT / "data" / "p2"


@pytest.mark.skipif(not (DATA / "backtest" / "fct_holdout_forecast.parquet").exists(),
                    reason="run build, backtest --freeze and holdout first")
def test_budget_lines_rebuild_matches_budget_table_and_closing_runs(tmp_path):
    from fintech_lab.p2_forecasting import backtest as bt
    from fintech_lab.p2_forecasting.closing import run_closing
    from fintech_lab.p2_forecasting.config import (
        DEFAULT_BACKTEST,
        DEFAULT_CHAMPIONS,
        load_assumptions,
    )

    cfg = load_assumptions()
    budget = pd.read_parquet(DATA / "budget_v1.parquet")
    pl = pnl.budget_pl(budget, cfg, date(2025, 1, 1), date(2025, 12, 31))
    tab = budget.groupby("country")[["net_revenue_brl", "contribution_brl"]].sum()
    assert (pl["net"] - tab["net_revenue_brl"]).abs().max() < 1.0      # 2-decimal rounding only
    assert (pl["contribution"] - tab["contribution_brl"]).abs().max() < 1.0

    load = lambda p: yaml.safe_load(p.read_text(encoding="utf-8"))  # noqa: E731
    o = run_closing(DATA, cfg, bt.load_cfg(DEFAULT_BACKTEST), load(DEFAULT_SCENARIOS),
                    load(DEFAULT_ALERTS), DEFAULT_CHAMPIONS, tmp_path)
    for k in ("budget_to_actual", "forecast_to_actual", "budget_to_forecast"):
        e = o[k].set_index("step")["effect"]
        assert abs(e["Residual"]) < 1e-3
    h = o["headline"].set_index("metric")
    assert h.loc["TPV", "actual"] == pytest.approx(o["actual"]["tpv"].sum())
    assert (tmp_path / "executive_closing_report.md").read_text(encoding="utf-8").startswith("# P2")
    assert set(o["alerts_ex_ante"]["severity"]) <= {"ok", "amber", "red", "n/a"}
