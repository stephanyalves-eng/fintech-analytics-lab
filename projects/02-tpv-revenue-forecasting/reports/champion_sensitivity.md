# Champion rule: post-hoc sensitivity (informational; nothing frozen changes)

The frozen rule uses an approximate paired standard error. The same paired differences (validation only, never the holdout) are resampled by bootstrap (iid and circular blocks of 4 origins) to check whether each complex-vs-baseline decision is robust. `delta_point` < 0 means the complex model has the lower composite WAPE.

| target | complex | baseline | method | delta_point | se | ci95_lo | ci95_hi | p_delta_negative | complex_wins_by_rule | same_decision_as_frozen |
|---|---|---|---|---|---|---|---|---|---|---|
| contribution_total | sarima | ma7 | analytic (frozen rule) | 0.0334 | n/a | n/a | n/a | n/a | False | True |
| contribution_total | sarima | ma7 | bootstrap iid | 0.0334 | 0.0151 | 0.0058 | 0.0646 | 0.0080 | False | True |
| contribution_total | sarima | ma7 | bootstrap block=4 | 0.0334 | 0.0172 | 0.0001 | 0.0677 | 0.0240 | False | True |
| net_revenue_total | sarima | ma7 | analytic (frozen rule) | -0.0219 | 0.0033 | n/a | n/a | n/a | True | True |
| net_revenue_total | sarima | ma7 | bootstrap iid | -0.0219 | 0.0032 | -0.0281 | -0.0154 | 1.0000 | True | True |
| net_revenue_total | sarima | ma7 | bootstrap block=4 | -0.0219 | 0.0037 | -0.0292 | -0.0148 | 1.0000 | True | True |
| tpv_BR | sarima | ma7 | analytic (frozen rule) | -0.0289 | 0.0024 | n/a | n/a | n/a | True | True |
| tpv_BR | sarima | ma7 | bootstrap iid | -0.0289 | 0.0023 | -0.0336 | -0.0244 | 1.0000 | True | True |
| tpv_BR | sarima | ma7 | bootstrap block=4 | -0.0289 | 0.0023 | -0.0332 | -0.0243 | 1.0000 | True | True |
| tpv_CL | sarima | ma28 | analytic (frozen rule) | -0.0049 | 0.0026 | n/a | n/a | n/a | True | True |
| tpv_CL | sarima | ma28 | bootstrap iid | -0.0049 | 0.0025 | -0.0097 | 0.0001 | 0.9722 | True | True |
| tpv_CL | sarima | ma28 | bootstrap block=4 | -0.0049 | 0.0031 | -0.0111 | 0.0010 | 0.9446 | True | True |
| tpv_MX | sarima | ma7 | analytic (frozen rule) | -0.0205 | 0.0043 | n/a | n/a | n/a | True | True |
| tpv_MX | sarima | ma7 | bootstrap iid | -0.0205 | 0.0042 | -0.0294 | -0.0127 | 1.0000 | True | True |
| tpv_MX | sarima | ma7 | bootstrap block=4 | -0.0205 | 0.0039 | -0.0281 | -0.0129 | 1.0000 | True | True |
| tpv_total | sarima | snaive | analytic (frozen rule) | -0.0297 | 0.0026 | n/a | n/a | n/a | True | True |
| tpv_total | sarima | snaive | bootstrap iid | -0.0297 | 0.0025 | -0.0346 | -0.0245 | 1.0000 | True | True |
| tpv_total | sarima | snaive | bootstrap block=4 | -0.0297 | 0.0030 | -0.0349 | -0.0234 | 1.0000 | True | True |

Decisions that differ from the frozen ones: none.
