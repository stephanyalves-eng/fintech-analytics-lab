"""P1 command line.

Examples (from the repo root, venv active)::

    python -m fintech_lab.p1_payments.cli generate                      # 500k attempts
    python -m fintech_lab.p1_payments.cli generate --attempts 2000000 --out data/p1/large
    python -m fintech_lab.p1_payments.cli corrupt                       # data-quality fixture
    python -m fintech_lab.p1_payments.cli build                         # DuckDB marts
    python -m fintech_lab.p1_payments.cli check                         # contract + reconciliation
    python -m fintech_lab.p1_payments.cli explain                       # EXPLAIN ANALYZE report
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import duckdb

from fintech_lab.p1_payments.corrupt import make_corrupted
from fintech_lab.p1_payments.generator import P1_ROOT, REPO_ROOT, generate, load_config
from fintech_lab.p1_payments.io import write_dataset
from fintech_lab.p1_payments.warehouse import analyses, build, connect, explain_analyze, run_checks

DEFAULT_DATA = REPO_ROOT / "data" / "p1" / "default"
DEFAULT_CORRUPTED = REPO_ROOT / "data" / "p1" / "corrupted"
DEFAULT_DB = REPO_ROOT / "data" / "p1" / "p1.duckdb"
EXPLAIN_QUERIES = ("q04_acquirer_mix_adjusted", "q08_retry_timing", "q11_merchant_concentration")


def _generate(a: argparse.Namespace) -> int:
    t0 = time.perf_counter()
    cfg = load_config(a.config, seed=a.seed, target_attempts=a.attempts, n_merchants=a.merchants)
    tables = generate(cfg)
    man = write_dataset(tables, a.out, cfg)
    rows = {k: v["rows"] for k, v in man["tables"].items()}
    print(
        json.dumps(
            {
                "out": str(a.out),
                "seed": cfg["seed"],
                "rows": rows,
                "dataset_content_sha256": man["dataset_content_sha256"],
                "seconds": round(time.perf_counter() - t0, 1),
            },
            indent=2,
        )
    )
    return 0


def _corrupt(a: argparse.Namespace) -> int:
    cfg = load_config(a.config)
    tables, extra = make_corrupted(cfg)
    man = write_dataset(tables, a.out, cfg, kind="corrupted", extra=extra)
    print(
        json.dumps({"out": str(a.out), "injected_defects": list(man["injected_defects"])}, indent=2)
    )
    return 0


def _build(a: argparse.Namespace) -> int:
    Path(a.db).parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    with connect(a.db) as con:
        build(con, a.data)
    print(f"built {a.db} from {a.data} in {time.perf_counter() - t0:.1f}s")
    return 0


def _check(a: argparse.Namespace) -> int:
    with connect() as con:
        build(con, a.data, marts=not a.contract_only)
        results = run_checks(con, "contract")
        if not a.contract_only:
            results |= run_checks(con, "reconciliation")
    for name, n in results.items():
        print(f"{'PASS' if n == 0 else 'FAIL'}  {name}  violations={n}")
    return 0 if all(n == 0 for n in results.values()) else 1


def _explain(a: argparse.Namespace) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with connect(a.db) as con:
        sizes = {
            t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("fct_payment", "fct_attempt")
        }
        threads = con.execute("SELECT current_setting('threads')").fetchone()[0]
        header = [
            "-- data_origin: derived from synthetic data (observed plan, not a benchmark claim)",
            f"-- duckdb {duckdb.__version__} | python {platform.python_version()}",
            f"-- os: {platform.platform()}",
            f"-- cpu: {platform.processor()} | logical cores: {os.cpu_count()}",
            f"-- duckdb threads: {threads}",
            f"-- dataset: fct_payment={sizes['fct_payment']:,} rows, "
            f"fct_attempt={sizes['fct_attempt']:,} rows",
        ]
        q = analyses()
        for name in EXPLAIN_QUERIES:
            con.execute(q[name]).fetchall()  # warm-up run
            t0 = time.perf_counter()
            con.execute(q[name]).fetchall()
            wall = time.perf_counter() - t0
            plan = explain_analyze(con, q[name])
            text = "\n".join(
                [*header, f"-- query: {name} | wall time (2nd run): {wall * 1000:.1f} ms", "", plan]
            )
            (out / f"{name}.txt").write_text(text + "\n", encoding="utf-8")
            print(f"{name}: {wall * 1000:.1f} ms -> {out / (name + '.txt')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="p1", description="P1 synthetic payments toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate the clean synthetic dataset")
    g.add_argument("--config", default=None)
    g.add_argument("--out", type=Path, default=DEFAULT_DATA)
    g.add_argument("--seed", type=int, default=None)
    g.add_argument("--attempts", type=int, default=None)
    g.add_argument("--merchants", type=int, default=None)
    g.set_defaults(func=_generate)

    c = sub.add_parser("corrupt", help="write the deliberately corrupted DQ fixture")
    c.add_argument("--config", default=None)
    c.add_argument("--out", type=Path, default=DEFAULT_CORRUPTED)
    c.set_defaults(func=_corrupt)

    b = sub.add_parser("build", help="build the DuckDB warehouse")
    b.add_argument("--data", type=Path, default=DEFAULT_DATA)
    b.add_argument("--db", type=Path, default=DEFAULT_DB)
    b.set_defaults(func=_build)

    k = sub.add_parser("check", help="run contract (+ reconciliation) checks")
    k.add_argument("--data", type=Path, default=DEFAULT_DATA)
    k.add_argument("--contract-only", action="store_true")
    k.set_defaults(func=_check)

    e = sub.add_parser("explain", help="EXPLAIN ANALYZE selected analyses")
    e.add_argument("--db", type=Path, default=DEFAULT_DB)
    e.add_argument("--out", type=Path, default=P1_ROOT / "reports" / "query_plans")
    e.set_defaults(func=_explain)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
