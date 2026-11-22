from __future__ import annotations

import pytest

from fintech_lab.p1_payments.generator import generate, load_config
from fintech_lab.p1_payments.io import write_dataset
from fintech_lab.p2_forecasting.config import load_assumptions
from fintech_lab.p2_forecasting.mart import build_mart, run_checks


@pytest.fixture(scope="session")
def cfg():
    return load_assumptions()


@pytest.fixture(scope="session")
def p1_dir(tmp_path_factory):
    c = load_config(target_attempts=20_000, n_merchants=60)
    out = tmp_path_factory.mktemp("p1_small")
    write_dataset(generate(c), out, c)
    return out


@pytest.fixture(scope="session")
def con(p1_dir, cfg):
    return build_mart(p1_dir, cfg)


@pytest.fixture(scope="session")
def check_results(con, cfg):
    return run_checks(con, cfg)
