"""P2 command line (from the repo root, venv active).

    python -m fintech_lab.p2_forecasting.cli build     # mart + checks + budget v1 + export
    python -m fintech_lab.p2_forecasting.cli check     # checks only (no export)
    python -m fintech_lab.p2_forecasting.cli backtest [--workers 4] [--freeze]  # validation only
    python -m fintech_lab.p2_forecasting.cli holdout   # T4, requires frozen champions
    python -m fintech_lab.p2_forecasting.cli budget-v2 # run-rate reforecast frozen at the as-of
    python -m fintech_lab.p2_forecasting.cli pipeline  # build + backtest + holdout + v2 + close
    python -m fintech_lab.p2_forecasting.cli dashboard # Streamlit cockpit (runs pipeline if needed)
    python -m fintech_lab.p2_forecasting.cli audit     # independent recompute from raw P1
    python -m fintech_lab.p2_forecasting.cli close     # P2.4 bridges, scenarios, alerts, report
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd

from fintech_lab.p2_forecasting import budget
from fintech_lab.p2_forecasting.config import (
    DEFAULT_ALERTS,
    DEFAULT_ASSUMPTIONS,
    DEFAULT_BACKTEST,
    DEFAULT_BUDGET,
    DEFAULT_BUDGET_V2,
    DEFAULT_BUDGET_V2_RULES,
    DEFAULT_CHAMPIONS,
    DEFAULT_OUT,
    DEFAULT_P1_DATA,
    DEFAULT_SCENARIOS,
    REPORTS,
    d,
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


def _data_hash(data: Path) -> str:
    m = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    return hashlib.sha256(json.dumps(m["tables"], sort_keys=True).encode()).hexdigest()


def _targets(cfg: dict) -> list[str]:
    return [*cfg["targets"]["totals"], *[f"tpv_{c}" for c in cfg["targets"]["tpv_by_country"]]]


def _backtest(a: argparse.Namespace) -> int:
    from fintech_lab.p2_forecasting import backtest as bt
    from fintech_lab.p2_forecasting.reporting import md_table
    from fintech_lab.p2_forecasting.series import load_targets

    cfg = bt.load_cfg(a.config)
    data = Path(a.out)
    series = load_targets(data, cfg["targets"]["tpv_by_country"], d(cfg["as_of"]))
    t0 = time.perf_counter()
    fc, logs = bt.run_backtest(series, cfg, workers=a.workers)
    summ = bt.summarize(fc, logs, cfg)
    champs = bt.select_champions(fc, summ, cfg)
    bdir = data / "backtest"
    bdir.mkdir(parents=True, exist_ok=True)
    fc.to_parquet(bdir / "fct_backtest_forecast.parquet", index=False)
    summ.to_parquet(bdir / "fct_backtest_metrics.parquet", index=False)
    logs.assign(info=logs["info"].astype(str)).to_parquet(bdir / "fit_log.parquet", index=False)
    rep = Path(a.reports)
    rep.mkdir(parents=True, exist_ok=True)
    # machine-dependent timings stay in the parquet only, so reruns do not dirty the versioned CSV
    summ.drop(columns=["sec_per_fit"]).to_csv(rep / "backtest_metrics.csv", index=False)
    champs.to_csv(rep / "champions.csv", index=False)
    comp = (summ.pivot_table(index=["target", "model"], columns="horizon", values="wape")
            .assign(composite=lambda x: x.mean(axis=1, skipna=False)).reset_index())
    comp.columns = [str(c) if not isinstance(c, str) else c for c in comp.columns]
    head = ("# P2.3 backtest (validation only, origins up to as-of 2025-09-30)\n\n"
            "WAPE pooled over origins and days; full windows only. "
            "`composite` = mean of horizons.\n\n")
    body = (md_table(comp, pct=("7", "30", "90", "composite"))
            + "\n\n## Champions\n\n" + md_table(champs, digits=4) + "\n")
    (rep / "backtest_summary.md").write_text(head + body, encoding="utf-8")
    n_failed = int(logs["failed"].sum())
    print(f"backtest done in {time.perf_counter() - t0:.0f}s; failed fits: {n_failed}")
    cols = ["target", "champion", "composite_wape", "best_baseline", "reason"]
    print(champs[cols].to_string(index=False))
    if a.freeze:
        doc = bt.freeze_champions(champs, cfg, _data_hash(data), a.champions)
        print(f"champions frozen -> {a.champions} ({len(doc['champions'])} targets)")
    return 0


def _holdout(a: argparse.Namespace) -> int:
    from fintech_lab.p2_forecasting import backtest as bt
    from fintech_lab.p2_forecasting.holdout import run_holdout
    from fintech_lab.p2_forecasting.reporting import md_table
    from fintech_lab.p2_forecasting.series import load_targets

    if not Path(a.champions).exists():
        print("champions not frozen: run `backtest --freeze` first", file=sys.stderr)
        return 1
    cfg = bt.load_cfg(a.config)
    data = Path(a.out)
    series = load_targets(data, cfg["targets"]["tpv_by_country"], None)
    budget = pd.read_parquet(data / "budget_v1.parquet")
    daily, summ = run_holdout(series, cfg, a.champions, budget, _data_hash(data))
    daily.to_parquet(data / "backtest" / "fct_holdout_forecast.parquet", index=False)
    rep = Path(a.reports)
    rep.mkdir(parents=True, exist_ok=True)
    summ.to_csv(rep / "holdout_t4.csv", index=False)
    pct = ("forecast_err_pct", "budget_err_pct", "wape_daily", "bias", "cov80", "cov95",
           "wape_h7", "wape_h30", "wape_h90")
    head = ("# P2.3 holdout T4/2025 (champions frozen before this run)\n\n"
            "Errors are (forecast or budget - actual) / actual on the 92-day total. "
            "Not used for any model choice.\n\n")
    table = md_table(summ, pct=pct, money=("actual_t4", "forecast_t4", "budget_t4"))
    (rep / "holdout_t4.md").write_text(head + table + "\n", encoding="utf-8")
    print(summ[["target", "champion", "forecast_err_pct", "budget_err_pct", "wape_daily"]]
          .round(4).to_string(index=False))
    return 0


def _budget_v2(a: argparse.Namespace) -> int:
    import yaml

    data = Path(a.out)
    rules = yaml.safe_load(Path(a.rules).read_text(encoding="utf-8"))
    cfg = load_assumptions(a.assumptions)
    if Path(a.budget_v2).exists():
        doc = budget.load_frozen(a.budget_v2)
        if not budget.verify_v2(doc, rules, cfg):
            print("FAIL  budget v2 changed after freeze", file=sys.stderr)
            return 1
        print("budget v2 already frozen and verified")
    else:
        frozen = budget.calibrate_v2(pd.read_parquet(data / "fct_monthly.parquet"),
                                     pd.read_parquet(data / "fct_daily_segment.parquet"), rules)
        doc = budget.freeze_v2(frozen, rules, cfg, a.budget_v2)
        print(f"budget v2 frozen -> {a.budget_v2}")
    keys = ("base_daily_tpv_brl", "monthly_growth", "take_rate", "rc_share", "proc_share",
            "rules_version", "data_cutoff")
    table = budget.build_budget_v2({k: doc[k] for k in keys}, rules, cfg)
    table.to_parquet(data / "budget_v2.parquet", index=False)
    print(table.groupby("month")[["tpv_brl", "net_revenue_brl", "contribution_brl"]].sum().round(0))
    return 0


def _close(a: argparse.Namespace) -> int:
    import yaml

    from fintech_lab.p2_forecasting import backtest as bt
    from fintech_lab.p2_forecasting.closing import run_closing

    load = lambda p: yaml.safe_load(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    if not Path(a.champions).exists():
        print("champions not frozen: run `backtest --freeze` and `holdout` first", file=sys.stderr)
        return 1
    o = run_closing(a.out, load_assumptions(a.assumptions), bt.load_cfg(a.config),
                    load(a.scenarios), load(a.alerts), a.champions, a.reports)
    from fintech_lab.p2_forecasting.onepager import build_onepager

    man = json.loads((Path(a.out) / "manifest.json").read_text(encoding="utf-8"))
    bcfg = bt.load_cfg(a.config)
    meta = {"as_of": str(bcfg["as_of"]), "backtest_version": bcfg["version"],
            "assumptions_version": man["assumptions_version"], "p1_seed": man["p1"]["seed"]}
    (Path(a.reports) / "executive_one_pager.html").write_text(build_onepager(o, meta),
                                                              encoding="utf-8")
    print(o["headline"][["metric", "budget", "forecast_composed", "actual", "actual_vs_budget_pct"]]
          .round(3).to_string(index=False))
    sev = o["alerts_ex_ante"]["severity"].value_counts().to_dict()
    print("ex-ante alerts:", sev, "| report -> reports/executive_closing_report.md")
    return 0


def _pipeline(a: argparse.Namespace) -> int:
    from fintech_lab.p2_forecasting.config import P2_ROOT
    from fintech_lab.p2_forecasting.pipeline import run_all

    run_all(a.p1_data, a.out, P2_ROOT / "configs", REPORTS, workers=a.workers)
    return 0


def _dashboard(a: argparse.Namespace) -> int:
    import subprocess

    from fintech_lab.p2_forecasting.config import P2_ROOT
    from fintech_lab.p2_forecasting.pipeline import artifacts_ready, run_all

    if not artifacts_ready(a.out):
        print("P2 artifacts missing: running the pipeline first")
        run_all(a.p1_data, a.out, P2_ROOT / "configs", REPORTS, workers=a.workers)
    import json as _json

    from fintech_lab.p1_payments.generator import REPO_ROOT

    c = _json.loads((REPO_ROOT / "shared" / "design_tokens" / "tokens.json").read_text())["color"]
    cmd = [sys.executable, "-m", "streamlit", "run", str(P2_ROOT / "app" / "app.py"),
           "--server.port", str(a.port), "--server.headless", "true",
           "--browser.gatherUsageStats", "false", "--theme.base", "light",
           "--theme.primaryColor", c["primary"], "--theme.textColor", c["text"],
           "--theme.backgroundColor", c["bg"], "--theme.secondaryBackgroundColor", c["surface"]]
    print(f"dashboard -> http://localhost:{a.port}")
    return subprocess.call(cmd)


def _audit(a: argparse.Namespace) -> int:
    from fintech_lab.p2_forecasting.audit import run_audit, write_report
    from fintech_lab.p2_forecasting.config import P2_ROOT

    checks = run_audit(a.p1_data, a.out, P2_ROOT / "configs", REPORTS)
    write_report(checks, REPORTS / "audit_p2.md")
    for n, ok, det in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {n}  {det}")
    return 0 if all(ok for _, ok, _ in checks) else 1


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
    for name, fn in (("backtest", _backtest), ("holdout", _holdout)):
        q = sub.add_parser(name)
        q.add_argument("--config", default=str(DEFAULT_BACKTEST))
        q.add_argument("--out", default=str(DEFAULT_OUT))
        q.add_argument("--champions", default=str(DEFAULT_CHAMPIONS))
        q.add_argument("--reports", default=str(REPORTS))
        q.set_defaults(fn=fn)
        if name == "backtest":
            q.add_argument("--workers", type=int, default=1)
            q.add_argument("--freeze", action="store_true")
    for name, fn in (("pipeline", _pipeline), ("dashboard", _dashboard)):
        q = sub.add_parser(name)
        q.add_argument("--out", default=str(DEFAULT_OUT))
        q.add_argument("--workers", type=int, default=4)
        if name == "dashboard":
            q.add_argument("--port", type=int, default=8503)
        q.set_defaults(fn=fn)
    au = sub.add_parser("audit")
    au.add_argument("--out", default=str(DEFAULT_OUT))
    au.set_defaults(fn=_audit)
    bv = sub.add_parser("budget-v2")
    bv.add_argument("--out", default=str(DEFAULT_OUT))
    bv.add_argument("--rules", default=str(DEFAULT_BUDGET_V2_RULES))
    bv.add_argument("--budget-v2", default=str(DEFAULT_BUDGET_V2))
    bv.set_defaults(fn=_budget_v2)
    cl = sub.add_parser("close")
    cl.add_argument("--config", default=str(DEFAULT_BACKTEST))
    cl.add_argument("--out", default=str(DEFAULT_OUT))
    cl.add_argument("--champions", default=str(DEFAULT_CHAMPIONS))
    cl.add_argument("--scenarios", default=str(DEFAULT_SCENARIOS))
    cl.add_argument("--alerts", default=str(DEFAULT_ALERTS))
    cl.add_argument("--reports", default=str(REPORTS))
    cl.set_defaults(fn=_close)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
