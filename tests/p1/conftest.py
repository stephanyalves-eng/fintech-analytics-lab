from __future__ import annotations

import pytest

from fintech_lab.p1_payments.corrupt import make_corrupted
from fintech_lab.p1_payments.generator import generate, load_config
from fintech_lab.p1_payments.io import write_dataset
from fintech_lab.p1_payments.warehouse import build, connect

SMALL = {"target_attempts": 20_000, "n_merchants": 60}


@pytest.fixture(scope="session")
def cfg():
    return load_config(**SMALL)


@pytest.fixture(scope="session")
def tables(cfg):
    return generate(cfg)


@pytest.fixture(scope="session")
def dataset_dir(tables, cfg, tmp_path_factory):
    out = tmp_path_factory.mktemp("p1_clean")
    write_dataset(tables, out, cfg)
    return out


@pytest.fixture(scope="session")
def con(dataset_dir):
    c = connect()
    build(c, dataset_dir)
    yield c
    c.close()


@pytest.fixture(scope="session")
def corrupted(cfg, tmp_path_factory):
    out = tmp_path_factory.mktemp("p1_corrupted")
    tables, extra = make_corrupted(cfg)
    manifest = write_dataset(tables, out, cfg, kind="corrupted", extra=extra)
    c = connect()
    build(c, out, marts=False)
    yield c, manifest
    c.close()
