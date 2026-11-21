"""Pre-experiment sample size, MDE and power (P3.1).

Primary metric: two-sided two-proportion test, sized with Cohen's h (statsmodels
``NormalIndPower``). Proportion guardrails: one-sided non-inferiority z-test with true
difference 0, inflated by a design effect for repeated units per user.
Continuous guardrails (quantile/ratio) have no closed-form pre-experiment power here;
they are verified by Monte Carlo in P3.3.
"""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from scipy.stats import norm
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

REPO_ROOT = Path(__file__).resolve().parents[3]
P3_ROOT = REPO_ROOT / "projects" / "03-experimentation-lab"
PROTOCOL_YAML = P3_ROOT / "configs" / "protocol.yaml"
SAMPLE_SIZE_CSV = P3_ROOT / "reports" / "sample_size.csv"


def load_protocol(path: Path = PROTOCOL_YAML) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def n_two_proportions(p0: float, mde_abs: float, alpha: float, power: float) -> int:
    """Units per arm (1:1) to detect p0 -> p0 + mde_abs, two-sided."""
    if not 0 < p0 < 1 or not 0 < p0 + mde_abs < 1 or mde_abs == 0:
        raise ValueError("p0 and p0 + mde_abs must lie in (0, 1) and mde_abs != 0")
    h = abs(proportion_effectsize(p0 + mde_abs, p0))
    n = NormalIndPower().solve_power(effect_size=h, alpha=alpha, power=power, ratio=1.0)
    return math.ceil(n)


def mde_two_proportions(p0: float, n_per_arm: int, alpha: float, power: float) -> float:
    """Smallest positive absolute lift detectable with n_per_arm (inverse of Cohen's h)."""
    h = NormalIndPower().solve_power(nobs1=n_per_arm, alpha=alpha, power=power, ratio=1.0)
    p1 = math.sin(math.asin(math.sqrt(p0)) + h / 2) ** 2
    return p1 - p0


def ni_units_per_arm(p: float, margin: float, alpha_one_sided: float, power: float) -> float:
    """Independent units per arm for a non-inferiority test of a proportion (true diff = 0)."""
    z = norm.ppf(1 - alpha_one_sided) + norm.ppf(power)
    return z**2 * 2 * p * (1 - p) / margin**2


def ni_power(p: float, margin: float, n_units_per_arm: float, alpha_one_sided: float) -> float:
    """Power of the non-inferiority test with n independent units per arm (true diff = 0)."""
    se = math.sqrt(2 * p * (1 - p) / n_units_per_arm)
    return float(norm.cdf(margin / se - norm.ppf(1 - alpha_one_sided)))


@dataclass(frozen=True)
class SizeRow:
    metric_id: str
    metric: str
    test: str
    baseline: float
    effect_or_margin: float
    users_per_arm_required: int
    power_at_plan: float


def plan(protocol: dict[str, Any]) -> dict[str, Any]:
    """Planned users per arm = max over primary and proportion guardrails, + missing buffer."""
    pr = protocol["primary"]
    gr = protocol["guardrails"]
    deff = gr["design_effect_assumption"]
    a1, target = gr["alpha_one_sided"], gr["power_target"]

    rows: list[SizeRow] = []
    n_primary = n_two_proportions(
        pr["baseline_assumption"], pr["mde_abs"], pr["alpha"], pr["power"]
    )
    rows.append(
        SizeRow(pr["id"], pr["name"], "two-sided superiority", pr["baseline_assumption"],
                pr["mde_abs"], n_primary, float("nan"))
    )
    for g in gr["items"]:
        if g["kind"] != "proportion":
            continue
        units = ni_units_per_arm(g["baseline_assumption"], g["margin_abs"], a1, target)
        users = math.ceil(units * deff / g["units_per_user_assumption"])
        rows.append(
            SizeRow(g["id"], g["name"], "one-sided non-inferiority", g["baseline_assumption"],
                    g["margin_abs"], users, float("nan"))
        )

    required = max(r.users_per_arm_required for r in rows)
    planned = math.ceil(required / (1 - pr["missing_buffer"]))
    analysed = planned * (1 - pr["missing_buffer"])  # users expected with complete trails

    final: list[SizeRow] = []
    for r in rows:
        if r.metric_id == pr["id"]:
            p = NormalIndPower().power(
                effect_size=abs(proportion_effectsize(r.baseline + r.effect_or_margin,
                                                      r.baseline)),
                nobs1=analysed, alpha=pr["alpha"], ratio=1.0,
            )
        else:
            g = next(x for x in gr["items"] if x["id"] == r.metric_id)
            eff_units = analysed * g["units_per_user_assumption"] / deff
            p = ni_power(r.baseline, r.effect_or_margin, eff_units, a1)
        final.append(SizeRow(**{**asdict(r), "power_at_plan": round(float(p), 4)}))

    daily = protocol["traffic"]["daily_new_eligible_users_assumption"]
    min_days = protocol["windows_days"]["enrollment"]
    days = max(min_days, math.ceil(2 * planned / daily))
    days = math.ceil(days / 7) * 7  # whole weeks (weekly seasonality)
    w = protocol["windows_days"]
    joint = math.prod(r.power_at_plan for r in final)  # independence approximation
    return {
        "joint_power_approx": round(joint, 4),
        "rows": final,
        "binding_metric": max(rows, key=lambda r: r.users_per_arm_required).metric_id,
        "users_per_arm_required": required,
        "users_per_arm_planned": planned,
        "users_total_planned": 2 * planned,
        "mde_abs_at_plan": round(
            mde_two_proportions(pr["baseline_assumption"], math.floor(analysed),
                                pr["alpha"], pr["power"]), 5),
        "enrollment_days": days,
        "analysis_day": days + w["conversion"] + w["chargeback_maturation"],
    }


def write_sample_size_csv(result: dict[str, Any], path: Path = SAMPLE_SIZE_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(SizeRow.__dataclass_fields__)
    summary = {k: v for k, v in result.items() if k != "rows"}
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["# data_origin=derived (from synthetic assumptions in protocol.yaml)"])
        w.writerow(fields)
        for r in result["rows"]:
            w.writerow([getattr(r, k) for k in fields])
        for k, v in summary.items():
            w.writerow([f"# {k}={v}"])
    return path
