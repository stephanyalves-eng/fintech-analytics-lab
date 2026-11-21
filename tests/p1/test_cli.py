from __future__ import annotations

from fintech_lab.p1_payments import cli


def test_build_passes_on_clean_data(dataset_dir, tmp_path):
    db = tmp_path / "clean.duckdb"
    assert cli.main(["build", "--data", str(dataset_dir), "--db", str(db)]) == 0
    assert db.exists()


def test_build_refuses_contract_violations(corrupted_dir, tmp_path, capsys):
    out, _ = corrupted_dir
    db = tmp_path / "bad.duckdb"
    assert cli.main(["build", "--data", str(out), "--db", str(db)]) == 1
    assert not db.exists()
    err = capsys.readouterr().err
    assert "FAIL  c01_pk_unique" in err and "build aborted" in err


def test_build_skip_checks_is_explicit(corrupted_dir, tmp_path, capsys):
    out, _ = corrupted_dir
    db = tmp_path / "fixture.duckdb"
    assert cli.main(["build", "--data", str(out), "--db", str(db), "--skip-checks"]) == 0
    assert db.exists()
    assert "checks SKIPPED" in capsys.readouterr().out


def test_dashboard_does_not_launch_on_bad_data(corrupted_dir, tmp_path):
    out, _ = corrupted_dir
    db = tmp_path / "dash.duckdb"
    assert cli.main(["dashboard", "--data", str(out), "--db", str(db)]) == 1
    assert not db.exists()
