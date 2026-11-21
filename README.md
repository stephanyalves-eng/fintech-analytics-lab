# Fintech Analytics Lab

Portfolio of three fintech analytics projects built on **synthetic, explicitly labeled data**, local-first and reproducible.

| # | Project | Focus | Status |
|---|---|---|---|
| 01 | [Payment Intelligence & Transaction Optimization](projects/01-payment-intelligence/README.md) | Authorization rate, declines, retries, routing scenarios, advanced SQL | MVP done, audited (CI not yet run) |
| 02 | Fintech Revenue & TPV Forecasting Engine | TPV/revenue forecasting, backtesting, variance bridge | Planned |
| 03 | Fintech Experimentation & A/B Testing Lab | Preregistered protocol, SRM, power, guardrails, decision | Planned |

> No results are reported until they are produced by executed, tested code.

## Setup (Windows)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt   # pinned versions used for committed outputs
python -m pip install -e . --no-deps
ruff check .
pytest -q
```

## Layout

```text
src/fintech_lab/      shared + per-project Python packages
projects/<nn-name>/   sql, app, configs, reports, docs, assets per project
tests/                unit and integration tests
data/                 generated data (not versioned)
docs/                 blueprint, decision log
```

## License

MIT (code). Synthetic datasets are generated locally and are not real payment data.
