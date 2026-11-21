"""HYPOTHETICAL economics of B vs A (P3.4). Synthetic data x assumed take rate / fees.

Value per exposed user = take_rate x approved amount - simulated processing/3DS cost
                         - (chargeback amount + fixed fee per chargeback).
The annualisation assumes the experiment population repeats every year (external validity is
NOT established). Nothing here changes the locked decision rule.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fintech_lab.p3_experiments.analysis import Z
from fintech_lab.p3_experiments.power import P3_ROOT

ECON_YAML = P3_ROOT / "configs" / "economics.yaml"


def load_economics(path: Path = ECON_YAML) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def user_value(u: pd.DataFrame, econ: dict[str, Any]) -> pd.Series:
    return (econ["take_rate_pct"] * u["approved_amount"] - u["cost_brl"]
            - u["chargeback_amount"] - econ["chargeback_fee_brl"] * u["n_chargeback"])  # fmt: skip


def evaluate(u: pd.DataFrame, econ: dict[str, Any]) -> dict[str, Any]:
    v = user_value(u, econ)
    a, b = v[u.assigned_arm == "A"].to_numpy(), v[u.assigned_arm == "B"].to_numpy()
    d = float(b.mean() - a.mean())
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    n_year = econ["annual_eligible_users"]
    cost = econ["implementation_cost_brl"]
    lo, hi = (d - Z * se) * n_year, (d + Z * se) * n_year
    return {
        "label": "HYPOTHETICAL - assumed take rate and fees [TO VERIFY]",
        "value_per_user_a": float(a.mean()), "value_per_user_b": float(b.mean()),
        "diff_per_user": d, "ci_low_per_user": d - Z * se, "ci_high_per_user": d + Z * se,
        "annual_users": n_year, "annual_delta": d * n_year, "annual_ci_low": lo,
        "annual_ci_high": hi, "implementation_cost": cost, "year1_net": d * n_year - cost,
        "year1_net_ci_low": lo - cost, "year1_net_ci_high": hi - cost,
        "breakeven_diff_per_user": cost / n_year,
        "ci_excludes_breakeven": bool(d - Z * se > cost / n_year or d + Z * se < cost / n_year),
    }  # fmt: skip
