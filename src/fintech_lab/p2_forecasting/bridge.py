"""Variance bridges that close exactly: fee volume/mix/rate (+ interaction), cost lines, LMDI.

Fee = T * sum_c s_c r_c  (T total TPV, s country share, r country take rate). With deltas against a
reference ("from") state b and a compared ("to") state a:

  volume      = dT * rbar_b                       (rbar_b = F_b / T_b)
  mix         = T_b * sum(ds * r_b)               (share shift at reference rates)
  rate        = T_b * sum(s_b * dr)               (take-rate change at reference shares)
  interaction = dT*sum(ds*r_b) + dT*sum(s_b*dr) + T_b*sum(ds*dr) + dT*sum(ds*dr)

volume + mix + rate + interaction == F_a - F_b identically (algebra, no residual); the code asserts
it numerically. Cost lines split into a volume part (dT at the reference cost-per-TPV) and a
rate/mix part (the rest); every cost effect is signed as impact on contribution.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

COST_LINES = {"rc": "Refund + chargeback", "inc": "Incentives", "proc": "Processing cost",
              "var": "Other variable cost"}


def fee_bridge(b: pd.DataFrame, a: pd.DataFrame) -> dict[str, float]:
    """Decompose Fee_a - Fee_b by country mix. ``b``/``a`` are P&L frames indexed by country."""
    tb, ta = float(b["tpv"].sum()), float(a["tpv"].sum())
    sb, sa = b["tpv"] / tb, a["tpv"] / ta
    rb, ra = b["fee"] / b["tpv"], a["fee"] / a["tpv"]
    dt, ds, dr = ta - tb, sa - sb, ra - rb
    rbar = float(b["fee"].sum()) / tb
    parts = {
        "volume": dt * rbar,
        "mix": tb * float((ds * rb).sum()),
        "rate": tb * float((sb * dr).sum()),
        "interaction": dt * float((ds * rb).sum()) + dt * float((sb * dr).sum())
        + tb * float((ds * dr).sum()) + dt * float((ds * dr).sum()),
    }
    total = float(a["fee"].sum() - b["fee"].sum())
    if not math.isclose(sum(parts.values()), total, rel_tol=1e-9, abs_tol=1e-6):
        raise AssertionError("fee bridge does not close")
    return parts


def contribution_bridge(b: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    """Reference -> compared contribution bridge. Columns: step, effect, kind."""
    fee = fee_bridge(b, a)
    tb, dt = float(b["tpv"].sum()), float(a["tpv"].sum() - b["tpv"].sum())
    rows = [("Contribution (reference)", float(b["contribution"].sum()), "start")]
    labels = {"volume": "Fee: TPV volume", "mix": "Fee: country mix", "rate": "Fee: take rate",
              "interaction": "Fee: interaction (vol x mix x rate)"}
    rows += [(labels[k], v, "fee") for k, v in fee.items()]
    for col, name in COST_LINES.items():
        d_line = float(a[col].sum() - b[col].sum())
        vol = dt * float(b[col].sum()) / tb
        rows.append((f"{name}: volume", -vol, "cost"))
        rows.append((f"{name}: rate/mix", -(d_line - vol), "cost"))
    end = float(a["contribution"].sum())
    effects = sum(v for _, v, k in rows if k != "start")
    residual = end - rows[0][1] - effects
    rows.append(("Residual", residual, "residual"))
    rows.append(("Contribution (compared)", end, "end"))
    out = pd.DataFrame(rows, columns=["step", "effect", "kind"])
    if abs(residual) > 1e-6 * max(1.0, abs(end)):
        raise AssertionError(f"contribution bridge residual too large: {residual}")
    return out


def _logmean(a: float, b: float) -> float:
    return a if math.isclose(a, b, rel_tol=1e-12) else (a - b) / (math.log(a) - math.log(b))


def lmdi(drivers0: dict[str, float], drivers1: dict[str, float]) -> pd.DataFrame:
    """LMDI-I decomposition of a product of drivers: exact, interactions shared symmetrically."""
    t0, t1 = float(np.prod(list(drivers0.values()))), float(np.prod(list(drivers1.values())))
    w = _logmean(t1, t0)
    rows = [{"driver": k, "from": drivers0[k], "to": drivers1[k],
             "effect": w * math.log(drivers1[k] / drivers0[k])} for k in drivers0]
    out = pd.DataFrame(rows)
    if not math.isclose(out["effect"].sum(), t1 - t0, rel_tol=1e-9, abs_tol=1e-6):
        raise AssertionError("LMDI does not close")
    return out
