# P2 — TPV, Revenue & Margin Forecasting (synthetic)

Forecasting cockpit and reproducible pipeline for a fintech closing quarter. **All data is synthetic**
(P1 payments + synthetic refunds, chargebacks, costs and budgets). Revenue and margin are estimates
`[TO VERIFY]`; nothing here is a real result.

## Run
```powershell
.\.venv\Scripts\Activate.ps1
python -m fintech_lab.p1_payments.cli generate          # P1 data (once)
python -m fintech_lab.p2_forecasting.cli pipeline       # mart -> backtest -> holdout -> budget v2 -> close
python -m fintech_lab.p2_forecasting.cli dashboard      # Streamlit cockpit on :8503 (runs the pipeline if needed)
python -m fintech_lab.p2_forecasting.cli audit          # independent recompute from raw P1 -> reports/audit_p2.md
pytest -q tests/p2
```
Frozen artifacts (`configs/budget_v1.yaml`, `budget_v2.yaml`, `champions_b1.yaml`) are verified and reused,
never overwritten. The pipeline is idempotent: same inputs give the same tables and CSV reports (fit timings are kept only in the parquet).

## What is inside
| Stage | Where |
|---|---|
| Specification, contracts, assumptions | `docs/problem_statement.md`, `metric_contracts.md`, `assumptions.md`, `data_dictionary.md` |
| Daily mart (DuckDB on P1 core) + reconciliation R01–R10 | `sql/mart.sql`, `sql/checks.sql`, `src/fintech_lab/p2_forecasting/mart.py` |
| Baselines, ETS, SARIMA, rolling-origin backtest, frozen champions, T4 holdout | `docs/methods.md`, `reports/backtest_*`, `reports/holdout_t4.*` |
| Scenarios, variance bridges, alerts, executive report | `docs/scenarios_bridge.md`, `reports/executive_closing_report.md`, `reports/p24_*.csv` |
| Budget v1 (labelled as-of 2024-12-31, anchored on January 2025; purposeful error) and v2 (run-rate reforecast at the cut-off) | `configs/`, `docs/assumptions.md`, `docs/methods.md` |
| Dashboard, one-pager, QA, audit | `app/app.py`, `reports/executive_one_pager.html`, `docs/dashboard_qa.md`, `reports/audit_p2.md`, `reports/a11y_axe.md` |

## Headline (T4/2025, computed; see the report for definitions)
Actual TPV was 53.0% above budget v1 and 25.7% above the forecast made at the 2025-09-30 cut-off; the
contribution margin was 69.8% below budget v1. Budget v1's processing-cost and refund+chargeback
assumptions were not calibrated to P1 (documented; v1 stays frozen). Budget v2 (numbers from data up to the cut-off only, but its rules were chosen after v1 failed, so not a blind pre-registration) reduces the TPV error from
−34.6% to −17.1% and the margin error from +231.4% to −10.1%. One quarter of synthetic data is a case, not a statistic.

## Limits
One year of history (no annual seasonality learnable), one holdout quarter, scenario values are assumptions,
holidays are a curated rule set `[TO VERIFY]`, an automated, partial keyboard smoke test exists (`reports/keyboard_smoke.md`) but human keyboard and screen-reader checks are `[TO VERIFY]`.
Design tokens are neutral placeholders until the brand design system is provided.
