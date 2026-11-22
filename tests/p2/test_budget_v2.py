from __future__ import annotations

import copy

import pandas as pd
import pytest
import yaml

from fintech_lab.p2_forecasting import budget
from fintech_lab.p2_forecasting.config import DEFAULT_BUDGET_V2_RULES

C = ["BR", "CL", "MX"]


@pytest.fixture(scope="module")
def rules():
    return yaml.safe_load(DEFAULT_BUDGET_V2_RULES.read_text(encoding="utf-8"))


def _inputs(t4_scale=1.0):
    months = pd.date_range("2025-01-01", "2025-12-01", freq="MS")
    mrows = [(m.date(), c, 1000.0 * (1 + 0.05 * i) * (t4_scale if m.month >= 10 else 1.0))
             for i, m in enumerate(months) for c in C]
    monthly = pd.DataFrame(mrows, columns=["month", "country", "tpv_brl"])
    days = pd.date_range("2025-01-01", "2025-12-31")
    srows = []
    for dd in days:
        k = t4_scale if dd.month >= 10 else 1.0
        for c in C:
            srows.append((dd.date(), c, 100.0 * k, 2.0 * k, 0.05 * k, 0.05 * k, 0.05 * k,
                          1.0 * k, 0.1 * k))
    seg = pd.DataFrame(srows, columns=["date_local", "country", "tpv_brl", "fee_brl",
                                       "refund_fee_returned_brl", "chargeback_brl",
                                       "incentive_brl", "proc_cost_brl", "var_cost_brl"])
    return monthly, seg


def test_calibration_ignores_everything_after_as_of(rules):
    a = budget.calibrate_v2(*_inputs(), rules)
    b = budget.calibrate_v2(*_inputs(t4_scale=50.0), rules)  # perturb Oct-Dec only
    assert a == b


def test_growth_level_and_ratios(rules):
    f = budget.calibrate_v2(*_inputs(), rules)
    # TPV grows 5% of the January level each month: Apr -> Sep, 5 intervals
    apr, sep = 1000 * (1 + 0.05 * 3), 1000 * (1 + 0.05 * 8)
    assert f["monthly_growth"]["BR"] == pytest.approx((sep / apr) ** (1 / 5) - 1, abs=1e-5)
    assert f["base_daily_tpv_brl"]["BR"] == pytest.approx(sep / 30, abs=0.01)
    assert f["take_rate"]["BR"] == pytest.approx(0.02)
    assert f["rc_share"]["BR"] == pytest.approx(0.1 / 2.0)
    assert f["proc_share"]["BR"] == pytest.approx(0.01)


def test_table_lines_close_and_freeze_is_immutable(rules, tmp_path):
    cfg = {"incentive_rate": 0.0005, "var_cost_rate": 0.001}
    f = budget.calibrate_v2(*_inputs(), rules)
    t = budget.build_budget_v2(f, rules, cfg)
    assert len(t) == 9 and set(t["month"].astype(str)) == {"2025-10-01", "2025-11-01", "2025-12-01"}
    assert ((t["fee_brl"] - t["rc_brl"] - t["inc_brl"] - t["net_revenue_brl"]).abs() < 1e-3).all()
    assert ((t["net_revenue_brl"] - t["proc_brl"] - t["var_brl"] - t["contribution_brl"]).abs()
            < 1e-3).all()
    p = tmp_path / "b2.yaml"
    doc = budget.freeze_v2(f, rules, cfg, p)
    assert budget.verify_v2(doc, rules, cfg)
    with pytest.raises(FileExistsError):
        budget.freeze_v2(f, rules, cfg, p)
    changed = copy.deepcopy(cfg)
    changed["var_cost_rate"] = 0.01
    assert not budget.verify_v2(doc, rules, changed)
