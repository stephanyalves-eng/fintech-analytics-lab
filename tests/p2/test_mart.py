from __future__ import annotations

import pytest

from fintech_lab.p2_forecasting.mart import build_mart, run_checks


def test_all_reconciliation_checks_pass(check_results):
    assert len(check_results) == 9
    assert {k: v for k, v in check_results.items() if v} == {}


def test_tpv_counts_payments_not_attempts(con):
    tpv, n = con.execute("SELECT SUM(tpv_brl), SUM(n_succeeded) FROM fct_daily_total").fetchone()
    p1 = con.execute(
        "SELECT SUM(amount_brl) FROM fct_payment WHERE is_succeeded "
        "AND created_date_local BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'"
    ).fetchone()[0]
    assert tpv == p1 and n > 0


def test_zero_days_explicit_and_no_pre_activation_rows(con):
    n_zero = con.execute(
        "SELECT COUNT(*) FROM fct_daily_merchant WHERE n_payments = 0"
    ).fetchone()[0]
    assert n_zero > 0
    assert con.execute(
        "SELECT COUNT(*) FROM fct_daily_merchant f JOIN dim_merchant m USING (merchant_id) "
        "WHERE f.date_local < m.activation_date"
    ).fetchone()[0] == 0


def test_events_land_on_event_date(con):
    row = con.execute(
        "SELECT merchant_id, event_date_local, amount_brl FROM syn_adjustment "
        "WHERE event_type = 'refund' AND event_date_local <= DATE '2025-12-31' LIMIT 1"
    ).fetchone()
    assert row is not None
    got = con.execute(
        "SELECT SUM(refund_brl) FROM fct_daily_merchant WHERE merchant_id = ? AND date_local = ?",
        [row[0], row[1]],
    ).fetchone()[0]
    assert got >= row[2]


def test_mart_is_deterministic(p1_dir, cfg):
    def digest(c):
        return c.execute(
            "SELECT SUM(tpv_brl), SUM(net_revenue_brl), SUM(contribution_brl), SUM(refund_brl), "
            "SUM(chargeback_brl) FROM fct_daily_total"
        ).fetchone()

    assert digest(build_mart(p1_dir, cfg)) == digest(build_mart(p1_dir, cfg))


@pytest.mark.parametrize(
    ("tamper", "expected"),
    [
        ("DELETE FROM fct_daily_total WHERE date_local = DATE '2025-03-10'",
         "r01_daily_monthly_total"),
        ("UPDATE fct_daily_merchant SET tpv_brl = tpv_brl + 1 WHERE rowid = 5",
         "r02_merchant_segment_total"),
        ("UPDATE fct_daily_total SET net_revenue_brl = net_revenue_brl + 1 "
         "WHERE date_local = DATE '2025-03-10'", "r09_margin_identity"),
    ],
)
def test_checks_detect_tampering(p1_dir, cfg, tamper, expected):
    c = build_mart(p1_dir, cfg)
    c.execute(tamper)
    assert run_checks(c, cfg)[expected] > 0


def test_duplicate_adjustment_is_detected(p1_dir, cfg):
    c = build_mart(p1_dir, cfg)
    c.execute("INSERT INTO syn_adjustment SELECT * FROM syn_adjustment LIMIT 1")
    assert run_checks(c, cfg)["r08_adjustments_valid"] > 0
