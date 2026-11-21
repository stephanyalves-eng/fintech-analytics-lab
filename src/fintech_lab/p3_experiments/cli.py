"""P3 command line.

Examples (from the repo root, venv active)::

    python -m fintech_lab.p3_experiments.cli size      # sample size / power -> reports/
    python -m fintech_lab.p3_experiments.cli lock      # SHA-256 lock of the preregistered protocol
    python -m fintech_lab.p3_experiments.cli lock --amend "reason"
    python -m fintech_lab.p3_experiments.cli verify    # exit 1 if the protocol changed
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
              f"power@plan={r.power_at_plan}")
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="p3", description="P3 experimentation lab")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("size", help="pre-experiment sample size and power").set_defaults(func=_size)
    k = sub.add_parser("lock", help="lock the preregistered protocol")
    k.add_argument("--amend", default=None, help="reason for re-locking a changed protocol")
    k.set_defaults(func=_lock)
    sub.add_parser("verify", help="verify protocol hashes").set_defaults(func=_verify)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
