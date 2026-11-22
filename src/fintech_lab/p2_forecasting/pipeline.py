"""One instruction for the whole P2 pipeline (mart -> backtest -> holdout -> budget v2 -> close).

Frozen artifacts (budget v1/v2, champions) live in ``config_dir``: if a file is already there it is
VERIFIED and reused, never overwritten; if absent it is created once. Tests use a temp config_dir.
"""

from __future__ import annotations

from pathlib import Path

from fintech_lab.p2_forecasting.cli import main

ARTIFACTS = ("fct_daily_total.parquet", "fct_monthly.parquet", "budget_v1.parquet",
             "budget_v2.parquet", "backtest/fct_holdout_forecast.parquet",
             "backtest/fct_backtest_forecast.parquet", "backtest/fct_backtest_metrics.parquet")


def artifacts_ready(data_dir: str | Path) -> bool:
    return all((Path(data_dir) / a).exists() for a in ARTIFACTS)


def run_all(p1_data: str | Path, data_dir: str | Path, config_dir: str | Path,
            reports_dir: str | Path, workers: int = 4) -> None:
    c, data, rep = Path(config_dir), str(data_dir), str(reports_dir)
    top = ["--assumptions", str(c / "assumptions.yaml"), "--p1-data", str(p1_data)]
    champions = c / "champions_b1.yaml"
    bt = ["--config", str(c / "backtest.yaml"), "--out", data, "--champions", str(champions),
          "--reports", rep]
    steps = [
        [*top, "build", "--out", data, "--budget", str(c / "budget_v1.yaml")],
        [*top, "backtest", *bt, "--workers", str(workers),
         *([] if champions.exists() else ["--freeze"])],
        [*top, "holdout", *bt],
        [*top, "sensitivity", "--config", str(c / "backtest.yaml"), "--out", data,
         "--reports", rep],
        [*top, "budget-v2", "--out", data, "--rules", str(c / "budget_v2_rules.yaml"),
         "--budget-v2", str(c / "budget_v2.yaml")],
        [*top, "close", *bt[:6], "--scenarios", str(c / "scenarios.yaml"),
         "--alerts", str(c / "alerts.yaml"), "--reports", rep],
    ]
    for argv in steps:
        if main(argv) != 0:
            raise RuntimeError(f"pipeline step failed: {argv[len(top)]}")
