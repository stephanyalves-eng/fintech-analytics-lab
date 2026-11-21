"""P1.4 scenario simulator (S1 rerouting, S2 retry cap) — hypothetical, NOT causal.

Every output is a *simulated estimate under explicit assumptions* computed from the synthetic
dataset (data_origin = derived). Fee/take-rate inputs come from the synthetic MDR and are
``[TO VERIFY]``: they are not real revenue. See ``docs/diagnostic_memo.md`` for limitations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

S1_KEYS = ["country", "first_acquirer_id", "method_code", "amount_band_brl"]
THETAS = (0.0, 0.25, 0.5, 0.75, 1.0)
DELTAS = (0.5, 0.75, 1.0)
MULTS = (0.8, 1.0, 1.2)
Z95 = 1.959963984540054


def wilson(successes: float, n: float, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a proportion; (nan, nan) when n == 0."""
    if n <= 0:
        return (math.nan, math.nan)
    p = successes / n
    den = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return (centre - half, centre + half)


@dataclass(frozen=True)
class S1Assumptions:
    """S1: retries of soft-declined card payments that stayed on the first acquirer are
    rerouted to the alternative acquirer of the same country.

    theta: weight with which rerouted payments take on the observed switched-arm success rate
        and per-payment cost (1 = observed gap transfers fully; 0 = no effect).
    take_mult / cost_mult: multipliers on the synthetic take rate and on the cost gap.
    min_n: minimum payments per arm in a stratum; smaller strata are excluded (coverage reported).
    """

    theta: float = 1.0
    take_mult: float = 1.0
    cost_mult: float = 1.0
    min_n: int = 30


def s1_strata(base: pd.DataFrame, min_n: int = 30) -> pd.DataFrame:
    """Pivot the ``s1_reroute_base`` rows into one row per stratum with both arms."""
    num = ["payments", "succeeded", "tpv_brl", "processing_cost_brl", "fee_brl"]
    b = base.copy()
    b[num] = b[num].astype(float)
    same = b[~b["switched"].astype(bool)].set_index(S1_KEYS)[num].add_suffix("_0")
    sw = b[b["switched"].astype(bool)].set_index(S1_KEYS)[num].add_suffix("_1")
    s = same.join(sw, how="outer").fillna(0.0).reset_index()
    s["eligible"] = (s["payments_0"] >= min_n) & (s["payments_1"] >= min_n)
    n0 = s["payments_0"].where(s["payments_0"] > 0)
    n1 = s["payments_1"].where(s["payments_1"] > 0)
    s["p0"] = s["succeeded_0"] / n0
    s["p1"] = s["succeeded_1"] / n1
    s["gap"] = s["p1"] - s["p0"]
    s["var_gap"] = s["p1"] * (1 - s["p1"]) / n1 + s["p0"] * (1 - s["p0"]) / n0
    succ = s["succeeded_0"] + s["succeeded_1"]
    tpv = s["tpv_brl_0"] + s["tpv_brl_1"]
    s["ticket_brl"] = tpv / succ.where(succ > 0)
    s["take_rate"] = (s["fee_brl_0"] + s["fee_brl_1"]) / tpv.where(tpv > 0)
    s["cost_gap_per_payment"] = s["processing_cost_brl_1"] / n1 - s["processing_cost_brl_0"] / n0
    return s


def simulate_s1(
    base: pd.DataFrame, country_payments: pd.Series, a: S1Assumptions = S1Assumptions()
) -> pd.DataFrame:
    """S1 result per reroute direction (first acquirer -> alternative acquirer).

    ``country_payments``: payments per country (all methods) for the M02 change denominator.
    """
    s = s1_strata(base, a.min_n)
    e = s[s["eligible"]].copy()
    e["d_succ"] = e["payments_0"] * e["gap"] * a.theta
    e["d_succ_var"] = (e["payments_0"] ** 2) * e["var_gap"] * a.theta**2
    e["d_tpv"] = e["d_succ"] * e["ticket_brl"]
    e["d_fee"] = e["d_tpv"] * e["take_rate"] * a.take_mult
    # Mixture reading: rerouted payments behave like the observed switched arm with weight
    # theta (success AND per-payment cost); theta = 0 is the null "rerouting changes nothing".
    e["d_cost"] = e["payments_0"] * e["cost_gap_per_payment"] * a.theta * a.cost_mult
    g = e.groupby(["country", "first_acquirer_id"], as_index=False).agg(
        rerouted_payments=("payments_0", "sum"),
        d_succeeded=("d_succ", "sum"),
        d_succ_var=("d_succ_var", "sum"),
        d_tpv_brl=("d_tpv", "sum"),
        d_fee_brl=("d_fee", "sum"),
        d_cost_brl=("d_cost", "sum"),
    )
    cov = s.groupby(["country", "first_acquirer_id"])["payments_0"].sum().rename("pop")
    g = g.join(cov, on=["country", "first_acquirer_id"])
    g["coverage"] = g["rerouted_payments"] / g["pop"]
    se = np.sqrt(g["d_succ_var"])
    g["d_succeeded_lo95"] = g["d_succeeded"] - Z95 * se
    g["d_succeeded_hi95"] = g["d_succeeded"] + Z95 * se
    g["d_m02_pp"] = 100 * g["d_succeeded"] / g["country"].map(country_payments).astype(float)
    g["d_net_contribution_brl"] = g["d_fee_brl"] - g["d_cost_brl"]
    g["theta"] = a.theta
    g["take_mult"] = a.take_mult
    cols = [
        "country",
        "first_acquirer_id",
        "theta",
        "take_mult",
        "rerouted_payments",
        "coverage",
        "d_succeeded",
        "d_succeeded_lo95",
        "d_succeeded_hi95",
        "d_m02_pp",
        "d_tpv_brl",
        "d_fee_brl",
        "d_cost_brl",
        "d_net_contribution_brl",
    ]
    return g[cols]


def s1_sensitivity(base: pd.DataFrame, country_payments: pd.Series) -> pd.DataFrame:
    rows = [
        simulate_s1(base, country_payments, S1Assumptions(theta=t, take_mult=m))
        for t in THETAS
        for m in MULTS
    ]
    return pd.concat(rows, ignore_index=True)


@dataclass(frozen=True)
class S2Assumptions:
    """S2: max attempts per payment = ``cap`` (observed policy = 3).

    cap = 2: drops attempt 3 (inside data support; assumes attempts 1-2 unchanged).
    cap = 4: EXTRAPOLATION. A 4th attempt happens with the observed 2->3 retry propensity and
        approves with the observed attempt-3 M01 times ``delta`` (decay; <1 = more pessimistic).
    """

    cap: int = 3
    delta: float = 1.0
    take_mult: float = 1.0
    cost_mult: float = 1.0


def simulate_s2(base: pd.DataFrame, a: S2Assumptions = S2Assumptions()) -> pd.DataFrame:
    """S2 result per country plus a TOTAL row (BRL, payment grain)."""
    if a.cap not in (2, 3, 4):
        raise ValueError("cap must be 2, 3 or 4")
    b = base.copy()
    num = [c for c in b.columns if c != "country"]
    b[num] = b[num].astype(float)
    take = b["fee_brl"] / b["tpv_brl"]
    succ, fee, cost = b["succeeded"], b["fee_brl"], b["processing_cost_brl"]
    fee = fee * a.take_mult
    d_succ = d_tpv = d_fee = d_cost = pd.Series(0.0, index=b.index)
    if a.cap == 2:
        d_succ, d_tpv = -b["succ_at_3"], -b["tpv_at_3_brl"]
        d_fee = -b["fee_at_3_brl"] * a.take_mult
        d_cost = -b["cost_3_brl"] * a.cost_mult
    elif a.cap == 4:
        retry_p = b["retried_after_2"] / b["retryable_fail_2"]
        p4 = (b["approved_3"] / b["attempts_3"] * a.delta).clip(0, 1)
        n4 = b["retryable_fail_3"] * retry_p
        d_succ = n4 * p4
        d_tpv = d_succ * b["avg_ticket_eligible_brl"]
        d_fee = d_tpv * take * a.take_mult
        d_cost = (
            n4
            * (
                p4 * b["approved_cost_rate"] * b["avg_ticket_eligible_brl"]
                + (1 - p4) * b["fixed_cost_per_attempt_brl"]
            )
            * a.cost_mult
        )
    out = pd.DataFrame(
        {
            "country": b["country"],
            "payments": b["payments"],
            "succeeded_base": succ,
            "d_succeeded": d_succ,
            "d_tpv_brl": d_tpv,
            "d_fee_brl": d_fee,
            "d_cost_brl": d_cost,
            "net_base_brl": fee - cost * a.cost_mult,
        }
    )
    tot = out.drop(columns="country").sum().to_frame().T.assign(country="TOTAL")
    out = pd.concat([out, tot], ignore_index=True)
    out["m02_base"] = out["succeeded_base"] / out["payments"]
    out["m02_scenario"] = (out["succeeded_base"] + out["d_succeeded"]) / out["payments"]
    out["d_m02_pp"] = 100 * (out["m02_scenario"] - out["m02_base"])
    out["d_net_contribution_brl"] = out["d_fee_brl"] - out["d_cost_brl"]
    out.insert(1, "cap", a.cap)
    out.insert(2, "delta", a.delta if a.cap == 4 else math.nan)
    out.insert(3, "take_mult", a.take_mult)
    out.insert(4, "support", "extrapolated" if a.cap == 4 else "in-support")
    return out


def s2_grid(base: pd.DataFrame) -> pd.DataFrame:
    runs = [S2Assumptions(cap=2, take_mult=m) for m in MULTS]
    runs += [S2Assumptions(cap=3, take_mult=m) for m in MULTS]
    runs += [S2Assumptions(cap=4, delta=d, take_mult=m) for d in DELTAS for m in MULTS]
    return pd.concat([simulate_s2(base, a) for a in runs], ignore_index=True)
