"""Deterministic synthetic event generator for P3-EXP-001 (P3.2). All data is SYNTHETIC.

Reads ``configs/simulation.yaml`` (the data-generating truth) and the LOCKED protocol
(assignment rules only). The analysis modules never import this module or read that config.

Outputs per scenario (``data/p3/<scenario>/``):
  users.parquet    one row per candidate user (assignment, eligibility, pre-treatment segments)
  events.parquet   exposure, checkout_start, payment_attempt, payment_approved, chargeback
  manifest.json    seed, counts, hashes, protocol lock hash, environment (no true effect)
  truth.json       the true effect used (for tests / audits ONLY; analysis must not read it)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from fintech_lab.p3_experiments.assignment import assign
from fintech_lab.p3_experiments.lock import verify_lock
from fintech_lab.p3_experiments.power import P3_ROOT, REPO_ROOT, load_protocol
from fintech_lab.shared.provenance import DataOrigin, environment, make_rng

SIM_YAML = P3_ROOT / "configs" / "simulation.yaml"
DATA_ROOT = REPO_ROOT / "data" / "p3"
SCENARIOS = ("null", "positive", "negative", "srm", "missing")
EVENT_ORDER = {"exposure": 0, "checkout_start": 1, "payment_attempt": 2,
               "payment_approved": 3, "chargeback": 4}  # fmt: skip
MAX_ATTEMPTS = 3
DAY = 86_400
CONVERSION_WINDOW_S = 7 * DAY


def load_sim_config(path: Path = SIM_YAML) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ticket_band(amount: np.ndarray) -> np.ndarray:
    return np.where(amount < 100, "low", np.where(amount < 300, "mid", "high"))


def generate(
    scenario: str,
    cfg: dict[str, Any] | None = None,
    protocol: dict[str, Any] | None = None,
    candidate_users: int | None = None,
    seed: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Return (users, events, truth) for one scenario. Same inputs => identical output."""
    cfg = cfg or load_sim_config()
    protocol = protocol or load_protocol()
    if scenario not in cfg["scenarios"]:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {list(cfg['scenarios'])}")
    sc = cfg["scenarios"][scenario]
    eff, logging_cfg = sc.get("effect", {}), sc.get("logging", {})
    pop, base = cfg["population"], cfg["baseline"]
    n = int(candidate_users or pop["candidate_users"])
    rng = make_rng(int(seed if seed is not None else sc["seed"]))

    user_ids = np.array([f"U{i:07d}" for i in range(n)])
    arm = assign(user_ids, protocol)
    is_b = arm == "B"
    internal = rng.random(n) < pop["internal_share"]
    blocked = rng.random(n) < pop["prefraud_blocked_share"]
    eligible = ~internal & ~blocked
    card_credit = rng.random(n) < pop["credit_card_share"]
    returning = rng.random(n) < pop["returning_share"]
    high_risk = rng.random(n) < pop["high_risk_share"]  # latent: never exported
    low = ~high_risk
    amount = np.round(base["ticket_median_brl"] * np.exp(base["ticket_sigma"] * rng.normal(size=n)), 2)  # fmt: skip

    users = pd.DataFrame({
        "user_id": user_ids, "assigned_arm": arm, "is_internal": internal,
        "prefraud_blocked": blocked, "eligible": eligible,
        "card_type": np.where(card_credit, "credit_card", "debit_card"),
        "user_type": np.where(returning, "returning", "new"),
        "ticket_band": _ticket_band(amount),
    })  # fmt: skip

    # ---- exposure time: weekly seasonality, first eligible checkout_start of the window
    days = np.arange(pop["enrollment_days"])
    start = np.datetime64(pop["start_date"], "s")
    dow = (days + (start.astype("datetime64[D]").astype(int) + 3)) % 7  # 1970-01-01 = Thursday
    w = np.where(dow >= 5, pop["weekend_weight"], 1.0)
    day_idx = rng.choice(days, size=n, p=w / w.sum())
    t0 = day_idx * DAY + rng.integers(0, DAY, size=n)  # seconds from start

    # ---- per-user parameters (true effect applies to B only)
    treated_low = is_b & low
    p_attempt = np.clip(base["p_attempt"] + treated_low * eff.get("p_attempt_delta_low_risk", 0.0), 0, 1)  # fmt: skip
    p_ok = np.clip(base["p_approve_given_ok"] + treated_low * eff.get("p_approve_delta_low_risk", 0.0), 0, 1)  # fmt: skip
    p_err = np.clip(base["p_technical_error"] + is_b * eff.get("p_technical_error_delta", 0.0), 0, 1)  # fmt: skip
    lat_med = base["latency_median_ms"] * np.where(treated_low, eff.get("latency_median_ratio_low_risk", 1.0), 1.0)  # fmt: skip
    fee = base["cost_3ds_fee_brl"] * np.where(treated_low, eff.get("cost_3ds_fee_ratio_low_risk", 1.0), 1.0)  # fmt: skip
    p_cb = np.clip(base["chargeback_rate"] * np.where(is_b, eff.get("chargeback_ratio", 1.0), 1.0), 0, 1)  # fmt: skip

    # ---- attempts (max 3): retry only after a failed attempt
    active = eligible & (rng.random(n) < p_attempt)
    prev_ts = t0.copy()
    rows: list[pd.DataFrame] = []
    limit = t0 + CONVERSION_WINDOW_S - 120
    for k in range(1, MAX_ATTEMPTS + 1):
        idx = np.flatnonzero(active)
        if idx.size == 0:
            break
        gap = rng.exponential(300 if k == 1 else 6 * 3600, size=idx.size)
        ts = np.minimum(prev_ts[idx] + (1 if k == 1 else 60) + gap.astype(np.int64), limit[idx])
        tech = rng.random(idx.size) < p_err[idx]
        ok = ~tech & (rng.random(idx.size) < p_ok[idx])
        lat = np.round(lat_med[idx] * np.exp(base["latency_sigma"] * rng.normal(size=idx.size)))
        cost = np.round(amount[idx] * base["cost_processing_pct"] + fee[idx], 4)
        cb = ok & (rng.random(idx.size) < p_cb[idx])
        cb_delay = (rng.uniform(5, 30, size=idx.size) * DAY).astype(np.int64)
        rows.append(pd.DataFrame({
            "u": idx, "k": k, "ts": ts, "tech": tech, "ok": ok, "lat": lat, "cost": cost,
            "cb": cb, "cb_delay": cb_delay,
        }))  # fmt: skip
        prev_ts[idx] = ts
        nxt = np.zeros(n, dtype=bool)
        nxt[idx] = ~ok & (rng.random(idx.size) < base["p_retry"])
        active = nxt
    att = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["u", "k"])

    # ---- logging failures (the truth is generated first, then the log is damaged)
    keep_user = eligible.copy()
    if "drop_exposure_share_B" in logging_cfg:
        lost = is_b & (rng.random(n) < logging_cfg["drop_exposure_share_B"])
        keep_user &= ~lost
    if len(att):
        p_drop = np.where(is_b[att["u"]], logging_cfg.get("drop_attempt_share_B", 0.0),
                          logging_cfg.get("drop_attempt_share_A", 0.0))  # fmt: skip
        att["logged"] = rng.random(len(att)) >= p_drop
    ev: list[pd.DataFrame] = []
    uidx = np.flatnonzero(keep_user)
    for etype in ("exposure", "checkout_start"):
        ev.append(pd.DataFrame({"user_id": user_ids[uidx], "event_type": etype, "ts": t0[uidx]}))
    if len(att):
        att = att[keep_user[att["u"]]]
        u = att["u"].to_numpy()
        outcome = np.where(att["tech"], "technical_error", np.where(att["ok"], "approved", "declined"))  # fmt: skip
        aid = np.char.add(np.char.add(user_ids[u], "-"), att["k"].to_numpy().astype(str))
        base_cols = {"user_id": user_ids[u], "attempt_id": aid, "attempt_no": att["k"].to_numpy(),
                     "amount_brl": amount[u]}  # fmt: skip
        logged = att["logged"].to_numpy()
        ev.append(pd.DataFrame({**base_cols, "event_type": "payment_attempt", "ts": att["ts"].to_numpy(),
                                "outcome": outcome, "latency_ms": att["lat"].to_numpy(),
                                "cost_brl": att["cost"].to_numpy()})[logged])  # fmt: skip
        okm = att["ok"].to_numpy()
        appr_ts = att["ts"].to_numpy() + np.ceil(att["lat"].to_numpy() / 1000).astype(np.int64)
        ev.append(pd.DataFrame({**base_cols, "event_type": "payment_approved", "ts": appr_ts})[okm])
        cbm = att["cb"].to_numpy()
        ev.append(pd.DataFrame({**base_cols, "event_type": "chargeback",
                                "ts": appr_ts + att["cb_delay"].to_numpy()})[cbm])  # fmt: skip
    events = pd.concat(ev, ignore_index=True)
    events["attempt_no"] = events["attempt_no"].astype("Int64")
    events["ts"] = start + events["ts"].astype("int64").to_numpy().astype("timedelta64[s]")
    events["_o"] = events["event_type"].map(EVENT_ORDER)
    events = events.sort_values(["user_id", "ts", "_o", "attempt_no"], kind="mergesort")
    events = events.drop(columns="_o").reset_index(drop=True)
    events.insert(0, "event_id", np.arange(1, len(events) + 1))
    events = events[["event_id", "user_id", "event_type", "ts", "attempt_id", "attempt_no",
                     "outcome", "amount_brl", "latency_ms", "cost_brl"]]  # fmt: skip

    truth = {"scenario": scenario, "data_origin": DataOrigin.SYNTHETIC.value,
             "effect": eff, "logging": logging_cfg, "seed": int(seed if seed is not None else sc["seed"])}  # fmt: skip
    return users, events, truth


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_scenario(scenario: str, out_root: Path = DATA_ROOT, **kw: Any) -> Path:
    """Generate and persist one scenario; requires an intact protocol lock."""
    lock = verify_lock()
    users, events, truth = generate(scenario, **kw)
    out = Path(out_root) / scenario
    out.mkdir(parents=True, exist_ok=True)
    users.to_parquet(out / "users.parquet", index=False)
    events.to_parquet(out / "events.parquet", index=False)
    (out / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    protocol = load_protocol()
    cfg = load_sim_config()
    w = protocol["windows_days"]
    observation_end = np.datetime64(cfg["population"]["start_date"], "s") + np.timedelta64(
        cfg["population"]["enrollment_days"] + w["conversion"] + w["chargeback_maturation"], "D")
    manifest = {
        "observation_end": str(observation_end),
        "data_origin": DataOrigin.SYNTHETIC.value,
        "scenario": scenario,
        "experiment_id": protocol["experiment"]["id"],
        "protocol_version": protocol["experiment"]["protocol_version"],
        "protocol_lock_files": lock["files"],
        "seed": truth["seed"],
        "counts": {"candidate_users": len(users), "eligible_users": int(users["eligible"].sum()),
                   "events": len(events)},  # fmt: skip
        "sha256": {f: _sha256(out / f) for f in ("users.parquet", "events.parquet")},
        "environment": environment(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return out
