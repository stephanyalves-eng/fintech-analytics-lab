"""DuckDB analytics layer for P1 (P1.3): staging views, marts, checks and analyses."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

from fintech_lab.p1_payments.generator import P1_ROOT

SQL_DIR = P1_ROOT / "sql"
_NAME = re.compile(r"^-- name:\s*(\S+)\s*$", re.MULTILINE)


def connect(db_path: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute("SET TimeZone = 'UTC'")
    return con


def load_named(path: str | Path) -> dict[str, str]:
    """Split a SQL file into ``-- name: x`` blocks -> {name: sql without trailing ';'}."""
    text = Path(path).read_text(encoding="utf-8")
    parts = _NAME.split(text)
    return {parts[i]: parts[i + 1].strip().rstrip(";").strip() for i in range(1, len(parts), 2)}


def build(con: duckdb.DuckDBPyConnection, data_dir: str | Path, marts: bool = True) -> None:
    """Create staging views over ``data_dir`` and (optionally) materialize the marts."""
    data = Path(data_dir).resolve().as_posix().replace("'", "''")
    staging = (SQL_DIR / "staging" / "01_staging.sql").read_text(encoding="utf-8")
    con.execute(staging.replace("{data_dir}", data))
    if marts:
        for f in sorted((SQL_DIR / "marts").glob("*.sql")):
            con.execute(f.read_text(encoding="utf-8"))


def run_checks(con: duckdb.DuckDBPyConnection, suite: str = "contract") -> dict[str, int]:
    """Run a check suite (``contract`` or ``reconciliation``) -> {check: violating rows}."""
    checks = load_named(SQL_DIR / "checks" / f"{suite}.sql")
    return {
        name: con.execute(f"SELECT COUNT(*) FROM (\n{sql}\n)").fetchone()[0]
        for name, sql in checks.items()
    }


def analyses() -> dict[str, str]:
    return load_named(SQL_DIR / "analyses" / "analyses.sql")


def run_analysis(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    return con.execute(analyses()[name]).df()


def explain_analyze(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    rows = con.execute(f"EXPLAIN ANALYZE {sql}").fetchall()
    return "\n".join(str(r[-1]) for r in rows)
