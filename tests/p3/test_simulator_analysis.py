"""P3.2/P3.3 tests: simulator invariants, estimators, gates, decisions, analysis/sim separation."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.proportion import proportions_ztest

from fintech_lab.p3_experiments import analysis as an
from fintech_lab.p3_experiments.assignment import assign, bucket
from fintech_lab.p3_experiments.decision import decide
from fintech_lab.p3_experiments.power import load_protocol
from fintech_lab.p3_experiments.simulator import SCENARIOS, generate, write_scenario

N = 12_000
PKG = Path(an.__file__).parent


@pytest.fixture(scope="module")
def protocol():
    return load_protocol()


@pytest.fixture(scope="module")
def sims():
    return {s: generate(s, candidate_users=N) for s in SCENARIOS}


@pytest.fixture(scope="module")
def results(sims, protocol, tmp_path_factory):
    out = {}
    root = tmp_path_factory.mktemp("p3data")
    for s in SCENARIOS:
        write_scenario(s, out_root=root, candidate_users=N)
        r = an.analyze(root / s, protocol)
        r["decision"] = decide(r)
        out[s] = r
    return out


# ---------------------------------------------------------------- simulator
def test_deterministic(sims):
    u, e, _ = generate("positive", candidate_users=N)
    pd.testing.assert_frame_equal(u, sims["positive"][0])
    pd.testing.assert_frame_equal(e, sims["positive"][1])


def test_assignment_is_stable_and_matches_protocol(sims, protocol):
    u = sims["null"][0]
    assert (assign(u["user_id"].to_numpy(), protocol) == u["assigned_arm"].to_numpy()).all()
    assert bucket("U0000001", protocol["assignment"]["salt"]) == bucket(
        "U0000001", protocol["assignment"]["salt"]
    )
    share_b = (u["assigned_arm"] == "B").mean()
    assert 0.48 < share_b < 0.52


def test_no_cross_group_and_eligibility(sims):
    for u, e, _ in sims.values():
        assert not u["user_id"].duplicated().any()
        exposed = set(e.loc[e.event_type == "exposure", "user_id"])
        assert exposed <= set(u.loc[u.eligible, "user_id"])
        assert not (u.is_internal & u.eligible).any()
        assert not (u.prefraud_blocked & u.eligible).any()


def test_event_ordering(sims):
    e = sims["null"][1]
    first = e[e.event_type == "exposure"].set_index("user_id")["ts"]
    assert (e["ts"] >= e["user_id"].map(first)).all()
    cs = e[e.event_type == "checkout_start"].set_index("user_id")["ts"]
    assert (cs == first.reindex(cs.index)).all()
    att = e[e.event_type == "payment_attempt"].set_index("attempt_id")["ts"]
    appr = e[e.event_type == "payment_approved"].set_index("attempt_id")["ts"]
    common = appr.index.intersection(att.index)
    assert (appr[common] >= att[common]).all()
    cb = e[e.event_type == "chargeback"].set_index("attempt_id")["ts"]
    assert (cb > appr.reindex(cb.index)).all()


def test_labels_and_truth_separate(tmp_path, sims):
    out = write_scenario("null", out_root=tmp_path, candidate_users=2000)
    assert (out / "truth.json").exists()
    assert "effect" not in (out / "manifest.json").read_text()
    assert '"synthetic"' in (out / "manifest.json").read_text()


# ---------------------------------------------------------------- estimators
def test_two_proportions_matches_statsmodels():
    r = an.two_proportions(600, 1000, 640, 1000)
    z, p = proportions_ztest([640, 600], [1000, 1000])
    assert r["p_value"] == pytest.approx(p, rel=1e-6)
    assert r["diff"] == pytest.approx(0.04)
    assert r["ci_low"] < 0.04 < r["ci_high"]


def test_ratio_cluster_known_value():
    num = np.array([1.0, 0, 0, 1])
    den = np.array([2.0, 1, 1, 2])
    r, var, _ = an.ratio_cluster(num, den)
    assert r == pytest.approx(2 / 6)
    resid = num - r * den
    assert var == pytest.approx(4 / 3 * np.sum(resid**2) / 36)


def test_status_rule():
    assert an.status_from_bounds(-0.1, 0.001, 0.002) == "pass"
    assert an.status_from_bounds(0.003, 0.01, 0.002) == "fail"
    assert an.status_from_bounds(-0.001, 0.005, 0.002) == "undetermined"


# ---------------------------------------------------------------- scenarios end to end
def test_scenario_decisions(results):
    assert results["srm"]["decision"]["decision"] == "INVALID"
    assert not results["srm"]["gates"]["srm"]["pass"]
    assert results["missing"]["decision"]["decision"] == "INVALID"
    assert not results["missing"]["gates"]["missing_events"]["pass"]
    assert results["negative"]["decision"]["decision"] == "DO NOT LAUNCH"
    assert results["null"]["decision"]["decision"] != "LAUNCH"
    assert results["positive"]["primary"]["diff"] > 0
    assert results["positive"]["decision"]["decision"] in {"LAUNCH", "INCONCLUSIVE"}
    for r in results.values():
        assert all(math.isfinite(r["primary"][k]) for k in ("diff", "ci_low", "ci_high"))


def test_valid_scenarios_pass_gates(results):
    for s in ("null", "positive", "negative"):
        assert results[s]["gates"]["all_pass"], s


def test_sensitivity_hc1_matches_primary(results):
    r = results["null"]
    assert r["sensitivity"]["robust_hc1"]["diff"] == pytest.approx(r["primary"]["diff"])


def test_analysis_requires_lock(tmp_path, monkeypatch):
    from fintech_lab.p3_experiments import lock

    def boom():
        raise lock.ProtocolLockError("x")

    monkeypatch.setattr(an, "verify_lock", boom)
    with pytest.raises(lock.ProtocolLockError):
        an.analyze(tmp_path)


# ---------------------------------------------------------------- separation of concerns
def _code_facts(path: Path) -> tuple[list[str], list[str]]:
    """(imported module names, string literals) excluding docstrings."""
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef):
            d = node.body[0] if node.body else None
            if isinstance(d, ast.Expr) and isinstance(d.value, ast.Constant):
                docs.add(id(d.value))
    mods, strs = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docs):
            strs.append(node.value)
    return mods, strs


def test_analysis_never_touches_simulation_truth():
    root = PKG.parents[2] / "projects" / "03-experimentation-lab" / "app" / "app.py"
    files = [PKG / n for n in ("analysis.py", "decision.py", "economics.py", "montecarlo.py",
                                "report.py")]
    files += [root] if root.exists() else []
    for f in files:
        mods, strs = _code_facts(f)
        assert not any("simulator" in m for m in mods), f.name
        assert not any("simulation" in s or "truth" in s for s in strs), f.name
