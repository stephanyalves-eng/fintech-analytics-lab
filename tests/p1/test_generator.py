from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from fintech_lab.p1_payments.generator import TABLES, generate, load_config
from fintech_lab.p1_payments.io import content_hash, write_dataset
from fintech_lab.p1_payments.warehouse import build, connect, run_checks


def test_same_seed_identical_data_and_files(cfg, tables, dataset_dir, tmp_path):
    again = generate(cfg)
    for name in TABLES:
        assert content_hash(again[name]) == content_hash(tables[name]), name
    m2 = write_dataset(again, tmp_path, cfg)
    m1 = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    assert m1["dataset_content_sha256"] == m2["dataset_content_sha256"]
    assert {t: v["file_sha256"] for t, v in m1["tables"].items()} == {
        t: v["file_sha256"] for t, v in m2["tables"].items()
    }


def test_different_seed_differs(cfg, tables):
    other = generate({**cfg, "seed": cfg["seed"] + 1})
    assert content_hash(other["fact_attempt"]) != content_hash(tables["fact_attempt"])


@pytest.mark.parametrize("target", [5_000, 12_345])
def test_volume_is_configurable(target):
    t = generate(load_config(target_attempts=target, n_merchants=40))
    n = len(t["fact_attempt"])
    assert target - 3 < n <= target  # payment prefix with <= 3 attempts each
    assert len(t["fact_payment"]) < n


@pytest.mark.parametrize("seed", [1, 7, 2024])
def test_contract_holds_across_seeds(seed, tmp_path):
    cfg = load_config(seed=seed, target_attempts=5_000, n_merchants=30)
    write_dataset(generate(cfg), tmp_path, cfg)
    with connect() as con:
        build(con, tmp_path, marts=False)
        assert run_checks(con, "contract") == dict.fromkeys(run_checks(con, "contract"), 0)


def test_unique_ids(tables):
    for t, pk in [
        ("fact_payment", "payment_id"),
        ("fact_attempt", "attempt_id"),
        ("fact_settlement", "settlement_id"),
        ("dim_merchant", "merchant_id"),
    ]:
        assert tables[t][pk].is_unique, t
    assert not tables["fact_attempt"].duplicated(["payment_id", "attempt_no"]).any()


def test_status_transitions(tables):
    """Every non-final attempt failed retryably; hard declines and approvals are terminal."""
    a = tables["fact_attempt"].merge(
        tables["dim_decline_code"][["decline_code", "category"]], on="decline_code", how="left"
    )
    a = a.sort_values(["payment_id", "attempt_no"])
    is_last = ~a["payment_id"].duplicated(keep="last")
    non_final = a[~is_last]
    retryable = (non_final["result"] == "error") | (
        (non_final["result"] == "declined") & (non_final["category"] == "soft")
    )
    assert retryable.all()
    assert (a.loc[a["result"] == "approved"].index.isin(a[is_last].index)).all()
    assert a.groupby("payment_id")["attempt_no"].max().le(3).all()


def test_temporal_ordering(tables):
    a = tables["fact_attempt"].sort_values(["payment_id", "attempt_no"])
    gaps = a.groupby("payment_id")["attempted_at_utc"].diff().dropna()
    assert (gaps > pd.Timedelta(0)).all()
    first = a[a["attempt_no"] == 1].merge(tables["fact_payment"], on="payment_id")
    assert (first["attempted_at_utc"] >= first["created_at_utc"]).all()


def test_amount_validity(tables):
    p = tables["fact_payment"]
    assert (p["amount"] > 0).all()
    clp = p.loc[p["currency"] == "CLP", "amount"]
    assert np.allclose(clp, clp.round(0))
    other = p.loc[p["currency"] != "CLP", "amount"]
    assert np.allclose(other * 100, (other * 100).round(0))
    assert (tables["fact_attempt"]["latency_ms"] > 0).all()


def test_payment_level_deduplication(tables):
    """TPV counts each succeeded payment once; a payment x attempt join would inflate it."""
    p, a = tables["fact_payment"], tables["fact_attempt"]
    succ = p[p["final_status"] == "succeeded"]
    approved = a[a["result"] == "approved"]
    assert approved["payment_id"].is_unique
    assert set(approved["payment_id"]) == set(succ["payment_id"])
    by_payment = succ.groupby("currency")["amount"].sum()
    naive = succ.merge(a, on="payment_id").groupby("currency")["amount"].sum()
    assert (naive >= by_payment).all() and (naive > by_payment).any()


def test_marked_synthetic(dataset_dir):
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_origin"] == "synthetic"
    for name in TABLES:
        meta = pq.read_schema(dataset_dir / f"{name}.parquet").metadata
        assert meta[b"data_origin"] == b"synthetic"
        assert manifest["tables"][name]["rows"] > 0


def test_config_validation():
    with pytest.raises(ValueError):
        load_config(seed=-1)
    with pytest.raises(ValueError):
        load_config(target_attempts=10)
    cfg = load_config()
    cfg["method_mix"]["MX"] = {"credit_card": 0.5, "pix": 0.5}
    with pytest.raises(ValueError):
        generate(cfg)


def test_manifest_records_environment(dataset_dir):
    m =json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    assert {"python", "numpy", "pandas", "pyarrow", "duckdb"} <= set(m["environment"])
