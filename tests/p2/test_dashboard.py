"""P2.5: full pipeline on a small P1 dataset (temp dirs, frozen files NOT touched), then the
Streamlit app (AppTest), KPI consistency and the one-pager."""

from __future__ import annotations

import shutil

import pandas as pd
import pytest
import yaml
from streamlit.testing.v1 import AppTest

from fintech_lab.p2_forecasting import dashboard_data as dd
from fintech_lab.p2_forecasting.config import P2_ROOT
from fintech_lab.p2_forecasting.onepager import build_onepager
from fintech_lab.p2_forecasting.pipeline import artifacts_ready, run_all

APP = str(P2_ROOT / "app" / "app.py")
CONFIGS = ["assumptions.yaml", "backtest.yaml", "scenarios.yaml", "alerts.yaml",
           "budget_v2_rules.yaml"]


@pytest.fixture(scope="module")
def env(p1_dir, tmp_path_factory):
    root = tmp_path_factory.mktemp("p2pipe")
    cfg_dir, data, reports = root / "configs", root / "data", root / "reports"
    cfg_dir.mkdir()
    for n in CONFIGS:
        shutil.copy(P2_ROOT / "configs" / n, cfg_dir / n)
    bt = yaml.safe_load((cfg_dir / "backtest.yaml").read_text(encoding="utf-8"))
    bt["origins"]["step_days"] = 21  # fewer origins: the test checks plumbing, not accuracy
    (cfg_dir / "backtest.yaml").write_text(yaml.safe_dump(bt), encoding="utf-8")
    run_all(p1_dir, data, cfg_dir, reports, workers=4)
    return {"data": data, "cfg": cfg_dir, "reports": reports}


def test_pipeline_outputs_and_frozen_files_created_in_temp_dir(env):
    assert artifacts_ready(env["data"])
    for f in ("budget_v1.yaml", "budget_v2.yaml", "champions_b1.yaml"):
        assert (env["cfg"] / f).exists()
    for f in ("executive_closing_report.md", "executive_one_pager.html",
              "monthly_actual_vs_budget.csv", "backtest_summary.md", "holdout_t4.csv"):
        assert (env["reports"] / f).exists()


def test_rerunning_the_pipeline_reuses_and_verifies_frozen_files(env, p1_dir):
    before = (env["cfg"] / "champions_b1.yaml").read_text(encoding="utf-8")
    one = (env["reports"] / "executive_one_pager.html").read_text(encoding="utf-8")
    run_all(p1_dir, env["data"], env["cfg"], env["reports"], workers=4)
    assert (env["cfg"] / "champions_b1.yaml").read_text(encoding="utf-8") == before
    assert (env["reports"] / "executive_one_pager.html").read_text(encoding="utf-8") == one


@pytest.fixture(scope="module")
def bundle(env):
    return dd.load_bundle(env["data"], env["cfg"])


def test_kpis_are_consistent_across_views(bundle):
    o, tot = bundle["o"], bundle["total"]
    t4s, t4e = (pd.Timestamp(x) for x in o["t4"])
    in_t4 = tot[(tot["date_local"] >= t4s) & (tot["date_local"] <= t4e)]
    assert o["headline"].set_index("metric").loc["TPV", "actual"] == pytest.approx(
        in_t4["tpv_brl"].sum())
    h = dd.history(bundle, tot["date_local"].min(), tot["date_local"].max(), [], [], [], [])
    assert h["tpv_brl"].sum() == pytest.approx(tot["tpv_brl"].sum())
    by_country = sum(dd.history(bundle, tot["date_local"].min(), tot["date_local"].max(),
                                [c], [], [], [])["tpv_brl"].sum() for c in ("BR", "CL", "MX"))
    assert by_country == pytest.approx(tot["tpv_brl"].sum())
    for grain in ("Week", "Month"):
        g = dd.regrain(h, grain)
        assert g["tpv_brl"].sum() == pytest.approx(h["tpv_brl"].sum())
        assert g["net_revenue_brl"].sum() == pytest.approx(h["net_revenue_brl"].sum())
        assert g["take_rate"].between(0, 0.2).all()
    # derived net/contribution of the filtered history equal the mart's own columns
    assert h["net_revenue_brl"].sum() == pytest.approx(tot["net_revenue_brl"].sum(), rel=1e-9)
    assert h["contribution_brl"].sum() == pytest.approx(tot["contribution_brl"].sum(), rel=1e-9)
    # a merchant selection is a subset of the total
    m = bundle["merchant_dim"]["merchant_id"].iloc[:3].tolist()
    sub = dd.history(bundle, tot["date_local"].min(), tot["date_local"].max(), [], [], [], m)
    assert 0 < sub["tpv_brl"].sum() < tot["tpv_brl"].sum()


def test_bridges_in_bundle_close(bundle):
    for k in ("budget_to_actual", "budget_to_forecast", "forecast_to_actual",
              "budget_v2_to_actual"):
        e = bundle["o"][k].set_index("step")["effect"]
        assert abs(e["Residual"]) < 1e-3


def test_onepager_is_reproducible_and_numbers_match(bundle, env):
    meta = {"as_of": "2025-09-30", "backtest_version": "b1", "assumptions_version": "v1",
            "p1_seed": 1}
    a, b = build_onepager(bundle["o"], meta), build_onepager(bundle["o"], meta)
    assert a == b and "SYNTHETIC DATA" in a and "TO VERIFY" in a
    tpv = bundle["o"]["headline"].set_index("metric").loc["TPV", "actual"]
    assert f"{tpv / 1e6:.2f}M" in a


@pytest.fixture
def app_env(env, monkeypatch):
    monkeypatch.setenv("P2_DATA_ROOT", str(env["data"]))
    monkeypatch.setenv("P2_CONFIG_DIR", str(env["cfg"]))


def test_app_renders_and_filters_work(app_env):
    at = AppTest.from_file(APP, default_timeout=240).run()
    assert not at.exception and not at.error
    assert len(at.tabs) == 8
    assert any("SYNTHETIC" in md.value for md in at.markdown)
    text = " ".join(md.value for md in at.markdown)
    for label in ("Data cut-off", "Last training day", "Forecast horizon", "Backtest / budgets"):
        assert label in text
    # country + grain + metric + model + target filters
    at.sidebar.multiselect[0].set_value(["BR"]).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("Month").run()
    assert not at.exception
    at.sidebar.selectbox[1].set_value("Net revenue").run()
    assert not at.exception
    tgt = next(s for s in at.sidebar.selectbox if s.label == "Forecast target")
    tgt.set_value("TPV MX").run()
    assert not at.exception
    mdl = next(s for s in at.sidebar.selectbox if s.label.startswith("Model"))
    mdl.set_value("naive").run()
    assert not at.exception and not at.error


def test_app_scenario_controls_and_empty_filter(app_env):
    at = AppTest.from_file(APP, default_timeout=240).run()
    preset = next(s for s in at.selectbox if s.label == "Preset")
    preset.set_value("conservative").run()
    assert not at.exception
    sliders = [s for s in at.slider if s.label == "Take rate"]
    assert sliders and sliders[0].value == -3
    sliders[0].set_value(-10).run()
    assert not at.exception
    # merchants + a tier with no overlap can leave an empty view: must show a message, not crash
    at.sidebar.multiselect[2].set_value(["small"]).run()
    assert not at.exception


def test_app_missing_artifacts_shows_error(tmp_path, monkeypatch):
    monkeypatch.setenv("P2_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("P2_CONFIG_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.error and "artifacts not found" in at.error[0].value


def test_independent_audit_passes_on_the_small_pipeline(env, p1_dir):
    from fintech_lab.p2_forecasting.audit import run_audit

    checks = run_audit(p1_dir, env["data"], env["cfg"], env["reports"])
    failed = [(n, d) for n, ok, d in checks if not ok]
    assert not failed, failed
    assert len(checks) >= 17
