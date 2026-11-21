"""Headless Streamlit tests of the P3.5 app (AppTest) on null, positive, negative, SRM scenarios."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from fintech_lab.p3_experiments.power import P3_ROOT
from fintech_lab.p3_experiments.simulator import write_scenario

APP = str(P3_ROOT / "app" / "app.py")
SCENARIOS = ["null", "positive", "negative", "srm", "missing"]


@pytest.fixture(scope="module")
def data_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("p3app")
    for s in SCENARIOS:
        write_scenario(s, out_root=root, candidate_users=8000)
    return root


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenarios_render(data_root, monkeypatch, scenario):
    monkeypatch.setenv("P3_DATA_ROOT", str(data_root))
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.sidebar.radio[0].set_value(scenario).run()
    assert not at.exception
    invalid = scenario in ("srm", "missing")
    # the only expected st.error is the INVALID banner on the data-quality tab
    assert bool(at.error) == invalid
    assert len(at.tabs) == 7
    assert any("SYNTHETIC" in md.value for md in at.markdown)
    text = " ".join(md.value for md in at.markdown)
    if invalid:
        assert "INVALID" in text and "validity gate failed" in at.error[0].value


def test_missing_data_error_state(tmp_path, monkeypatch):
    monkeypatch.setenv("P3_DATA_ROOT", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.error and "Dataset not found" in at.error[0].value
