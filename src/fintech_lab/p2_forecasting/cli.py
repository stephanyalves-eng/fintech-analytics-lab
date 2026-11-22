"""P2 command line (from the repo root, venv active).

    python -m fintech_lab.p2_forecasting.cli build     # mart + checks + budget v1 + export
    python -m fintech_lab.p2_forecasting.cli check     # checks only (no export)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from fintech_lab.p2_forecasting import budget
from fintech_lab.p2_forecasting.config import (
    DEFAULT_ASSUMPTIONS,
    DEFAULT_BUDGET,
    DEFAULT_OUT,
    DEFAULT_P1_DATA,
    load_assumptions,
)
from fintech_lab.p2_forecasting.features import validate_splits
from fintech_lab.p2_forecasting.mart import build_mart, export, run_checks


def _report(results: dict[str, int]) -> bool:
    for name, n in results.items():
        print(f"{'PASS' if n == 0 else 'FAIL'}  {name}  violations={n}")
    return all(n == 0 for n in results.values())


def _build(a: argparse.Namespace) -> int:
    cfg = load_assumptions(a.assumptions)
    validate_splits(cfg)
    t0 = time.perf_counter()
    con = build_mart(a.p1_data, cfg)
    results = run_checks(con, cfg)
    ok = _report(results)
    if not ok:
        print("checks failed: nothing exported", file=sys.stderr)
        return 1
    if not Path(a.budget).exists():
        frozen = budget.calibrate(con.execute("SELECT * FROM fct_daily_merchant").df(), cfg)
        budget.freeze(frozen, cfg, a.budget)
        print(f"budget v1 frozen -> {a.budget}")
    doc = budget.load_frozen(a.budget)
    if not budget.verify(doc, cfg):
        print("FAIL  r10_budget_hash: budget v1 changed after freeze", file=sys.stderr)
        return 1
    print("PASS  r10_budget_hash")
    out = Path(a.out)
    manifest = export(con, out, cfg, a.p1_data, results)
    tbl = budget.build_budget({k: doc[k] for k in ("base_daily_tpv_brl", "take_rate",
                                                   "calibration_window", "calibration_rows")}, cfg)
    tbl.to_parquet(out / "budget_v1.parquet", index=False)
    print(f"built in {time.perf_counter() - t0:.1f}s; rows: "
          + ", ".join(f"{k}={v['rows']}" for k, v in manifest["tables"].items()))
    return 0


def _check(a: argparse.Namespace) -> int:
    cfg = load_assumptions(a.assumptions)
    con = build_mart(a.p1_data, cfg)
    return 0 if _report(run_checks(con, cfg)) else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="p2")
    p.add_argument("--assumptions", default=str(DEFAULT_ASSUMPTIONS))
    p.add_argument("--p1-data", default=str(DEFAULT_P1_DATA))
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    b.add_argument("--budget", default=str(DEFAULT_BUDGET))
    b.set_defaults(fn=_build)
    c = sub.add_parser("check")
    c.set_defaults(fn=_check)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
