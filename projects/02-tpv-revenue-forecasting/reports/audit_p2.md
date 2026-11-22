# P2 independent audit

Recomputed from the raw P1 Parquet with plain pandas (no DuckDB/SQL of P2). Findings are reported, not fixed.

| check | result | detail |
|---|---|---|
| A1a TPV: raw pandas vs mart (year) | PASS | mart 76,079,714.40 vs raw 76,079,713.77 |
| A1b fee: raw pandas vs mart (year) | PASS | mart 1,614,300.48 vs raw 1,614,300.49 |
| A1c processing cost: raw vs mart (year) | PASS | mart 1,137,829.41 vs raw 1,137,829.39 |
| A1d TPV T4: raw vs mart | PASS | raw 28,142,908.92 |
| A1e TPV by country: raw vs mart | PASS | BR 48,113,885, CL 12,868,174, MX 15,097,655 |
| A2a budget v1 base level = raw January mean daily TPV (cent-rounding bound) | PASS | {'BR': 81148.92, 'CL': 26588.55, 'MX': 27301.69} |
| A2b budget v1 take rate = raw January fee/TPV (4 d.p.) | PASS |  |
| A3a budget v2 growth = raw Apr->Sep compound monthly growth | PASS | {'BR': 0.0738, 'CL': 0.026, 'MX': 0.0801} |
| A3b budget v2 uses only data <= as-of | PASS |  |
| A4a backtest never evaluates dates after as-of | PASS | max date 2025-09-30 00:00:00 |
| A4b backtest origins <= last configured origin and < as-of | PASS |  |
| A4c champions are explained by the validation composite WAPE (recomputed) | PASS |  |
| A4d holdout WAPE of champions recomputed from daily rows | PASS |  |
| A4e holdout actual TPV = raw T4 TPV | PASS | 28,142,909 |
| A5a no table is labelled 'observed' | PASS | ['derived', 'synthetic'] |
| A5b mart checks recorded as passing | PASS | 9 checks |
| A5c daily total has no gaps and no negative TPV | PASS | 365 days |

**17/17 passed.**
