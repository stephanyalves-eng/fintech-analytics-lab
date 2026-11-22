# Fintech Analytics Lab

Portfolio of three fintech analytics projects built on **synthetic, explicitly labeled data**, local-first and reproducible.

| # | Project | Focus | Status |
|---|---|---|---|
| 01 | [Payment Intelligence & Transaction Optimization](projects/01-payment-intelligence/README.md) | Authorization rate, declines, retries, routing scenarios, advanced SQL | Done; independent audits (P1, M7); CI green on GitHub Actions |
| 02 | [TPV, Revenue & Margin Forecasting](projects/02-tpv-revenue-forecasting/README.md) | Daily mart, baselines vs ETS/SARIMA, rolling-origin backtest, budgets, scenarios, variance bridge, cockpit | Done; independent audits (P2, M7); CI green on GitHub Actions |
| 03 | [Experimentation & A/B Testing Lab](projects/03-experimentation-lab/README.md) | Preregistered protocol, SRM, power, guardrails, launch decision | Done; independent audits (P3, M7); CI green on GitHub Actions |

> No result is reported unless executed, tested code produced it. All data is synthetic: nothing here is real
> payment data or real-world performance. Revenue and margin figures are estimates `[TO VERIFY]`.
> CI (ubuntu, Python 3.12, pinned lock): ruff, `pytest -q`, P1 generate/check/build, P2 pipeline + independent audit with the
> committed frozen budgets and champions, P3 verify/generate/analyze. Last verified run: [44977708812](https://github.com/stephanyalves-eng/fintech-analytics-lab/actions/runs/44977708812).
> The latest cross-project review is [`docs/audit_m7_final.md`](docs/audit_m7_final.md); current state in [`PROGRESS.md`](PROGRESS.md).

## Setup (Windows)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt   # pinned versions used for committed outputs
python -m pip install -e . --no-deps
ruff check .
pytest -q                                        # ~2-4 min (includes the P2 pipeline test)
```

## Run each project

```powershell
# P1: generate data, build DuckDB marts, open the dashboard (:8501)
python -m fintech_lab.p1_payments.cli dashboard

# P2: mart -> backtest -> holdout -> budget v2 -> closing report; then the cockpit (:8503)
python -m fintech_lab.p1_payments.cli generate          # P2 reads the P1 dataset
python -m fintech_lab.p2_forecasting.cli pipeline
python -m fintech_lab.p2_forecasting.cli dashboard
python -m fintech_lab.p2_forecasting.cli audit          # independent recompute from raw P1

# P3: verify the locked protocol, generate 5 scenarios, run the locked analysis, dashboard (:8502)
python -m fintech_lab.p3_experiments.cli verify
python -m fintech_lab.p3_experiments.cli generate
python -m fintech_lab.p3_experiments.cli analyze
python -m fintech_lab.p3_experiments.cli dashboard
```

## Layout

```text
src/fintech_lab/      shared + per-project Python packages
projects/<nn-name>/   sql, app, configs, reports, docs, assets per project
shared/               design tokens (neutral placeholders) and the vendored axe-core used for a11y checks
tests/                unit and integration tests
data/                 generated data (not versioned)
docs/                 blueprint, decision log, audit reports
```

## License

MIT (code). Synthetic datasets are generated locally and are not real payment data.
Third-party components (including the vendored axe-core, MPL-2.0) are listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
