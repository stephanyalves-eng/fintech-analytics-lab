from __future__ import annotations

from datetime import date

import pandas as pd

from fintech_lab.p2_forecasting.adjustments import generate_adjustments
from fintech_lab.p2_forecasting.calendar import build_calendar


def test_calendar_rules_2025():
    cal = build_calendar(date(2025, 1, 1), date(2025, 12, 31)).set_index("date_local")
    assert cal.loc[date(2025, 4, 18), "holiday_br"] and cal.loc[date(2025, 4, 18), "holiday_cl"]
    assert cal.loc[date(2025, 11, 17), "holiday_mx"]           # 3rd Monday of November
    assert cal.loc[date(2025, 2, 3), "holiday_mx"]             # 1st Monday of February
    assert cal.loc[date(2025, 11, 28), "is_black_friday"]
    assert cal.loc[date(2025, 12, 1), "is_cyber_monday"]
    assert cal["is_black_friday"].sum() == 1 and len(cal) == 365
    assert cal.loc[date(2025, 1, 6), "dow"] == 0               # Monday


def _pay(n=4000):
    return pd.DataFrame({
        "payment_id": [f"P{i:07d}" for i in range(n)],
        "merchant_id": "M1",
        "method_code": ["credit_card", "debit_card", "pix", "credit_card"] * (n // 4),
        "date_local": pd.Timestamp("2025-03-01").date(),
        "amount_brl": 100.0, "fee_brl": 2.0,
    })


def test_adjustments_deterministic_exclusive_and_order_free(cfg):
    pay = _pay()
    a = generate_adjustments(pay, cfg)
    b = generate_adjustments(pay.sample(frac=1.0, random_state=1), cfg)
    pd.testing.assert_frame_equal(a, b)
    assert a["payment_id"].is_unique                      # refund XOR chargeback
    assert set(a["event_type"]) == {"refund", "chargeback"}
    assert not a.loc[a["event_type"] == "chargeback", "method_code"].eq("pix").any()
    ref = a[a["event_type"] == "refund"]
    delay = (pd.to_datetime(ref["event_date_local"]) - pd.Timestamp("2025-03-01")).dt.days
    assert delay.between(*cfg["refund"]["delay_days"]).all()
    rate = (a["event_type"] == "refund").sum() / len(pay)
    assert 0.008 < rate < 0.02                            # mix of 2% / 1% / 0.5% / 2%
    assert (a.loc[a["event_type"] == "chargeback", "chargeback_fee_brl"] == 15.0).all()
