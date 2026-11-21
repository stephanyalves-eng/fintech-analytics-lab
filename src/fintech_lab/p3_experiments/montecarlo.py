"""Monte Carlo check of Type I error and power (P3.3.f), on controlled SYNTHETIC scenarios.

Users are simulated directly (not through the event simulator) and fed to the SAME estimators the
analysis uses (`two_proportions`, `ratio_cluster`, `status_from_bounds`). G3 (p95 latency) and G4
(cost ratio) are NOT covered: no closed form and the bootstrap would be costly -> [TO VERIFY].
Joint Launch power covers P01, G1, G2 and G5 only, assuming guardrails with no degradation.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

from fintech_lab.p3_experiments.analysis import (
    Z,
    ratio_cluster,
    status_from_bounds,
    two_proportions,
)
from fintech_lab.p3_experiments.power import P3_ROOT, load_protocol, plan

MC_CSV = P3_ROOT / "reports" / "monte_carlo.csv"
SEED = 20260322


def _g1_user_arrays(rng, n: int, conv: float, cb: float):
    """Per user: approved payments (0 if not converted, else 1 + Bernoulli(0.25)) and chargebacks."""
    appr = (rng.random(n) < conv) * (1 + (rng.random(n) < 0.25))
    return rng.binomial(appr, cb).astype(float), appr.astype(float)


def _g2_user_arrays(rng, n: int, err: float):
    att = (rng.random(n) < 0.75) * (1 + rng.poisson(0.867, n))
    return rng.binomial(att, err).astype(float), att.astype(float)


def _ratio_status(arrs_a, arrs_b, margin: float) -> tuple[str, float, float]:
    ra, va, _ = ratio_cluster(*arrs_a)
    rb, vb, _ = ratio_cluster(*arrs_b)
    d, se = rb - ra, math.sqrt(va + vb)
    return status_from_bounds(d - Z * se, d + Z * se, margin), d - Z * se, d + Z * se


def run_all(reps: int = 2000, protocol: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    protocol = protocol or load_protocol()
    rng = np.random.default_rng(SEED)
    pl = plan(protocol)
    n = math.floor(pl["users_per_arm_planned"] * (1 - protocol["primary"]["missing_buffer"]))
    pr = protocol["primary"]
    gs = {g["id"]: g for g in protocol["guardrails"]["items"]}
    p0, mde = pr["baseline_assumption"], pr["mde_abs"]
    rows: list[dict[str, Any]] = []

    def add(check: str, hits: int, expected: str) -> None:
        rows.append({"check": check, "reps": reps, "n_per_arm": n, "rate": hits / reps,
                     "expected": expected})  # fmt: skip

    # P01: Type I error and power
    for label, delta, exp in (("P01 type I error (true diff 0)", 0.0, "~0.05"),
                              ("P01 power (true diff = MDE)", mde, ">= 0.80")):  # fmt: skip
        hits = 0
        for _ in range(reps):
            xa, xb = rng.binomial(n, p0), rng.binomial(n, p0 + delta)
            hits += two_proportions(xa, n, xb, n)["p_value"] < pr["alpha"]
        add(label, hits, exp)

    # G5 (user grain) non-inferiority
    g5 = gs["G5"]
    for label, delta, exp in (("G5 pass rate at true diff 0 (power)", 0.0, ">= 0.80"),
                              ("G5 pass rate at true diff = margin (type I)", g5["margin_abs"],
                               "<= 0.025")):  # fmt: skip
        hits = 0
        for _ in range(reps):
            xa = rng.binomial(n, g5["baseline_assumption"])
            xb = rng.binomial(n, g5["baseline_assumption"] + delta)
            r = two_proportions(xa, n, xb, n)
            hits += status_from_bounds(r["ci_low"], r["ci_high"], g5["margin_abs"]) == "pass"
        add(label, hits, exp)

    # G1 / G2 clustered by user
    for gid, maker, args in (("G1", _g1_user_arrays, (0.60, gs["G1"]["baseline_assumption"])),
                             ("G2", _g2_user_arrays, (gs["G2"]["baseline_assumption"],))):  # fmt: skip
        base = gs[gid]["baseline_assumption"]
        m = gs[gid]["margin_abs"]
        for label, delta, exp in ((f"{gid} pass rate at true diff 0 (power)", 0.0, "~0.80"),
                                  (f"{gid} pass rate at true diff = margin (type I)", m,
                                   "<= 0.025")):  # fmt: skip
            hits = 0
            for _ in range(reps):
                a = maker(rng, n, *args)
                b = maker(rng, n, *((args[0], base + delta) if gid == "G1" else (base + delta,)))
                hits += _ratio_status(a, b, m)[0] == "pass"
            add(label, hits, exp)

    # Joint Launch power at true effect = MDE with non-degraded guardrails (P01, G1, G2, G5)
    hits = 0
    for _ in range(reps):
        r = two_proportions(rng.binomial(n, p0), n, rng.binomial(n, p0 + mde), n)
        ok = r["ci_low"] > 0
        ok &= _ratio_status(_g1_user_arrays(rng, n, 0.6, gs["G1"]["baseline_assumption"]),
                            _g1_user_arrays(rng, n, 0.6 + mde, gs["G1"]["baseline_assumption"]),
                            gs["G1"]["margin_abs"])[0] == "pass"  # fmt: skip
        ok &= _ratio_status(_g2_user_arrays(rng, n, gs["G2"]["baseline_assumption"]),
                            _g2_user_arrays(rng, n, gs["G2"]["baseline_assumption"]),
                            gs["G2"]["margin_abs"])[0] == "pass"  # fmt: skip
        g5 = gs["G5"]
        r5 = two_proportions(rng.binomial(n, g5["baseline_assumption"]), n,
                             rng.binomial(n, g5["baseline_assumption"]), n)  # fmt: skip
        ok &= status_from_bounds(r5["ci_low"], r5["ci_high"], g5["margin_abs"]) == "pass"
        hits += bool(ok)
    add(f"Joint Launch power P01+G1+G2+G5 (protocol approx {pl['joint_power_approx']})", hits,
        "compare with protocol approximation")
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path = MC_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write("# data_origin=derived (Monte Carlo on synthetic assumptions); G3/G4 [TO VERIFY]\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return path
