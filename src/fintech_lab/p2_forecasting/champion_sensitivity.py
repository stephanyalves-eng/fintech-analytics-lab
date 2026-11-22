"""Post-hoc sensitivity of the champion rule to its approximation (audit L8). INFORMATIONAL ONLY.

The frozen rule compares a complex model with the best baseline using a paired standard error that
treats horizons as independent and origins as independent. Here the same paired differences are
resampled with a bootstrap (iid and circular block) to check whether the decisions are robust.
It uses validation data only (never the holdout) and changes nothing that is frozen.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from fintech_lab.p2_forecasting import backtest as bt
from fintech_lab.p2_forecasting.config import d


def _resample(n: int, rng: np.random.Generator, block: int) -> np.ndarray:
    if block <= 1:
        return rng.integers(0, n, n)
    starts = rng.integers(0, n, int(np.ceil(n / block)))
    idx = (starts[:, None] + np.arange(block)[None, :]) % n  # circular blocks keep neighbours
    return idx.ravel()[:n]


def bootstrap_delta(diffs: dict[int, np.ndarray], reps: int, block: int, seed: int
                    ) -> np.ndarray:
    """Distribution of the composite paired difference (mean over horizons of mean diff)."""
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for b in range(reps):
        out[b] = np.mean([v[_resample(len(v), rng, block)].mean() for v in diffs.values()])
    return out


def run(fc: pd.DataFrame, champs: pd.DataFrame, cfg: dict[str, Any], reps: int = 5000,
        seed: int = 20262203) -> pd.DataFrame:
    as_of: date = d(cfg["as_of"])
    mult = float(cfg["selection"]["se_multiplier"])
    rows = []
    for r in champs.itertuples():
        if not isinstance(r.best_complex, str):
            continue
        diffs = {}
        for h in cfg["horizons"]:
            a = bt._per_origin_wape(fc, r.target, r.best_complex, h, as_of)
            b = bt._per_origin_wape(fc, r.target, r.best_baseline, h, as_of)
            diffs[h] = (a - b).dropna().to_numpy(float)
        point = float(np.mean([v.mean() for v in diffs.values()]))
        for name, block in (("analytic (frozen rule)", 0), ("bootstrap iid", 1),
                            ("bootstrap block=4", 4)):
            if block == 0:
                se = r.paired_se if r.paired_se == r.paired_se else float("nan")
                lo = hi = p_neg = float("nan")
            else:
                dist = bootstrap_delta(diffs, reps, block, seed)
                se = float(dist.std(ddof=1))
                lo, hi = (float(x) for x in np.quantile(dist, [0.025, 0.975]))
                p_neg = float((dist < 0).mean())
            rows.append({
                "target": r.target, "complex": r.best_complex, "baseline": r.best_baseline,
                "method": name, "delta_point": point, "se": se, "ci95_lo": lo, "ci95_hi": hi,
                "p_delta_negative": p_neg,
                "complex_wins_by_rule": bool(point < -mult * se) if se == se else False,
                "frozen_champion": r.champion,
                "frozen_decision_is_complex": r.champion == r.best_complex,
            })
    out = pd.DataFrame(rows)
    out["same_decision_as_frozen"] = (
        out["complex_wins_by_rule"] == out["frozen_decision_is_complex"]
    )
    return out
