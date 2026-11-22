# P2 — Dicionário de dados e dependências

Rótulos: `observed` (nenhum no P2), `synthetic`, `derived`.

## Entradas (P1, `data/p1/default`, somente leitura)
| Tabela | Campos usados | Rótulo | Uso |
|---|---|---|---|
| `fact_payment` | `payment_id`, `merchant_id`, `method_code`, `created_at_utc`, `amount`, `currency`, `final_status` | synthetic | TPV (F01), contagem de pagamentos |
| `fact_attempt` | `attempted_at_utc`, `processing_cost`, `result` | synthetic | F09 |
| `fact_settlement` | `payment_id`, `fee`, `settlement_date` | synthetic | F04 (fee); data de settlement só informativa |
| `dim_merchant` | `country`, `sector`, `size_tier`, `timezone`, `activation_date` | synthetic | Segmentos, fuso, dias elegíveis |
| `dim_fx_rate` | taxa diária por moeda | synthetic | Conversão para BRL |
| `manifest.json` | `seed`, hash | — | Rastreabilidade (versão dos dados) |

## Tabelas do P2 (exportadas em `data/p2/`)
| Tabela | Grão / chave | Campos principais | Rótulo |
|---|---|---|---|
| `fct_daily_merchant` | (`date_local`, `merchant_id`) | `tpv_brl`, `n_payments`, `fee_brl`, `proc_cost_brl`, `refund_brl`, `chargeback_brl`, `incentive_brl`, `var_cost_brl`, `net_revenue_brl`, `contribution_brl` | derived (+ synthetic) |
| `fct_daily_segment` | (`date_local`, `country`, `method_code`, `size_tier`) | idem, agregado | derived |
| `fct_daily_total` | (`date_local`) | idem, agregado; `take_rate` | derived |
| `fct_monthly` | (`month`, país) | idem | derived |
| `dim_calendar` | `date_local` | dia da semana, feriado (país), flags de fim de mês/início de mês, dia útil | derived |
| `syn_adjustment` | (`payment_id`, `event_type`) | `merchant_id`, `method_code`, `event_date_local`, `amount_brl`, `fee_returned_brl`, `chargeback_fee_brl` (refund XOR chargeback por pagamento) | synthetic |
| `budget_v1` | (`month`, `country`) | `tpv_brl`, `take_rate`, `fee_brl`, `net_revenue_brl`, `contribution_brl`, `version`, `as_of`; parâmetros e hash em `configs/budget_v1.yaml` | synthetic |
| `budget_v2` | (`month`, `country`) | `tpv_brl`, `take_rate`, `fee_brl`, `rc_brl`, `inc_brl`, `proc_brl`, `var_brl`, `net_revenue_brl`, `contribution_brl`, `version`, `as_of`; parâmetros e hash em `configs/budget_v2.yaml` | synthetic |
| `backtest/fct_backtest_forecast` | (`target`, `model`, `origin`, `step`) | `date`, `actual`, `yhat`, `lo80`, `hi80`, `lo95`, `hi95` (só datas ≤ as-of) | derived |
| `backtest/fct_backtest_metrics` | (`target`, `model`, `horizon`) | `n_origins`, `mae`, `rmse`, `wape`, `bias`, `wape_sd_origins`, `window_sum_ape`, `cov80`, `cov95`, `width80`, `width95`, `sec_per_fit`, `n_failed_fits` | derived |
| `backtest/fct_holdout_forecast` | (`target`, `model`, `step`) | previsão T4 de todos os modelos a partir do as-of; **não** usada para selecionar modelo | derived |
| `backtest/fit_log` | (`target`, `model`, `origin`) | `seconds`, `failed`, `error`, `info` | derived |

Premissas ficam em YAML versionado (`configs/assumptions.yaml`, `scenarios.yaml`, `alerts.yaml`, `backtest.yaml`), não em tabela. Feriados e eventos são colunas de `dim_calendar` (não há tabelas `ref_holiday`/`ref_events`).

## Regras de disponibilidade (anti-leakage)
- Data `t` com origem `o` só usa dados com `date ≤ o`. Lags e médias móveis em dia `d` usam `d−k` com `k ≥ horizonte`, para previsão direta; para previsão recursiva, só o histórico até `o`.
- Calendário (feriados, dia da semana) é conhecido com antecedência e pode ser usado no futuro. Eventos (Black Friday/Cyber Monday) entram em `dim_calendar` por regra, conhecidos antes da origem.
- Refunds e chargebacks de pagamentos até `o` que ocorrem depois de `o` **não** estão visíveis na origem `o` (usar data do evento).
- `activation_date` é conhecido; merchants futuros não entram na previsão de merchant.
- O orçamento v1 é conhecido em qualquer origem (as-of 2024-12-31).

## Dependências e sazonalidade
| Fator | Disponível? | Tratamento |
|---|---|---|
| Dia da semana | sim, do P1 (curva de demanda) | sazonalidade semanal (período 7) |
| Mês/ano | só 1 ciclo | sem sazonalidade anual; mês como feature só em ablação, com aviso |
| Feriados BR/MX/CL | externos | regras em `calendar.py`; colunas `holiday_*` de `dim_calendar` |
| Entrada de merchants | `activation_date` | regressor de "merchants ativos"; tendência decomposta no P2.4 |
| FX | série diária sintética | só como driver de desvio, não prevista |

## Grão e denominadores
- TPV, receita, custo: soma por dia no fuso local do merchant.
- Take rate e margem %: razão de somas no recorte (nunca média de razões).
- Dia sem venda de merchant ativo = 0 explícito; dia antes da ativação = ausente (não zero), para não penalizar o WAPE.

## Implementação (P2.2)
- Código: `src/fintech_lab/p2_forecasting/` (`mart.py`, `adjustments.py`, `calendar.py`, `budget.py`, `features.py`, `cli.py`); SQL em `sql/mart.sql` e `sql/checks.sql`.
- Comando: `python -m fintech_lab.p2_forecasting.cli build` (mart + checks R01–R09 + R10 do orçamento + export em `data/p2/`, não versionado). O build recusa exportar se algum check falhar.
- Arredondamento só no grão (dia × merchant × método), `DECIMAL(18,4)`; níveis superiores só somam, por isso as reconciliações são exatas.
- Eventos de refund/chargeback fora da janela (depois de 2025-12-31) ficam em `syn_adjustment` e são contados no manifest, mas não entram no mart.
- Feriados: conjunto curado por regra (datas fixas, Páscoa, n-ésima segunda); **não é calendário oficial completo** `[TO VERIFY]`. O gerador do P1 não modela feriados, então efeito de feriado deve dar ≈ 0.
- Black Friday/Cyber Monday entram no calendário por regra (4ª sexta de novembro e +3 dias), conhecidos antes da origem.
- Tabelas de previsão e backtest: ver `data/p2/backtest/` (P2.3).
