"""P3 command line.

Examples (from the repo root, venv active)::

    python -m fintech_lab.p3_experiments.cli size      # sample size / power -> reports/
    python -m fintech_lab.p3_experiments.cli lock      # SHA-256 lock of the preregistered protocol
    python -m fintech_lab.p3_experiments.cli lock --amend "reason"
    python -m fintech_lab.p3_experiments.cli verify    # exit 1 if the protocol changed
    python -m fintech_lab.p3_experiments.cli generate [--scenario S]   # synthetic events -> data/p3
    python -m fintech_lab.p3_experiments.cli analyze  [--scenario S]   # analysis + memos -> reports/
    python -m fintech_lab.p3_experiments.cli montecarlo                # type I error / power
    python -m fintech_lab.p3_experiments.cli dashboard                 # Streamlit app
"""

from __future__ import annotations

import argparse
import sys

from fintech_lab.p3_experiments.lock import ProtocolLockError, verify_lock, write_lock
from fintech_lab.p3_experiments.power import load_protocol, plan, write_sample_size_csv


def _size(a: argparse.Namespace) -> int:
    result = plan(load_protocol())
    path = write_sample_size_csv(result)
    for r in result["rows"]:
        print(f"{r.metric_id:4} {r.metric:28} n/arm={r.users_per_arm_required:>7} "
              f"power@plan={r.power_at_plan}")  # fmt: skip
    for k, v in result.items():
        if k != "rows":
            print(f"{k}={v}")
    print(f"wrote {path}")
    return 0


def _lock(a: argparse.Namespace) -> int:
    try:
        lock = write_lock(amend_reason=a.amend)
    except ProtocolLockError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(f"locked {len(lock['files'])} files; amendments={len(lock['amendments'])}")
    return 0


def _verify(a: argparse.Namespace) -> int:
    try:
        verify_lock()
    except ProtocolLockError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    print("PASS protocol matches lock")
    return 0


def _scenarios(a: argparse.Namespace) -> tuple[str, ...]:
    from fintech_lab.p3_experiments.simulator import SCENARIOS

    return SCENARIOS if a.scenario in (None, "all") else (a.scenario,)


def _generate(a: argparse.Namespace) -> int:
    from fintech_lab.p3_experiments.simulator import write_scenario

    try:
        for s in _scenarios(a):
            print(f"wrote {write_scenario(s)}")
    except ProtocolLockError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    return 0


def _analyze(a: argparse.Namespace) -> int:
    from fintech_lab.p3_experiments.report import run_all

    try:
        res = run_all(_scenarios(a))
    except (ProtocolLockError, FileNotFoundError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    for s, r in res.items():
        p = r["primary"]
        print(f"{s:9} {r['decision']['decision']:14} P01 diff={p['diff']:+.4f} "
              f"[{p['ci_low']:+.4f},{p['ci_high']:+.4f}] srm_p={r['gates']['srm']['p_value']:.3g}")  # fmt: skip
    return 0


def _montecarlo(a: argparse.Namespace) -> int:
    from fintech_lab.p3_experiments.montecarlo import run_all, write_csv

    rows = run_all(reps=a.reps)
    print(f"wrote {write_csv(rows)}")
    for r in rows:
        print(f"{r['check']:42} rate={r['rate']:.4f}  expected: {r['expected']}")
    return 0


def _dashboard(a: argparse.Namespace) -> int:
    import json
    import os
    import subprocess

    from fintech_lab.p3_experiments.power import P3_ROOT, REPO_ROOT
    from fintech_lab.p3_experiments.simulator import DATA_ROOT, SCENARIOS, write_scenario

    for s in SCENARIOS:
        if not (DATA_ROOT / s / "manifest.json").exists():
            write_scenario(s)
    c = json.loads((REPO_ROOT / "shared" / "design_tokens" / "tokens.json").read_text())["color"]
    cmd = [sys.executable, "-m", "streamlit", "run", str(P3_ROOT / "app" / "app.py"),
           "--server.port", str(a.port), "--server.headless", "true",
           "--browser.gatherUsageStats", "false", "--theme.base", "light",
           "--theme.primaryColor", c["primary"], "--theme.backgroundColor", c["bg"],
           "--theme.secondaryBackgroundColor", c["surface"], "--theme.textColor", c["text"]]  # fmt: skip
    return subprocess.call(cmd, env={**os.environ, "P3_DATA_ROOT": str(DATA_ROOT)})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="p3", description="P3 experimentation lab")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("size", help="pre-experiment sample size and power").set_defaults(func=_size)
    k = sub.add_parser("lock", help="lock the preregistered protocol")
    k.add_argument("--amend", default=None, help="reason for re-locking a changed protocol")
    k.set_defaults(func=_lock)
    sub.add_parser("verify", help="verify protocol hashes").set_defaults(func=_verify)
    for name, fn, h in (("generate", _generate, "generate synthetic scenario data"),
                        ("analyze", _analyze, "run the locked analysis and write memos")):  # fmt: skip
        sp = sub.add_parser(name, help=h)
        sp.add_argument("--scenario", default="all")
        sp.set_defaults(func=fn)
    mc = sub.add_parser("montecarlo", help="Monte Carlo type I error / power")
    mc.add_argument("--reps", type=int, default=2000)
    mc.set_defaults(func=_montecarlo)
    dp = sub.add_parser("dashboard", help="launch the Streamlit dashboard")
    dp.add_argument("--port", type=int, default=8502)
    dp.set_defaults(func=_dashboard)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
