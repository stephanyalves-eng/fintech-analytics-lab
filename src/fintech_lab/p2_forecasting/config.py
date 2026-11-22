"""Paths and config loading for P2."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from fintech_lab.p1_payments.generator import REPO_ROOT

P2_ROOT = REPO_ROOT / "projects" / "02-tpv-revenue-forecasting"
SQL_DIR = P2_ROOT / "sql"
DEFAULT_ASSUMPTIONS = P2_ROOT / "configs" / "assumptions.yaml"
DEFAULT_BUDGET = P2_ROOT / "configs" / "budget_v1.yaml"
DEFAULT_P1_DATA = REPO_ROOT / "data" / "p1" / "default"
DEFAULT_BACKTEST = P2_ROOT / "configs" / "backtest.yaml"
DEFAULT_CHAMPIONS = P2_ROOT / "configs" / "champions_b1.yaml"
DEFAULT_SCENARIOS = P2_ROOT / "configs" / "scenarios.yaml"
DEFAULT_ALERTS = P2_ROOT / "configs" / "alerts.yaml"
REPORTS = P2_ROOT / "reports"
DEFAULT_OUT = REPO_ROOT / "data" / "p2"


def load_assumptions(path: str | Path = DEFAULT_ASSUMPTIONS) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def d(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))
