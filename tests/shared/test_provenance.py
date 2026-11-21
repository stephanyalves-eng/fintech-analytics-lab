import numpy as np
import pytest

from fintech_lab.shared.provenance import DataOrigin, make_rng


def test_origin_values():
    assert {o.value for o in DataOrigin} == {"observed", "synthetic", "derived"}


def test_same_seed_same_draws():
    a = make_rng(42).normal(size=5)
    b = make_rng(42).normal(size=5)
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("bad", [-1, 1.5, "42", True])
def test_invalid_seed_rejected(bad):
    with pytest.raises(ValueError):
        make_rng(bad)


def test_environment_records_versions():
    from fintech_lab.shared.provenance import environment

    env = environment()
    assert env["python"].count(".") == 2
    for pkg in ("numpy", "pandas", "pyarrow", "duckdb"):
        assert env[pkg] != "not installed"
    assert environment(("no-such-package-xyz",))["no-such-package-xyz"] == "not installed"
