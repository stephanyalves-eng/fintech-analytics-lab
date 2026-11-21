from __future__ import annotations

import math

import pandas as pd
import pytest

from fintech_lab.p1_payments import diagnostics as dg
from fintech_lab.p1_payments import scenarios as sc


def test_wilson_bounds():
    lo, hi = sc.wilson(80, 100)
    assert 0 <= lo < 0.8 < hi <= 1
    assert all(math.isnan(x) for x in sc.wilson(0, 0))


def _toy_s1() -> pd.DataFrame:
    k = {
        "country": "BR",
        "first_acquirer_id": "A",
        "method_code": "credit_card",
        "amount_band_brl": "2: 50-200",
    }
    same = {
        **k,
        "switched": False,
        "payments": 100,
        "succeeded": 50,
        "amount_brl": 1e4,
        "tpv_brl": 5000.0,
        "processing_cost_brl": 100.0,
        "fee_brl": 150.0,
    }
    sw = {
        **k,
        "switched": True,
        "payments": 100,
        "succeeded": 60,
        "amount_brl": 1e4,
        "tpv_brl": 6000.0,
        "processing_cost_brl": 120.0,
        "fee_brl": 180.0,
    }
    return pd.DataFrame([same, sw])


def test_s1_hand_computed():
    cp = pd.Series({"BR": 1000})
    r = sc.simulate_s1(_toy_s1(), cp, sc.S1Assumptions(theta=1.0)).iloc[0]
    assert r["d_succeeded"] == pytest.approx(10.0)  # 100 x (0.6 - 0.5)
    assert r["d_tpv_brl"] == pytest.approx(1000.0)  # ticket = 11000 / 110 = 100
    assert r["d_fee_brl"] == pytest.approx(30.0)  # take = 330 / 11000 = 3%
    assert r["d_cost_brl"] == pytest.approx(20.0)  # 100 x (1.2 - 1.0)
    assert r["d_net_contribution_brl"] == pytest.approx(10.0)
    assert r["d_m02_pp"] == pytest.approx(1.0)
    assert r["d_succeeded_lo95"] < 10 < r["d_succeeded_hi95"]


def test_s1_theta_zero_is_null_and_small_strata_excluded():
    cp = pd.Series({"BR": 1000})
    r0 = sc.simulate_s1(_toy_s1(), cp, sc.S1Assumptions(theta=0.0)).iloc[0]
    assert r0["d_succeeded"] == 0 and r0["d_net_contribution_brl"] == 0
    assert sc.simulate_s1(_toy_s1(), cp, sc.S1Assumptions(min_n=101)).empty


def test_s1_population_matches_fact(con):
    base = dg.run(con, "s1_reroute_base")
    direct = con.execute(
        "SELECT COUNT(*) FROM fct_payment WHERE first_category = 'soft' AND n_attempts > 1 "
        "AND method_code <> 'pix'"
    ).fetchone()[0]
    assert base["payments"].sum() == direct


def test_s2_cap3_is_identity_and_cap2_exact(con):
    base = dg.run(con, "s2_retry_base")
    r3 = sc.simulate_s2(base, sc.S2Assumptions(cap=3))
    assert (r3[["d_succeeded", "d_tpv_brl", "d_cost_brl"]] == 0).all().all()
    tot = sc.simulate_s2(base, sc.S2Assumptions(cap=2)).iloc[-1]
    assert tot["country"] == "TOTAL"
    lost = con.execute(
        "SELECT COUNT(*) FROM fct_payment WHERE is_succeeded AND last_attempt_no = 3"
    ).fetchone()[0]
    cost3 = con.execute(
        "SELECT SUM(processing_cost_brl) FROM fct_attempt WHERE attempt_no = 3"
    ).fetchone()[0]
    assert tot["d_succeeded"] == -lost
    assert tot["d_cost_brl"] == pytest.approx(-float(cost3))
    assert tot["payments"] == con.execute("SELECT COUNT(*) FROM fct_payment").fetchone()[0]


def test_s2_cap4_monotone_in_delta_and_invalid_cap(con):
    base = dg.run(con, "s2_retry_base")
    vals = [
        sc.simulate_s2(base, sc.S2Assumptions(cap=4, delta=d)).iloc[-1]["d_succeeded"]
        for d in (0.5, 0.75, 1.0)
    ]
    assert 0 < vals[0] < vals[1] < vals[2]
    with pytest.raises(ValueError):
        sc.simulate_s2(base, sc.S2Assumptions(cap=5))


def test_memo_and_tables_written(con, dataset_dir, tmp_path):
    tables = dg.write_reports(con, dataset_dir, tmp_path)
    memo = (tmp_path / "diagnostic_memo.md").read_text(encoding="utf-8")
    assert "[TO VERIFY]" in memo and "synthetic" in memo
    assert "### S1" in memo and "### S2" in memo and "nan" not in memo
    assert (tmp_path / "diagnostics" / "s2_grid.csv").exists()
    s = tables["d01_failure_taxonomy"].groupby("country")["share_of_attempts"].sum()
    assert s.round(9).eq(1).all()
