"""Synthetic refunds and chargebacks over succeeded payments (label: synthetic, deterministic)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fintech_lab.shared.provenance import make_rng

COLUMNS = ["payment_id", "merchant_id", "method_code", "event_type", "event_date_local",
           "amount_brl", "fee_returned_brl", "chargeback_fee_brl"]


def generate_adjustments(pay: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """One refund OR one chargeback per payment at most (mutually exclusive).

    ``pay``: succeeded payments with payment_id, merchant_id, method_code, date_local,
    amount_brl, fee_brl. Draws are made on rows sorted by payment_id, so the result does not
    depend on the input order. Rates are shares of payments (≈ share of TPV in expectation).
    """
    pay = pay.sort_values("payment_id", kind="stable").reset_index(drop=True)
    rng = make_rng(int(cfg["seed"]))
    n = len(pay)
    u_ev = rng.random(n)
    u_ref = rng.random(n)
    u_cb = rng.random(n)
    rd, cd = cfg["refund"]["delay_days"], cfg["chargeback"]["delay_days"]
    ref_delay = rng.integers(rd[0], rd[1] + 1, n)
    cb_delay = rng.integers(cd[0], cd[1] + 1, n)

    p_ref = pay["method_code"].map(cfg["refund"]["rate_by_method"]).to_numpy(float)
    p_cb = pay["method_code"].map(cfg["chargeback"]["rate_by_method"]).to_numpy(float)
    if np.isnan(p_ref).any() or np.isnan(p_cb).any():
        raise ValueError("method_code without refund/chargeback rate in assumptions")
    # u_ev picks the event class so refund and chargeback never co-occur
    is_cb = u_ev < p_cb
    is_ref = (~is_cb) & (u_ev < p_cb + p_ref)
    del u_ref, u_cb  # drawn for stable stream layout; reserved for amount/partial refunds

    base = pd.to_datetime(pay["date_local"])
    out = []
    for mask, kind, delay in ((is_ref, "refund", ref_delay), (is_cb, "chargeback", cb_delay)):
        sub = pay.loc[mask]
        ev = pd.DataFrame({
            "payment_id": sub["payment_id"], "merchant_id": sub["merchant_id"],
            "method_code": sub["method_code"], "event_type": kind,
            "event_date_local": (base[mask] + pd.to_timedelta(delay[mask], unit="D")).dt.date,
            "amount_brl": sub["amount_brl"].astype(float),
        })
        if kind == "refund":
            ratio = cfg["refund"]["fee_return_ratio"]
            ev["fee_returned_brl"] = sub["fee_brl"].astype(float) * ratio
            ev["chargeback_fee_brl"] = 0.0
        else:
            ev["fee_returned_brl"] = 0.0
            ev["chargeback_fee_brl"] = float(cfg["chargeback"]["fixed_fee_brl"])
        out.append(ev)
    return pd.concat(out, ignore_index=True)[COLUMNS].sort_values(
        ["payment_id", "event_type"], kind="stable").reset_index(drop=True)
