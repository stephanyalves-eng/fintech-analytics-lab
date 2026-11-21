"""P1.5 dashboard data services (pure functions over a DuckDB connection; testable).

Denominator rules (docs/metric_catalog.md), preserved under every filter:
- Payment-grain metrics (M02, M05, M06/M07, M09, M12) filter ``fct_payment`` and recompute
  ratios as SUM(numerator) / SUM(denominator) on the filtered rows, never averages of rates.
- Attempt-grain metrics (M01, M03, M04, M10, M11) filter ``fct_attempt``.
- The acquirer filter means *attempt acquirer* at attempt grain and *first-attempt acquirer*
  at payment grain (a payment can touch two acquirers). The app states this next to the filter.
- Date filter = payment local creation date for both grains (catalog period rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import duckdb
import pandas as pd

PAYMENT, ATTEMPT = "payment", "attempt"


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    countries: tuple[str, ...] = field(default_factory=tuple)
    methods: tuple[str, ...] = field(default_factory=tuple)
    acquirers: tuple[str, ...] = field(default_factory=tuple)


def where(f: Filters, grain: str) -> tuple[str, dict]:
    """SQL WHERE clause + named params for a grain (``payment`` or ``attempt``)."""
    acq_col = "first_acquirer_id" if grain == PAYMENT else "acquirer_id"
    conds, params = ["TRUE"], {}
    if f.date_from is not None:
        conds.append("created_date_local >= $date_from")
        params["date_from"] = f.date_from
    if f.date_to is not None:
        conds.append("created_date_local <= $date_to")
        params["date_to"] = f.date_to
    for col, key, vals in (
        ("country", "countries", f.countries),
        ("method_code", "methods", f.methods),
        (acq_col, "acquirers", f.acquirers),
    ):
        if vals:
            conds.append(f"list_contains(${key}, {col})")
            params[key] = list(vals)
    return " AND ".join(conds), params


def _q(con: duckdb.DuckDBPyConnection, sql: str, params: dict) -> pd.DataFrame:
    return con.execute(sql, params).df()


def options(con: duckdb.DuckDBPyConnection) -> dict:
    lo, hi = con.execute(
        "SELECT MIN(created_date_local), MAX(created_date_local) FROM fct_payment"
    ).fetchone()

    def distinct(col: str, table: str) -> list[str]:
        rows = con.execute(f"SELECT DISTINCT {col} FROM {table} ORDER BY 1").fetchall()
        return [r[0] for r in rows]

    return {
        "date_min": lo,
        "date_max": hi,
        "countries": distinct("country", "fct_payment"),
        "methods": distinct("method_code", "fct_payment"),
        "acquirers": distinct("acquirer_id", "fct_attempt"),
    }


def kpis(con: duckdb.DuckDBPyConnection, f: Filters) -> dict:
    """Headline KPIs. Payment- and attempt-grain blocks are computed separately."""
    wp, pp = where(f, PAYMENT)
    wa, pa = where(f, ATTEMPT)
    p = _q(
        con,
        f"""
        SELECT COUNT(*)                                             AS payments,
               COUNT(*) FILTER (WHERE is_succeeded)                 AS succeeded,
               SUM(n_attempts)                                      AS attempts_of_payments,
               COALESCE(SUM(amount_brl) FILTER (WHERE is_succeeded), 0) AS tpv_brl,
               COALESCE(SUM(processing_cost_brl), 0)                AS cost_brl,
               COUNT(*) FILTER (WHERE first_failed_retryable)       AS first_failed_retryable,
               COUNT(*) FILTER (WHERE recovered_by_retry)           AS recovered
        FROM fct_payment WHERE {wp}
        """,
        pp,
    ).iloc[0]
    a = _q(
        con,
        f"""
        SELECT COUNT(*)                                    AS attempts,
               COUNT(*) FILTER (WHERE result = 'approved') AS approved,
               COUNT(*) FILTER (WHERE result = 'error')    AS errors
        FROM fct_attempt WHERE {wa}
        """,
        pa,
    ).iloc[0]

    def ratio(n: float, d: float) -> float | None:
        return float(n) / float(d) if d else None

    payments = int(p["payments"])
    succeeded = int(p["succeeded"])
    return {
        "payments": payments,
        "succeeded": succeeded,
        "m02": ratio(succeeded, payments),
        "attempts": int(a["attempts"]),
        "approved": int(a["approved"]),
        "m01": ratio(a["approved"], a["attempts"]),
        "m10": ratio(a["errors"], a["attempts"]),
        "m12": ratio(p["attempts_of_payments"] or 0, payments),
        "tpv_brl": float(p["tpv_brl"]),
        "cost_brl": float(p["cost_brl"]),
        "m09": ratio(p["cost_brl"], succeeded),
        "m05": ratio(p["recovered"], p["first_failed_retryable"]),
        "first_failed_retryable": int(p["first_failed_retryable"]),
    }


def daily(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    """Payment-grain daily M02 and TPV; attempt-grain daily M01 (separate denominators)."""
    wp, pp = where(f, PAYMENT)
    wa, pa = where(f, ATTEMPT)
    pay = _q(
        con,
        f"""
        SELECT created_date_local AS day, COUNT(*) AS payments,
               COUNT(*) FILTER (WHERE is_succeeded) AS succeeded,
               COALESCE(SUM(amount_brl) FILTER (WHERE is_succeeded), 0) AS tpv_brl
        FROM fct_payment WHERE {wp} GROUP BY 1
        """,
        pp,
    )
    att = _q(
        con,
        f"""
        SELECT created_date_local AS day, COUNT(*) AS attempts,
               COUNT(*) FILTER (WHERE result = 'approved') AS approved
        FROM fct_attempt WHERE {wa} GROUP BY 1
        """,
        pa,
    )
    d = pay.merge(att, on="day", how="outer").fillna(0).sort_values("day")
    d["m02"] = d["succeeded"] / d["payments"].where(d["payments"] > 0)
    d["m01"] = d["approved"] / d["attempts"].where(d["attempts"] > 0)
    return d.reset_index(drop=True)


def monthly_tpv(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    wp, pp = where(f, PAYMENT)
    return _q(
        con,
        f"""
        SELECT created_month_local AS month, country,
               COUNT(*) FILTER (WHERE is_succeeded) AS succeeded,
               COALESCE(SUM(amount_brl) FILTER (WHERE is_succeeded), 0) AS tpv_brl
        FROM fct_payment WHERE {wp} GROUP BY ALL ORDER BY ALL
        """,
        pp,
    )


def declines(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    """Failure codes at attempt grain with both denominators (all attempts / failed)."""
    wa, pa = where(f, ATTEMPT)
    return _q(
        con,
        f"""
        WITH base AS (SELECT * FROM fct_attempt WHERE {wa}),
        tot AS (SELECT COUNT(*) AS attempts,
                       COUNT(*) FILTER (WHERE result <> 'approved') AS failed FROM base)
        SELECT decline_category AS category, reason_group, decline_code,
               COUNT(*) AS failed_attempts,
               COUNT(*) / ANY_VALUE(tot.attempts) AS share_of_attempts,
               COUNT(*) / ANY_VALUE(tot.failed)   AS m04_share_of_failed
        FROM base, tot
        WHERE base.result <> 'approved'
        GROUP BY ALL
        ORDER BY failed_attempts DESC
        """,
        pa,
    )


def acquirers(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    wa, pa = where(f, ATTEMPT)
    return _q(
        con,
        f"""
        SELECT country, acquirer_id, COUNT(*) AS attempts,
               COUNT(*) FILTER (WHERE result = 'approved') / COUNT(*) AS m01,
               COUNT(*) FILTER (WHERE decline_category = 'soft') / COUNT(*) AS m03_soft,
               COUNT(*) FILTER (WHERE decline_category = 'hard') / COUNT(*) AS m03_hard,
               COUNT(*) FILTER (WHERE result = 'error') / COUNT(*) AS m10,
               quantile_cont(latency_ms, 0.50) AS p50_ms,
               quantile_cont(latency_ms, 0.95) AS p95_ms,
               SUM(processing_cost_brl) AS cost_brl
        FROM fct_attempt WHERE {wa}
        GROUP BY ALL ORDER BY country, acquirer_id
        """,
        pa,
    )


def error_by_hour(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    wa, pa = where(f, ATTEMPT)
    return _q(
        con,
        f"""
        SELECT country, acquirer_id, attempted_hour_local AS hour, COUNT(*) AS attempts,
               COUNT(*) FILTER (WHERE result = 'error') / COUNT(*) AS m10
        FROM fct_attempt WHERE {wa}
        GROUP BY ALL ORDER BY country, acquirer_id, hour
        """,
        pa,
    )


def retry_recovery(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    """M05 by first failure category (denominator: first attempt failed soft/technical)."""
    wp, pp = where(f, PAYMENT)
    return _q(
        con,
        f"""
        SELECT country, first_category,
               COUNT(*) AS payments_first_failed,
               COUNT(*) FILTER (WHERE n_attempts > 1) AS retried,
               COUNT(*) FILTER (WHERE recovered_by_retry) AS recovered,
               COUNT(*) FILTER (WHERE recovered_by_retry) / COUNT(*) AS m05
        FROM fct_payment
        WHERE {wp} AND first_failed_retryable
        GROUP BY ALL ORDER BY ALL
        """,
        pp,
    )


def attempt_ladder(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    """Marginal M01 by attempt_no and whether the retry switched acquirer (observational)."""
    wa, pa = where(f, ATTEMPT)
    return _q(
        con,
        f"""
        SELECT attempt_no,
               CASE WHEN attempt_no = 1 THEN 'first attempt'
                    WHEN switched_acquirer THEN 'retry, switched acquirer'
                    ELSE 'retry, same acquirer' END AS route,
               COUNT(*) AS attempts,
               COUNT(*) FILTER (WHERE result = 'approved') / COUNT(*) AS m01
        FROM fct_attempt WHERE {wa}
        GROUP BY ALL ORDER BY ALL
        """,
        pa,
    )
