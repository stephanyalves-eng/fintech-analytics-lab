"""Deliberately corrupted fixture for data-quality tests (P1.2.d).

Starts from a small clean synthetic dataset and injects one controlled defect per entry of
``DEFECTS``. Each defect names the contract check (``sql/checks``) expected to catch it.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd

from fintech_lab.p1_payments.generator import generate

# defect -> contract check expected to flag it
DEFECTS: dict[str, str] = {
    "duplicate_payment_id": "c01_pk_unique",
    "orphan_attempt": "c02_fk_valid",
    "payment_without_attempt": "c03_payment_has_attempt",
    "attempt_no_gap": "c04_attempt_sequence",
    "attempt_time_disorder": "c05_attempt_time_order",
    "attempt_after_approval": "c06_approved_is_last",
    "final_status_mismatch": "c07_final_status",
    "retry_after_hard": "c08_no_retry_after_hard",
    "approved_with_decline_code": "c09_result_code_coherence",
    "pix_outside_br": "c10_method_acquirer_country",
    "negative_amount": "c11_amount_valid",
    "clp_with_decimals": "c11_amount_valid",
    "settlement_for_failed": "c12_settlement_consistency",
    "settlement_currency_mismatch": "c12_settlement_consistency",
}


def make_corrupted(cfg: dict[str, Any]) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Return (corrupted tables, injection log). Deterministic for a given config."""
    fx = cfg["corrupted_fixture"]
    small = copy.deepcopy(cfg)
    small["seed"] = int(cfg["seed"]) + int(fx["seed_offset"])
    small["target_attempts"] = max(1_000, int(fx["n_payments"]) * 2)
    small["n_merchants"] = min(int(cfg["n_merchants"]), 60)
    t = {k: v.copy() for k, v in generate(small).items()}
    pay, att, sett = t["fact_payment"], t["fact_attempt"], t["fact_settlement"]
    pay = pay.iloc[: int(fx["n_payments"])].copy()
    att = att[att["payment_id"].isin(pay["payment_id"])].copy()
    sett = sett[sett["payment_id"].isin(pay["payment_id"])].copy()
    rng = np.random.default_rng(small["seed"])
    log: dict[str, list[str]] = {}

    n_att = att.groupby("payment_id")["attempt_no"].max()
    status = pay.set_index("payment_id")["final_status"]
    used: set[str] = set()

    def pick(ids: pd.Index | list[str]) -> str:
        cands = sorted(set(ids) - used)
        pid = cands[int(rng.integers(len(cands)))]
        used.add(pid)
        return pid

    two = n_att[n_att == 2].index
    succ = status[status == "succeeded"].index
    succ_single = succ.intersection(n_att[n_att == 1].index)

    pid = pick(pay["payment_id"])
    pay = pd.concat([pay, pay[pay["payment_id"] == pid]], ignore_index=True)
    log["duplicate_payment_id"] = [pid]

    row = att.iloc[[0]].copy()
    row["attempt_id"], row["payment_id"] = "A_ORPHAN_1", "P_DOES_NOT_EXIST"
    att = pd.concat([att, row], ignore_index=True)
    log["orphan_attempt"] = ["A_ORPHAN_1"]

    pid = pick(status[status == "failed"].index.intersection(n_att[n_att == 1].index))
    att = att[att["payment_id"] != pid]
    log["payment_without_attempt"] = [pid]

    pid = pick(two)
    att.loc[(att["payment_id"] == pid) & (att["attempt_no"] == 2), "attempt_no"] = 3
    log["attempt_no_gap"] = [pid]

    pid = pick(two)
    m1 = (att["payment_id"] == pid) & (att["attempt_no"] == 1)
    m2 = (att["payment_id"] == pid) & (att["attempt_no"] == 2)
    att.loc[m1, "attempted_at_utc"] = att.loc[m2, "attempted_at_utc"].iloc[0] + pd.Timedelta(
        seconds=5
    )
    log["attempt_time_disorder"] = [pid]

    pid = pick(succ_single)
    row = att[att["payment_id"] == pid].copy()
    row["attempt_id"], row["attempt_no"] = "A_AFTER_APPROVAL", 2
    row["attempted_at_utc"] += pd.Timedelta(minutes=1)
    row["result"], row["decline_code"] = "declined", "do_not_honor"
    att = pd.concat([att, row], ignore_index=True)
    log["attempt_after_approval"] = [pid]

    pid = pick(succ_single)
    pay.loc[pay["payment_id"] == pid, "final_status"] = "failed"
    sett = sett[sett["payment_id"] != pid]
    log["final_status_mismatch"] = [pid]

    pid = pick(two)
    m1 = (att["payment_id"] == pid) & (att["attempt_no"] == 1)
    att.loc[m1, ["result", "decline_code"]] = ["declined", "suspected_fraud"]
    log["retry_after_hard"] = [pid]

    pid = pick(succ_single)
    att.loc[att["payment_id"] == pid, "decline_code"] = "do_not_honor"
    log["approved_with_decline_code"] = [pid]

    mx = pay.merge(t["dim_merchant"], on="merchant_id")
    pid = pick(mx.loc[mx["country"] == "MX", "payment_id"])
    pay.loc[pay["payment_id"] == pid, "method_code"] = "pix"
    log["pix_outside_br"] = [pid]

    pid = pick(pay["payment_id"])
    pay.loc[pay["payment_id"] == pid, "amount"] = -10.0
    log["negative_amount"] = [pid]

    pid = pick(pay.loc[pay["currency"] == "CLP", "payment_id"])
    pay.loc[pay["payment_id"] == pid, "amount"] += 0.5
    log["clp_with_decimals"] = [pid]

    pid = pick(status[status == "failed"].index.intersection(att["payment_id"]))
    row = sett.iloc[[0]].copy()
    row["settlement_id"], row["payment_id"] = "S_FOR_FAILED", pid
    row["currency"] = pay.loc[pay["payment_id"] == pid, "currency"].iloc[0]
    sett = pd.concat([sett, row], ignore_index=True)
    log["settlement_for_failed"] = [pid]

    pid = pick(sett.loc[sett["currency"] == "BRL", "payment_id"])
    sett.loc[sett["payment_id"] == pid, "currency"] = "MXN"
    log["settlement_currency_mismatch"] = [pid]

    t["fact_payment"], t["fact_attempt"], t["fact_settlement"] = pay, att, sett
    extra = {
        "injected_defects": {d: {"expected_check": DEFECTS[d], "keys": log[d]} for d in DEFECTS},
        "base_config": {"seed": small["seed"], "target_attempts": small["target_attempts"]},
    }
    return t, extra
