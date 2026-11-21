from __future__ import annotations

from datetime import date

import pytest

from fintech_lab.p1_payments import dashboard_data as dd


def test_no_filter_matches_facts(con):
    k = dd.kpis(con, dd.Filters())
    n, s = con.execute(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE is_succeeded) FROM fct_payment"
    ).fetchone()
    assert (k["payments"], k["succeeded"]) == (n, s)
    assert k["m02"] == pytest.approx(s / n)
    tpv = con.execute("SELECT SUM(amount_brl) FROM fct_payment WHERE is_succeeded").fetchone()[0]
    assert k["tpv_brl"] == pytest.approx(float(tpv))


def test_country_partition_preserves_denominators(con):
    total = dd.kpis(con, dd.Filters())
    parts = [dd.kpis(con, dd.Filters(countries=(c,))) for c in ("BR", "MX", "CL")]
    assert sum(p["payments"] for p in parts) == total["payments"]
    assert sum(p["attempts"] for p in parts) == total["attempts"]
    pooled = sum(p["succeeded"] for p in parts) / sum(p["payments"] for p in parts)
    assert total["m02"] == pytest.approx(pooled)  # ratio of sums, not mean of rates


def test_acquirer_filter_grains(con):
    k = dd.kpis(con, dd.Filters(acquirers=("ACQ_BR_A",)))
    att = con.execute("SELECT COUNT(*) FROM fct_attempt WHERE acquirer_id = 'ACQ_BR_A'").fetchone()
    pay = con.execute(
        "SELECT COUNT(*) FROM fct_payment WHERE first_acquirer_id = 'ACQ_BR_A'"
    ).fetchone()
    assert k["attempts"] == att[0] and k["payments"] == pay[0]


def test_daily_sums_to_kpis(con):
    f = dd.Filters(date_from=date(2025, 3, 1), date_to=date(2025, 3, 31), methods=("pix",))
    d, k = dd.daily(con, f), dd.kpis(con, f)
    assert d["payments"].sum() == k["payments"] and d["attempts"].sum() == k["attempts"]
    assert d["day"].min().date() >= date(2025, 3, 1)


def test_empty_selection_is_safe(con):
    f = dd.Filters(methods=("credit_card",), acquirers=("PIX_BR",))
    k = dd.kpis(con, f)
    assert k["payments"] == 0 and k["attempts"] == 0
    assert k["m02"] is None and k["m01"] is None
    for fn in (
        dd.daily,
        dd.monthly_tpv,
        dd.declines,
        dd.acquirers,
        dd.error_by_hour,
        dd.retry_recovery,
        dd.attempt_ladder,
    ):
        assert fn(con, f).empty


def test_decline_shares(con):
    d = dd.declines(con, dd.Filters(countries=("MX",)))
    assert d["m04_share_of_failed"].sum() == pytest.approx(1.0)
    assert set(d["category"]) <= {"soft", "hard", "technical"}
