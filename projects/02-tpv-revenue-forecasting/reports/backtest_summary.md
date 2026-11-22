# P2.3 backtest (validation only, origins up to as-of 2025-09-30)

WAPE pooled over origins and days; full windows only. `composite` = mean of horizons.

| target | model | 7 | 30 | 90 | composite |
|---|---|---|---|---|---|
| contribution_total | ets | 44.7% | 47.5% | 50.8% | 47.7% |
| contribution_total | ma28 | 39.9% | 42.4% | 44.5% | 42.3% |
| contribution_total | ma7 | 38.5% | 41.7% | 45.8% | 42.0% |
| contribution_total | naive | 43.9% | 44.0% | 44.2% | 44.1% |
| contribution_total | sarima | 41.5% | 44.5% | 48.9% | 45.0% |
| contribution_total | snaive | 51.5% | 50.1% | 50.9% | 50.8% |
| net_revenue_total | ets | 10.9% | 12.9% | 16.2% | 13.4% |
| net_revenue_total | ma28 | 12.5% | 13.8% | 16.4% | 14.2% |
| net_revenue_total | ma7 | 11.9% | 13.1% | 15.5% | 13.5% |
| net_revenue_total | naive | 14.3% | 15.1% | 17.2% | 15.6% |
| net_revenue_total | sarima | 10.4% | 11.4% | 11.9% | 11.2% |
| net_revenue_total | snaive | 13.3% | 13.8% | 15.8% | 14.3% |
| tpv_BR | ets | 8.5% | 9.3% | 11.7% | 9.9% |
| tpv_BR | ma28 | 10.0% | 10.6% | 13.6% | 11.4% |
| tpv_BR | ma7 | 10.2% | 10.3% | 13.0% | 11.2% |
| tpv_BR | naive | 12.0% | 12.4% | 16.6% | 13.7% |
| tpv_BR | sarima | 8.2% | 8.3% | 8.3% | 8.3% |
| tpv_BR | snaive | 10.9% | 11.2% | 13.4% | 11.8% |
| tpv_CL | ets | 14.6% | 15.3% | 16.9% | 15.6% |
| tpv_CL | ma28 | 15.2% | 15.5% | 16.4% | 15.7% |
| tpv_CL | ma7 | 15.6% | 15.9% | 16.5% | 16.0% |
| tpv_CL | naive | 19.7% | 20.8% | 22.4% | 21.0% |
| tpv_CL | sarima | 14.4% | 15.0% | 16.2% | 15.2% |
| tpv_CL | snaive | 19.9% | 20.4% | 21.5% | 20.6% |
| tpv_MX | ets | 13.1% | 14.0% | 17.3% | 14.8% |
| tpv_MX | ma28 | 14.2% | 14.7% | 17.9% | 15.6% |
| tpv_MX | ma7 | 14.3% | 14.9% | 17.2% | 15.5% |
| tpv_MX | naive | 21.1% | 20.8% | 23.8% | 21.9% |
| tpv_MX | sarima | 12.9% | 13.1% | 14.1% | 13.4% |
| tpv_MX | snaive | 17.5% | 17.6% | 20.3% | 18.4% |
| tpv_total | ets | 6.1% | 6.5% | 8.0% | 6.9% |
| tpv_total | ma28 | 8.4% | 9.1% | 12.5% | 10.0% |
| tpv_total | ma7 | 8.1% | 8.6% | 11.3% | 9.3% |
| tpv_total | naive | 10.0% | 10.7% | 14.5% | 11.7% |
| tpv_total | sarima | 5.9% | 6.1% | 6.4% | 6.2% |
| tpv_total | snaive | 7.7% | 8.5% | 11.2% | 9.1% |

## Champions

| target | champion | reason | composite_wape | best_baseline | composite_best_baseline | best_complex | composite_best_complex | paired_delta_complex_minus_baseline | paired_se |
|---|---|---|---|---|---|---|---|---|---|
| contribution_total | ma7 | best baseline | 0.4201 | ma7 | 0.4201 | sarima | 0.4499 | n/a | n/a |
| net_revenue_total | sarima | beats best baseline by more than 1 paired SE | 0.1123 | ma7 | 0.1350 | sarima | 0.1123 | -0.0219 | 0.0033 |
| tpv_BR | sarima | beats best baseline by more than 1 paired SE | 0.0825 | ma7 | 0.1117 | sarima | 0.0825 | -0.0289 | 0.0024 |
| tpv_CL | sarima | beats best baseline by more than 1 paired SE | 0.1520 | ma28 | 0.1570 | sarima | 0.1520 | -0.0049 | 0.0026 |
| tpv_MX | sarima | beats best baseline by more than 1 paired SE | 0.1340 | ma7 | 0.1548 | sarima | 0.1340 | -0.0205 | 0.0043 |
| tpv_total | sarima | beats best baseline by more than 1 paired SE | 0.0615 | snaive | 0.0912 | sarima | 0.0615 | -0.0297 | 0.0026 |
