"""Build the P2 daily forecasting mart on top of the P1 warehouse (DuckDB) and export it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from fintech_lab.p1_payments.io import config_hash, content_hash
from fintech_lab.p1_payments.warehouse import build as build_p1
from fintech_lab.p1_payments.warehouse import connect, load_named
from fintech_lab.p2_forecasting.adjustments import generate_adjustments
from fintech_lab.p2_forecasting.calendar import build_calendar
from fintech_lab.p2_forecasting.config import SQL_DIR, d
from fintech_lab.shared.provenance import DataOrigin, environment

MART_TABLES = ("fct_daily_merchant", "fct_daily_segment", "fct_daily_total", "fct_monthly")
EXPORT_TABLES = (*MART_TABLES, "dim_calendar", "syn_adjustment")
VERSION = "p2.2-0.1"


def _fmt(sql: str, cfg: dict[str, Any]) -> str:
    sub = {
        "{win_start}": str(cfg["window"]["start"]),
        "{win_end}": str(cfg["window"]["end"]),
        "{incentive_rate}": repr(float(cfg["incentive_rate"])),
        "{var_cost_rate}": repr(float(cfg["var_cost_rate"])),
    }
    for k, v in sub.items():
        sql = sql.replace(k, v)
    return sql


def build_mart(p1_data: str | Path, cfg: dict[str, Any]) -> duckdb.DuckDBPyConnection:
    """P1 core + P2 tables in one in-memory connection (nothing is written to P1 files)."""
    con = connect()
    build_p1(con, p1_data, marts=True)
    blocks = load_named(SQL_DIR / "mart.sql")

    con.execute(_fmt(blocks["p2_payment_fin"], cfg))
    pay = con.execute(
        "SELECT payment_id, merchant_id, method_code, date_local, tpv_brl AS amount_brl, fee_brl "
        "FROM p2_payment_fin"
    ).df()
    adj = generate_adjustments(pay, cfg)
    con.register("adj_df", adj)
    con.execute(
        """CREATE OR REPLACE TABLE syn_adjustment AS
           SELECT payment_id, merchant_id, method_code, event_type,
                  CAST(event_date_local AS DATE) AS event_date_local,
                  CAST(ROUND(amount_brl, 4) AS DECIMAL(18, 4)) AS amount_brl,
                  CAST(ROUND(fee_returned_brl, 4) AS DECIMAL(18, 4)) AS fee_returned_brl,
                  CAST(ROUND(chargeback_fee_brl, 4) AS DECIMAL(18, 4)) AS chargeback_fee_brl
           FROM adj_df"""
    )
    con.unregister("adj_df")

    cal = build_calendar(d(cfg["window"]["start"]), d(cfg["window"]["end"]))
    con.register("cal_df", cal)
    con.execute("CREATE OR REPLACE TABLE dim_calendar AS SELECT * FROM cal_df")
    con.unregister("cal_df")

    for name, sql in blocks.items():
        if name != "p2_payment_fin":
            con.execute(_fmt(sql, cfg))
    return con


def run_checks(con: duckdb.DuckDBPyConnection, cfg: dict[str, Any]) -> dict[str, int]:
    checks = load_named(SQL_DIR / "checks.sql")
    return {
        name: con.execute(f"SELECT COUNT(*) FROM (\n{_fmt(sql, cfg)}\n)").fetchone()[0]
        for name, sql in checks.items()
    }


def _hashable(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype({c: str for c in df.columns if df[c].dtype == object})


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(
    con: duckdb.DuckDBPyConnection, out_dir: str | Path, cfg: dict[str, Any],
    p1_data: str | Path, check_results: dict[str, int],
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables: dict[str, Any] = {}
    for name in EXPORT_TABLES:
        order = {
            "fct_daily_merchant": "date_local, merchant_id",
            "fct_daily_segment": "date_local, country, method_code, size_tier",
            "fct_daily_total": "date_local",
            "fct_monthly": "month, country",
            "dim_calendar": "date_local",
            "syn_adjustment": "payment_id, event_type",
        }[name]
        df = con.execute(f"SELECT * FROM {name} ORDER BY {order}").df()
        target = (out / f"{name}.parquet").as_posix()
        con.execute(f"COPY (SELECT * FROM {name} ORDER BY {order}) TO '{target}' (FORMAT parquet)")
        origin = "synthetic" if name == "syn_adjustment" else "derived"
        tables[name] = {"rows": len(df), "content_hash": content_hash(_hashable(df)),
                        "data_origin": origin}
    n_censored = con.execute(
        "SELECT COUNT(*) FROM syn_adjustment WHERE event_date_local > CAST(? AS DATE)",
        [str(cfg["window"]["end"])],
    ).fetchone()[0]
    p1_manifest = Path(p1_data) / "manifest.json"
    manifest = {
        "version": VERSION,
        "data_origin": DataOrigin.DERIVED.value,
        "notice": "Derived from synthetic P1 payments + synthetic refunds/chargebacks. Not real.",
        "assumptions_version": cfg["version"],
        "assumptions_hash": config_hash(cfg),
        "window": cfg["window"], "as_of": str(cfg["as_of"]), "splits": cfg["splits"],
        "p1": {"seed": json.loads(p1_manifest.read_text(encoding="utf-8")).get("seed"),
               "manifest_sha256": _sha256_file(p1_manifest)},
        "adjustments": {
            "seed": cfg["seed"],
            "by_type": con.execute(
                "SELECT event_type, COUNT(*) FROM syn_adjustment GROUP BY 1 ORDER BY 1").fetchall(),
            "events_after_window_end_dropped_from_mart": n_censored,
        },
        "tables": tables,
        "checks": check_results,
        "environment": environment(),
    }
    text = json.dumps(manifest, indent=2, default=str)
    (out / "manifest.json").write_text(text, encoding="utf-8")
    return manifest
