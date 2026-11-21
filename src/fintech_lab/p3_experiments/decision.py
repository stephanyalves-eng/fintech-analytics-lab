"""Decision layer (P3.4): applies the LOCKED rule of protocol section 8, in order.

invalid -> do_not_launch -> launch -> inconclusive. Economics and exploratory segments are
reported next to the decision but never change it.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from fintech_lab.p3_experiments.analysis import two_proportions

LAUNCH, DO_NOT_LAUNCH, INCONCLUSIVE, INVALID = "LAUNCH", "DO NOT LAUNCH", "INCONCLUSIVE", "INVALID"
GATE_LABEL = {"srm": "SRM", "assignment_integrity": "assignment integrity",
              "events_before_exposure": "events before exposure",
              "missing_events": "missing events"}  # fmt: skip


def decide(res: dict[str, Any]) -> dict[str, Any]:
    gates, prim, gr = res["gates"], res["primary"], res["guardrails"]
    failed = [GATE_LABEL[k] for k in GATE_LABEL if not gates[k]["pass"]]
    if failed:
        return {"decision": INVALID, "rule": "section 8, step 1",
                "reasons": [f"validity gate failed: {', '.join(failed)}; no effect is interpreted"]}  # fmt: skip
    fails = [g["id"] for g in gr if g["status"] == "fail"]
    und = [g["id"] for g in gr if g["status"] == "undetermined"]
    if fails or prim["ci_high"] < 0:
        why = []
        if prim["ci_high"] < 0:
            why.append(f"P01 95% CI upper bound {prim['ci_high']:+.4f} < 0 (conversion fell)")
        if fails:
            why.append(f"guardrail(s) failed (harm beyond margin): {', '.join(fails)}")
        return {"decision": DO_NOT_LAUNCH, "rule": "section 8, step 2", "reasons": why}
    if prim["ci_low"] > 0 and not und:
        return {"decision": LAUNCH, "rule": "section 8, step 3",
                "reasons": [f"P01 95% CI lower bound {prim['ci_low']:+.4f} > 0",
                            "all guardrails pass (non-inferiority shown)"]}  # fmt: skip
    why = []
    if prim["ci_low"] <= 0:
        why.append(f"P01 95% CI [{prim['ci_low']:+.4f}, {prim['ci_high']:+.4f}] includes 0; "
                   "non-significance is not evidence of no effect")  # fmt: skip
    if und:
        why.append(f"guardrail(s) undetermined (non-inferiority not shown): {', '.join(und)}")
    return {"decision": INCONCLUSIVE, "rule": "section 8, step 4", "reasons": why}


def exploratory_segments(u: pd.DataFrame, protocol: dict[str, Any], min_n: int = 500) -> pd.DataFrame:
    """P01 effect per segment level. EXPLORATORY: no multiplicity control, not used to decide."""
    rows = []
    for seg in protocol["exploratory"]["segments"]:
        col = {"new_vs_returning_user": "user_type"}.get(seg, seg)
        for level, s in u.groupby(col):
            a, b = s[s.assigned_arm == "A"], s[s.assigned_arm == "B"]
            if min(len(a), len(b)) < min_n:
                continue
            r = two_proportions(int(a.converted.sum()), len(a), int(b.converted.sum()), len(b))
            rows.append({"segment": seg, "level": level, "n_a": len(a), "n_b": len(b),
                         "p_a": r["p_a"], "p_b": r["p_b"], "diff": r["diff"],
                         "ci_low": r["ci_low"], "ci_high": r["ci_high"],
                         "status": "exploratory"})  # fmt: skip
    return pd.DataFrame(rows)
