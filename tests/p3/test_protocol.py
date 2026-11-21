from __future__ import annotations

import csv
import json
import math
import shutil

import pytest

from fintech_lab.p3_experiments import cli
from fintech_lab.p3_experiments.lock import (
    LOCK_PATH,
    LOCKED_FILES,
    ProtocolLockError,
    verify_lock,
    write_lock,
)
from fintech_lab.p3_experiments.power import (
    P3_ROOT,
    SAMPLE_SIZE_CSV,
    load_protocol,
    mde_two_proportions,
    n_two_proportions,
    ni_power,
    ni_units_per_arm,
    plan,
)


def test_n_two_proportions_known_value():
    # statsmodels NormalIndPower + Cohen's h, p 0.60 -> 0.62, alpha .05, power .80
    assert n_two_proportions(0.60, 0.02, 0.05, 0.80) == 9335


def test_n_close_to_classic_unpooled_formula():
    p0, p1 = 0.60, 0.62
    z = 1.959964 + 0.841621
    classic = z**2 * (p0 * (1 - p0) + p1 * (1 - p1)) / (p1 - p0) ** 2
    assert abs(n_two_proportions(p0, 0.02, 0.05, 0.80) / classic - 1) < 0.01


def test_mde_inverts_sample_size():
    n = n_two_proportions(0.60, 0.02, 0.05, 0.80)
    assert mde_two_proportions(0.60, n, 0.05, 0.80) == pytest.approx(0.02, abs=2e-5)


def test_ni_power_and_n_are_inverse():
    units = ni_units_per_arm(0.02, 0.005, 0.025, 0.80)
    assert ni_power(0.02, 0.005, units, 0.025) == pytest.approx(0.80, abs=1e-9)


def test_n_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        n_two_proportions(0.99, 0.02, 0.05, 0.8)


def test_plan_is_max_over_metrics_with_buffer():
    proto = load_protocol()
    r = plan(proto)
    req = max(row.users_per_arm_required for row in r["rows"])
    assert r["users_per_arm_required"] == req
    assert r["users_per_arm_planned"] == math.ceil(req / (1 - proto["primary"]["missing_buffer"]))
    assert r["enrollment_days"] % 7 == 0
    assert r["enrollment_days"] >= proto["windows_days"]["enrollment"]
    assert all(row.power_at_plan >= 0.80 - 1e-3 for row in r["rows"])


def test_protocol_yaml_is_consistent():
    p = load_protocol()
    a = p["assignment"]
    assert sum(a["allocation"].values()) == pytest.approx(1.0)
    assert a["arm_A_buckets"][1] + 1 == a["arm_B_buckets"][0]
    assert a["arm_B_buckets"][1] == a["buckets"] - 1
    assert p["experiment"]["data_origin"] == "synthetic"
    assert p["stopping"]["interim_efficacy_looks"] == 0
    assert {g["id"] for g in p["guardrails"]["items"]} == {"G1", "G2", "G3", "G4", "G5"}


def test_committed_csv_and_doc_match_current_plan():
    r = plan(load_protocol())
    with open(SAMPLE_SIZE_CSV, encoding="utf-8") as f:
        rows = [x for x in csv.reader(f) if x and not x[0].startswith("#")]
    body = {x[0]: int(x[5]) for x in rows[1:]}
    assert body == {row.metric_id: row.users_per_arm_required for row in r["rows"]}
    doc = (P3_ROOT / "docs" / "protocol.md").read_text(encoding="utf-8")
    for v in (*body.values(), r["users_per_arm_planned"], r["users_total_planned"]):
        assert str(v) in doc


@pytest.fixture
def proto_copy(tmp_path):
    for f in LOCKED_FILES:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(P3_ROOT / f, tmp_path / f)
    return tmp_path, tmp_path / "lock.json"


def test_lock_detects_change_and_requires_amendment(proto_copy):
    root, lock = proto_copy
    write_lock(root, lock)
    verify_lock(root, lock)
    yaml_path = root / "configs" / "protocol.yaml"
    yaml_path.write_text(yaml_path.read_text(encoding="utf-8") + "# edit\n", encoding="utf-8")
    with pytest.raises(ProtocolLockError, match="changed"):
        verify_lock(root, lock)
    with pytest.raises(ProtocolLockError, match="amendment"):
        write_lock(root, lock)
    amended = write_lock(root, lock, amend_reason="test amendment")
    assert amended["amendments"][0]["reason"] == "test amendment"
    verify_lock(root, lock)


def test_lock_ignores_crlf(proto_copy):
    root, lock = proto_copy
    write_lock(root, lock)
    md = root / "docs" / "protocol.md"
    lf = md.read_bytes().replace(b"\r\n", b"\n")  # checkout may already be CRLF (autocrlf)
    md.write_bytes(lf.replace(b"\n", b"\r\n"))
    verify_lock(root, lock)


def test_verify_fails_without_lock(tmp_path):
    with pytest.raises(ProtocolLockError, match="not locked"):
        verify_lock(tmp_path, tmp_path / "missing.json")


def test_repo_protocol_is_locked_and_cli_verifies(capsys):
    assert LOCK_PATH.exists(), "run `python -m fintech_lab.p3_experiments.cli lock`"
    assert set(json.loads(LOCK_PATH.read_text(encoding="utf-8"))["files"]) == set(LOCKED_FILES)
    assert cli.main(["verify"]) == 0
    assert "PASS" in capsys.readouterr().out
