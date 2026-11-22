from __future__ import annotations

import pytest

from fintech_lab.p1_payments.corrupt import DEFECTS
from fintech_lab.p1_payments.warehouse import run_checks


def test_clean_dataset_passes_all_contract_checks(con):
    results = run_checks(con, "contract")
    assert len(results) == 14
    assert results == dict.fromkeys(results, 0)


def test_corrupted_manifest_lists_every_defect(corrupted):
    _, manifest = corrupted
    assert manifest["dataset_kind"] == "corrupted"
    assert set(manifest["injected_defects"]) == set(DEFECTS)


@pytest.mark.parametrize("defect", sorted(DEFECTS))
def test_each_injected_defect_is_detected(corrupted, defect):
    con, manifest = corrupted
    check = manifest["injected_defects"][defect]["expected_check"]
    assert run_checks(con, "contract")[check] > 0, f"{defect} not caught by {check}"
