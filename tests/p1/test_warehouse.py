from __future__ import annotations

from decimal import Decimal

from fintech_lab.p1_payments.warehouse import analyses, run_analysis, run_checks


def test_reconciliation_checks_pass(con):
    results = run_checks(con, "reconciliation")
    assert len(results) == 5
    assert results == dict.fromkeys(results, 0)


def test_tpv_not_inflated_by_retries(con, tables):
    """Acceptance test 9: mart M06 == direct sum over fact_payment (exact decimals)."""
    p = tables["fact_payment"]
    direct = p[p["final_status"] == "succeeded"].groupby("currency")["amount"].sum()
    mart = dict(
        con.execute(
            "SELECT currency, SUM(m06_tpv_local) FROM mart_auth_daily GROUP BY 1"
        ).fetchall()
    )
    for cur, value in direct.items():
        assert mart[cur] == Decimal(str(round(value, 2))), cur


def test_naive_join_would_inflate_tpv(con):
    df = run_analysis(con, "q15_double_counting_demo")
    assert (df["naive_inflation"] > 0).all()


def test_no_cross_currency_sum_in_marts(con):
    """Acceptance test 10: local-currency money columns are always grouped by currency."""
    cols = con.execute(
        "SELECT table_name FROM information_schema.columns WHERE column_name = 'm06_tpv_local'"
    ).fetchall()
    for (table,) in cols:
        has_currency = con.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = 'currency'",
            [table],
        ).fetchone()[0]
        assert has_currency, table


def test_all_analyses_execute(con):
    names = list(analyses())
    assert 12 <= len(names) <= 20
    for name in names:
        df = run_analysis(con, name)
        if name != "q14_anomaly_days":  # anomalies may legitimately be absent
            assert len(df) > 0, name


def test_daily_spine_is_dense(con):
    df = run_analysis(con, "q01_daily_trend_7d")
    per_country = df.groupby("country")["created_date_local"].nunique()
    span = (df["created_date_local"].max() - df["created_date_local"].min()).days + 1
    assert (per_country == span).all()


def test_cohorts_use_activation_and_flag_left_censoring(con):
    c = con.execute(
        "SELECT cohort_type, cohort_month, cohort_size, months_since_cohort, merchant_retention "
        "FROM mart_merchant_cohorts"
    ).df()
    assert set(c["cohort_type"]) <= {"activated_in_window", "pre_window"}
    sizes = c.drop_duplicates(["cohort_type", "cohort_month"])["cohort_size"].sum()
    assert sizes == con.execute("SELECT COUNT(*) FROM dim_merchant").fetchone()[0]
    pre = con.execute(
        "SELECT COUNT(*) FROM dim_merchant WHERE activation_date < "
        "(SELECT MIN(created_month_local) FROM fct_payment)"
    ).fetchone()[0]
    got_pre = c.loc[c["cohort_type"] == "pre_window", "cohort_size"].drop_duplicates().sum()
    assert got_pre == pre
    assert (c["months_since_cohort"] >= 0).all()
    assert c["merchant_retention"].between(0, 1).all()
