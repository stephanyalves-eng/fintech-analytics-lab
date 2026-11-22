# P2.3 holdout T4/2025 (champions frozen before this run)

Errors are (forecast or budget - actual) / actual on the 92-day total. Not used for any model choice.

| target | champion | actual_t4 | forecast_t4 | budget_t4 | forecast_err_pct | budget_err_pct | wape_daily | bias | cov80 | cov95 | wape_h7 | wape_h30 | wape_h90 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tpv_total | sarima | 28,142,909 | 22,294,593 | 18,399,499 | -20.8% | -34.6% | 21.7% | -20.8% | 19.6% | 29.3% | 7.4% | 6.4% | 21.6% |
| net_revenue_total | sarima | 532,028 | 430,972 | 375,585 | -19.0% | -29.4% | 22.4% | -19.0% | 40.2% | 58.7% | 11.7% | 11.9% | 22.3% |
| contribution_total | ma7 | 88,336 | 66,064 | 292,787 | -25.2% | 231.4% | 51.0% | -25.2% | 62.0% | 81.5% | 33.6% | 44.8% | 51.1% |
| tpv_BR | sarima | 18,276,321 | 14,341,694 | 11,056,790 | -21.5% | -39.5% | 23.3% | -21.5% | 19.6% | 35.9% | 8.4% | 8.4% | 23.1% |
| tpv_MX | sarima | 5,459,144 | 4,556,636 | 3,719,938 | -16.5% | -31.9% | 18.9% | -16.5% | 50.0% | 60.9% | 6.6% | 10.2% | 18.9% |
| tpv_CL | sarima | 4,407,444 | 3,496,505 | 3,622,772 | -20.7% | -17.8% | 22.8% | -20.7% | 42.4% | 60.9% | 11.4% | 12.4% | 23.0% |
