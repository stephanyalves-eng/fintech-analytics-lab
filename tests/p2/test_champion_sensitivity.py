from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fintech_lab.p2_forecasting import champion_sensitivity as cs


def test_bootstrap_distribution_centres_on_the_point_estimate():
    rng = np.random.default_rng(1)
    diffs = {7: rng.normal(-0.02, 0.005, 26), 30: rng.normal(-0.02, 0.005, 22),
             90: rng.normal(-0.02, 0.005, 14)}
    point = np.mean([v.mean() for v in diffs.values()])
    for block in (1, 4):
        dist = cs.bootstrap_delta(diffs, 3000, block, seed=7)
        assert abs(dist.mean() - point) < 0.002
        assert dist.std(ddof=1) > 0
    a = cs.bootstrap_delta(diffs, 200, 4, seed=7)
    b = cs.bootstrap_delta(diffs, 200, 4, seed=7)
    assert (a == b).all()  # seeded: reproducible


def test_resample_block_keeps_neighbouring_origins_together():
    rng = np.random.default_rng(0)
    idx = cs._resample(20, rng, block=4)
    assert len(idx) == 20
    diffs = np.diff(idx[:4]) % 20
    assert (diffs == 1).all()  # first block is 4 consecutive origins (circular)


def _fc(delta):
    rows = []
    for o in pd.date_range("2025-04-01", "2025-09-23", freq="7D"):
        for mdl, err in (("naive", 10.0), ("ets", 10.0 + delta)):
            for step in range(1, 8):
                rows.append({"target": "x", "model": mdl, "origin": o, "step": step,
                             "date": o + pd.Timedelta(days=step), "actual": 100.0,
                             "yhat": 100.0 + err})
    return pd.DataFrame(rows)


@pytest.mark.parametrize(("delta", "complex_wins"), [(-3.0, True), (3.0, False)])
def test_run_flags_clear_wins_and_losses(delta, complex_wins):
    cfg = {"as_of": "2025-09-30", "horizons": [7], "selection": {"se_multiplier": 1.0}}
    champs = pd.DataFrame([{
        "target": "x", "champion": "ets" if complex_wins else "naive", "best_complex": "ets",
        "best_baseline": "naive", "paired_se": 0.0005}])
    out = cs.run(_fc(delta), champs, cfg, reps=300)
    boot = out[out["method"] != "analytic (frozen rule)"]
    # a constant paired difference has zero spread, so the bootstrap rule needs delta < 0 strictly
    assert (boot["complex_wins_by_rule"] == complex_wins).all()
    assert (boot["p_delta_negative"] == (1.0 if complex_wins else 0.0)).all()
