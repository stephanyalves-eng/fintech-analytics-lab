"""Headless Streamlit tests of the P1.5 app (AppTest): render, empty, error and scenario states."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from fintech_lab.p1_payments.generator import P1_ROOT

APP = str(P1_ROOT / "app" / "app.py")


@pytest.fixture
def app(db_file, dataset_dir, monkeypatch):
    monkeypatch.setenv("P1_DB_PATH", str(db_file))
    monkeypatch.setenv("P1_DATA_DIR", str(dataset_dir))
    return AppTest.from_file(APP, default_timeout=120)


def test_renders_all_tabs(app):
    at = app.run()
    assert not at.exception and not at.error
    assert len(at.tabs) == 6
    labels = [m.label for m in at.metric]
    assert "Payment success (M02)" in labels and "Retry recovery (M05)" in labels
    assert all(m.help for m in at.metric[:4])  # tooltips on headline KPIs
    assert any("SYNTHETIC" in md.value for md in at.markdown)


def test_empty_state(app):
    at = app.run()
    at.sidebar.multiselect[1].set_value(["credit_card"])
    at.sidebar.multiselect[2].set_value(["PIX_BR"])
    at.run()
    assert not at.exception
    assert any("No payments match" in i.value for i in at.info)


def test_scenario_controls(app):
    at = app.run()
    at.radio[0].set_value(2).run()
    assert not at.exception
    assert any(m.label == "M02 under scenario" for m in at.metric)


def test_missing_db_error_state(monkeypatch, tmp_path):
    monkeypatch.setenv("P1_DB_PATH", str(tmp_path / "nope.duckdb"))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.error and "Warehouse not found" in at.error[0].value
