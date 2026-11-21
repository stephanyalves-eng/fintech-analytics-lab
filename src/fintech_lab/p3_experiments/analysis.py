"""Auditable frequentist analysis engine for P3-EXP-001 (P3.3).

Reads ONLY the event data (users/events/manifest) and the LOCKED protocol. It must never import
the simulator or read ``simulation.yaml`` / ``truth.json`` (enforced by tests/p3/test_separation).

Order: verify_lock -> validity gates -> primary (P01) -> guardrails (G1-G5) -> sensitivity.
Methods (all justified in docs/methods.md):
  P01  two-proportion z; p-value with pooled SE, 95% CI of the difference with unpooled (Wald) SE;
       relative uplift CI by the delta method on log(pB/pA).
  G1/G2/G4  ratio estimators clustered by user (delta method) -> repeated payments/attempts of one
       user do not look independent. G3 p95 latency: user-cluster bootstrap. G5: user grain.
Non-significance is never reported as "no effect".
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chisquare, norm

from fintech_lab.p3_experiments.assignment import assign
from fintech_lab.p3_experiments.lock import verify_lock
from fintech_lab.p3_experiments.power import load_protocol, mde_two_proportions

DAY = 86_400
Z = float(norm.ppf(0.975))  # same z for the two-sided 95% CI and the one-sided 97.5% bound


# ------------------------------------------------------------------ pure estimators
def two_proportions(x_a: int, n_a: int, x_b: int, n_b: int) -> dict[str, float]:
    """Difference p_B - p_A: pooled-SE z test, Wald 95% CI, delta-method relative CI."""
    pa, pb = x_a / n_a, x_b / n_b
    d = pb - pa
    se_u = math.sqrt(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b)
    pool = (x_a + x_b) / (n_a + n_b)
    se_p = math.sqrt(pool * (1 - pool) * (1 / n_a + 1 / n_b))
    z = d / se_p if se_p > 0 else 0.0
    out = {"p_a": pa, "p_b": pb, "diff": d, "se": se_u, "ci_low": d - Z * se_u,
           "ci_high": d + Z * se_u, "z": z, "p_value": float(2 * norm.sf(abs(z)))}  # fmt: skip
    if pa > 0 and pb > 0:
        se_log = math.sqrt((1 - pa) / (n_a * pa) + (1 - pb) / (n_b * pb))
        r = math.log(pb / pa)
        out |= {"rel": pb / pa - 1, "rel_ci_low": math.exp(r - Z * se_log) - 1,
                "rel_ci_high": math.exp(r + Z * se_log) - 1}  # fmt: skip
    else:
        out |= {"rel": float("nan"), "rel_ci_low": float("nan"), "rel_ci_high": float("nan")}
    return out


def ratio_cluster(num: np.ndarray, den: np.ndarray) -> tuple[float, float, float]:
    """Ratio of sums with cluster(user)-robust variance (delta method).

    Returns (R, var(R), design_effect) where the design effect compares the cluster variance with
    the one that would hold if every denominator unit were independent (binary numerators only).
    """
    n = len(num)
    sd = float(den.sum())
    if n < 2 or sd <= 0:
        return float("nan"), float("nan"), float("nan")
    r = float(num.sum() / sd)
    resid = num - r * den
    var = n / (n - 1) * float(np.sum(resid**2)) / sd**2
    srs = r * (1 - r) / sd if 0 < r < 1 else float("nan")
    return r, var, var / srs if srs == srs and srs > 0 else float("nan")


def status_from_bounds(lower_two_sided: float, upper_one_sided: float, margin: float) -> str:
    """Protocol: pass if the one-sided 97.5% upper bound <= margin; fail if the two-sided 95%
    lower bound > margin; undetermined otherwise (higher d = worse)."""
    if upper_one_sided <= margin:
        return "pass"
    if lower_two_sided > margin:
        return "fail"
    return "undetermined"


def _weighted_quantile_sorted(lat_sorted: np.ndarray, w: np.ndarray, q: float) -> float:
    cw = np.cumsum(w)
    return float(lat_sorted[np.searchsorted(cw, q * cw[-1])])


def bootstrap_p95_diff(
    lat_a: np.ndarray, pos_a: np.ndarray, n_a: int,
    lat_b: np.ndarray, pos_b: np.ndarray, n_b: int,
    reps: int, seed: int, q: float = 0.95,
) -> dict[str, float]:  # fmt: skip
    """User-cluster bootstrap of p95_B - p95_A (resample users, keep all their attempts)."""
    rng = np.random.default_rng(seed)
    prepared = []
    for lat, pos, n in ((lat_a, pos_a, n_a), (lat_b, pos_b, n_b)):
        order = np.argsort(lat, kind="stable")
        prepared.append((lat[order], pos[order], n))
    est = [
        _weighted_quantile_sorted(lat_s, np.ones(len(lat_s)), q) for lat_s, _, _ in prepared
    ]
    diffs = np.empty(reps)
    for i in range(reps):
        qs = []
        for lat_s, pos_s, n in prepared:
            counts = np.bincount(rng.integers(0, n, n), minlength=n)
            qs.append(_weighted_quantile_sorted(lat_s, counts[pos_s], q))
        diffs[i] = qs[1] - qs[0]
    return {"p95_a": est[0], "p95_b": est[1], "diff": est[1] - est[0],
            "ci_low": float(np.quantile(diffs, 0.025)),
            "ci_high": float(np.quantile(diffs, 0.975))}  # fmt: skip


# ------------------------------------------------------------------ data loading
def load_dataset(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("data_origin") != "synthetic":
        raise ValueError("dataset is not labelled synthetic")
    return (pd.read_parquet(data_dir / "users.parquet"),
            pd.read_parquet(data_dir / "events.parquet"), manifest)  # fmt: skip


def build_frames(
    users: pd.DataFrame, events: pd.DataFrame, protocol: dict[str, Any]
) -> dict[str, Any]:
    """User-grain frame of exposed users + attempt-grain frame (conversion window applied)."""
    win = protocol["windows_days"]["conversion"] * DAY
    cbwin = protocol["windows_days"]["chargeback_maturation"] * DAY
    expo = events[events.event_type == "exposure"].groupby("user_id")["ts"].min().rename("t_exp")
    u = users[users.eligible].merge(expo, on="user_id", how="inner").reset_index(drop=True)
    t = u.set_index("user_id")["t_exp"]

    ev = events[events.user_id.isin(t.index)].copy()
    ev["rel_s"] = (ev["ts"] - ev["user_id"].map(t)).dt.total_seconds()
    before = int((ev["rel_s"] < 0).sum())
    inwin = ev[(ev["rel_s"] <= win)]
    att = inwin[inwin.event_type == "payment_attempt"]
    appr = inwin[inwin.event_type == "payment_approved"]
    cb = ev[ev.event_type == "chargeback"]
    appr_ts = appr.set_index("attempt_id")["ts"]
    cb = cb[cb["attempt_id"].isin(appr_ts.index)]
    cb = cb[(cb["ts"] - cb["attempt_id"].map(appr_ts)).dt.total_seconds() <= cbwin]

    g = lambda s: s.reindex(u.user_id).fillna(0).to_numpy()  # noqa: E731
    u["n_attempts"] = g(att.groupby("user_id").size())
    u["n_tech"] = g(att[att.outcome == "technical_error"].groupby("user_id").size())
    u["n_approved"] = g(appr.groupby("user_id").size())
    u["n_chargeback"] = g(cb.groupby("user_id").size())
    u["cost_brl"] = g(att.groupby("user_id")["cost_brl"].sum())
    u["approved_amount"] = g(appr.groupby("user_id")["amount_brl"].sum())
    u["chargeback_amount"] = g(cb.groupby("user_id")["amount_brl"].sum())
    u["converted"] = u["n_approved"] > 0
    u["attempted"] = u["n_attempts"] > 0

    # incomplete trail: approval without its attempt event, or a gap in the attempt numbering
    known = set(att["attempt_id"])
    orphan = appr[~appr["attempt_id"].isin(known)].groupby("user_id").size()
    mx = att.groupby("user_id")["attempt_no"].max()
    gap = (mx != att.groupby("user_id").size().reindex(mx.index)).reindex(u.user_id).fillna(False)
    u["incomplete"] = (u["user_id"].isin(orphan.index) | gap.to_numpy().astype(bool))
    att = att.merge(u[["user_id", "assigned_arm"]], on="user_id")
    return {"users": u, "attempts": att, "events_before_exposure": before}


# ------------------------------------------------------------------ validity gates
def validity_gates(
    all_users: pd.DataFrame, frames: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, Any]:
    g = protocol["validity_gates"]
    u = frames["users"]
    n_a, n_b = int((u.assigned_arm == "A").sum()), int((u.assigned_arm == "B").sum())
    exp = [(n_a + n_b) * protocol["assignment"]["allocation"][k] for k in ("A", "B")]
    srm_p = float(chisquare([n_a, n_b], exp).pvalue)
    dup = int(all_users["user_id"].duplicated().sum())
    expected_arm = assign(all_users["user_id"].to_numpy(), protocol)
    mismatch = int((expected_arm != all_users["assigned_arm"].to_numpy()).sum())
    miss = u.groupby("assigned_arm")["incomplete"].mean().reindex(["A", "B"]).fillna(0)
    gates = {
        "srm": {"n_a": n_a, "n_b": n_b, "p_value": srm_p, "threshold": g["srm"]["p_threshold"],
                "pass": srm_p >= g["srm"]["p_threshold"]},
        "assignment_integrity": {"duplicate_users": dup, "arm_mismatch_vs_hash": mismatch,
                                 "pass": dup == 0 and mismatch == 0},
        "events_before_exposure": {"count": frames["events_before_exposure"],
                                   "pass": frames["events_before_exposure"] == 0},
        "missing_events": {"share_a": float(miss["A"]), "share_b": float(miss["B"]),
                           "diff": float(miss["B"] - miss["A"]),
                           "pass": bool(max(miss) <= g["max_missing_share_per_arm"]
                                        and abs(miss["B"] - miss["A"])
                                        <= g["max_missing_share_diff"])},
    }  # fmt: skip
    gates["all_pass"] = all(v["pass"] for v in gates.values())
    return gates


# ------------------------------------------------------------------ guardrails
def _arm_split(u: pd.DataFrame, col: str) -> tuple[np.ndarray, np.ndarray]:
    return (u.loc[u.assigned_arm == "A", col].to_numpy(float),
            u.loc[u.assigned_arm == "B", col].to_numpy(float))  # fmt: skip


def _mean_valid(*v: float) -> float:
    ok = [x for x in v if x == x]
    return float(sum(ok) / len(ok)) if ok else float("nan")


def _ratio_guardrail(g: dict, u: pd.DataFrame, num: str, den: str, relative: bool) -> dict:
    na, nb = _arm_split(u, num)
    da, db = _arm_split(u, den)
    ra, va, deff_a = ratio_cluster(na, da)
    rb, vb, deff_b = ratio_cluster(nb, db)
    if relative:  # d = R_B / R_A - 1 through log(R_B / R_A)
        r = math.log(rb / ra)
        se = math.sqrt(vb / rb**2 + va / ra**2)
        d, lo, hi = math.exp(r) - 1, math.exp(r - Z * se) - 1, math.exp(r + Z * se) - 1
        margin = g["margin_rel"]
    else:
        d, se = rb - ra, math.sqrt(va + vb)
        lo, hi, margin = d - Z * se, d + Z * se, g["margin_abs"]
    return {"est_a": ra, "est_b": rb, "diff": d, "ci_low": lo, "ci_high": hi, "margin": margin,
            "relative": relative, "design_effect": _mean_valid(deff_a, deff_b),
            "units_a": float(da.sum()), "units_b": float(db.sum())}  # fmt: skip


def guardrails(frames: dict[str, Any], protocol: dict[str, Any]) -> list[dict]:
    u, att = frames["users"], frames["attempts"]
    spec = {x["id"]: x for x in protocol["guardrails"]["items"]}
    out: list[dict] = []
    # G1: chargebacks per approved payment
    out.append({"id": "G1", "name": spec["G1"]["name"],
                **_ratio_guardrail(spec["G1"], u, "n_chargeback", "n_approved", False)})  # fmt: skip
    # G2: technical errors / attempts
    out.append({"id": "G2", "name": spec["G2"]["name"],
                **_ratio_guardrail(spec["G2"], u, "n_tech", "n_attempts", False)})  # fmt: skip
    # G3: p95 latency (user-cluster bootstrap)
    g3 = spec["G3"]
    arms = {}
    for arm in ("A", "B"):
        users_arm = u.loc[u.assigned_arm == arm, "user_id"].reset_index(drop=True)
        pos = pd.Series(np.arange(len(users_arm)), index=users_arm)
        a = att[att.assigned_arm == arm]
        arms[arm] = (a["latency_ms"].to_numpy(float), a["user_id"].map(pos).to_numpy(int),
                     len(users_arm))  # fmt: skip
    bs = bootstrap_p95_diff(*arms["A"], *arms["B"], reps=2000, seed=20260321)
    out.append({"id": "G3", "name": g3["name"], "est_a": bs["p95_a"], "est_b": bs["p95_b"],
                "diff": bs["diff"], "ci_low": bs["ci_low"], "ci_high": bs["ci_high"],
                "margin": g3["margin_abs"], "relative": False, "design_effect": float("nan"),
                "units_a": float(len(arms["A"][0])), "units_b": float(len(arms["B"][0]))})  # fmt: skip
    # G4: cost / approved payment (relative margin)
    out.append({"id": "G4", "name": spec["G4"]["name"],
                **_ratio_guardrail(spec["G4"], u, "cost_brl", "n_approved", True)})  # fmt: skip
    # G5: abandonment (user grain, two proportions)
    g5 = spec["G5"]
    ab = ~u["attempted"]
    ta = two_proportions(int(ab[u.assigned_arm == "A"].sum()), int((u.assigned_arm == "A").sum()),
                         int(ab[u.assigned_arm == "B"].sum()), int((u.assigned_arm == "B").sum()))  # fmt: skip
    out.append({"id": "G5", "name": g5["name"], "est_a": ta["p_a"], "est_b": ta["p_b"],
                "diff": ta["diff"], "ci_low": ta["ci_low"], "ci_high": ta["ci_high"],
                "margin": g5["margin_abs"], "relative": False, "design_effect": 1.0,
                "units_a": float((u.assigned_arm == "A").sum()),
                "units_b": float((u.assigned_arm == "B").sum())})  # fmt: skip
    for r in out:
        r["status"] = status_from_bounds(r["ci_low"], r["ci_high"], r["margin"])
    return out


# ------------------------------------------------------------------ primary + sensitivity
def primary(u: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]:
    pr = protocol["primary"]
    a, b = u[u.assigned_arm == "A"], u[u.assigned_arm == "B"]
    res = two_proportions(int(a.converted.sum()), len(a), int(b.converted.sum()), len(b))
    res |= {"id": pr["id"], "name": pr["name"], "n_a": len(a), "n_b": len(b),
            "x_a": int(a.converted.sum()), "x_b": int(b.converted.sum()), "alpha": pr["alpha"],
            "mde_abs_at_observed_n": mde_two_proportions(
                res["p_a"], min(len(a), len(b)), pr["alpha"], pr["power"])}  # fmt: skip
    return res


def sensitivity(u: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]:
    """Non-decisional checks: exclude incomplete trails; user-level HC1 robust SE (ols)."""
    comp = u[~u["incomplete"]]
    excl = primary(comp, protocol)
    x = sm.add_constant((u.assigned_arm == "B").astype(float).to_numpy())
    fit = sm.OLS(u["converted"].astype(float).to_numpy(), x).fit(cov_type="HC1")
    lo, hi = fit.conf_int()[1]
    return {
        "exclude_incomplete_trails": {k: excl[k] for k in ("diff", "ci_low", "ci_high", "p_value",
                                                           "n_a", "n_b")},  # fmt: skip
        "robust_hc1": {"diff": float(fit.params[1]), "ci_low": float(lo), "ci_high": float(hi),
                       "p_value": float(fit.pvalues[1])},  # fmt: skip
        "incomplete_users": int(u["incomplete"].sum()),
    }


# ------------------------------------------------------------------ orchestration
def analyze(data_dir: Path, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full pre-registered analysis of one dataset. Raises if the protocol lock is broken."""
    lock = verify_lock()
    protocol = protocol or load_protocol()
    users, events, manifest = load_dataset(data_dir)
    frames = build_frames(users, events, protocol)
    u = frames["users"]
    gates = validity_gates(users, frames, protocol)
    return {
        "meta": {"scenario": manifest["scenario"], "seed": manifest["seed"],
                 "data_origin": manifest["data_origin"],
                 "experiment_id": protocol["experiment"]["id"],
                 "protocol_version": protocol["experiment"]["protocol_version"],
                 "lock_algorithm": lock["algorithm"], "locked_at": lock["locked_at"],
                 "amendments": len(lock["amendments"]),
                 "window_days": {"conversion": protocol["windows_days"]["conversion"],
                                 "chargeback": protocol["windows_days"]["chargeback_maturation"]},
                 "events": int(len(events))},  # fmt: skip
        "counts": {"candidates": int(len(users)), "eligible": int(users.eligible.sum()),
                   "exposed_a": int((u.assigned_arm == "A").sum()),
                   "exposed_b": int((u.assigned_arm == "B").sum()),
                   "attempted": int(u.attempted.sum()), "converted": int(u.converted.sum())},  # fmt: skip
        "funnel": {arm: {"exposed": int(len(s)), "attempted": int(s.attempted.sum()),
                         "approved": int(s.converted.sum())}
                   for arm, s in u.groupby("assigned_arm")},  # fmt: skip
        "gates": gates,
        "primary": primary(u, protocol),
        "guardrails": guardrails(frames, protocol),
        "sensitivity": sensitivity(u, protocol),
        "multiplicity_policy": "single primary; guardrails by intersection-union (all must pass); "
        "segments exploratory and excluded from the decision",
        "_frames": frames,
    }
