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

## Tabelas do P2 (a criar no P2.2)
| Tabela | Grão / chave | Campos principais | Rótulo |
|---|---|---|---|
| `fct_daily_merchant` | (`date_local`, `merchant_id`) | `tpv_brl`, `n_payments`, `fee_brl`, `proc_cost_brl`, `refund_brl`, `chargeback_brl`, `incentive_brl`, `var_cost_brl`, `net_revenue_brl`, `contribution_brl` | derived (+ synthetic) |
| `fct_daily_segment` | (`date_local`, `country`, `method_code`, `size_tier`) | idem, agregado | derived |
| `fct_daily_total` | (`date_local`) | idem, agregado; `take_rate` | derived |
| `fct_monthly` | (`month`, país) | idem | derived |
| `dim_calendar` | `date_local` | dia da semana, feriado (país), flags de fim de mês/início de mês, dia útil | derived |
| `ref_holiday` | (`country`, `date`) | nome, fonte | **fonte documentada obrigatória** (biblioteca/tabela pública); sem fonte, não entra |
| `budget_v1` | (`month`, `country`) | `tpv_brl`, `take_rate`, `net_revenue`, `contribution`; `version`, `as_of`, `created_at`, `hash` | synthetic |
| `assumptions_vN` | parâmetro | valor, `version`, `as_of` | synthetic |
| `fct_forecast` | (`model`, `origin`, `date`, `horizon`, `metric`) | `yhat`, `lo80`, `hi80`, `lo95`, `hi95`, `config_hash` | derived |
| `fct_backtest_metrics` | (`model`, `origin`, `horizon`, `metric`) | MAE, RMSE, WAPE, Bias, cobertura, runtime | derived |

## Regras de disponibilidade (anti-leakage)
- Data `t` com origem `o` só usa dados com `date ≤ o`. Lags e médias móveis em dia `d` usam `d−k` com `k ≥ horizonte`, para previsão direta; para previsão recursiva, só o histórico até `o`.
- Calendário (feriados, dia da semana) é conhecido com antecedência e pode ser usado no futuro. Eventos sintéticos só se declarados no `ref_events` **antes** da origem.
- Refunds e chargebacks de pagamentos até `o` que ocorrem depois de `o` **não** estão visíveis na origem `o` (usar data do evento).
- `activation_date` é conhecido; merchants futuros não entram na previsão de merchant.
- O orçamento v1 é conhecido em qualquer origem (as-of 2024-12-31).

## Dependências e sazonalidade
| Fator | Disponível? | Tratamento |
|---|---|---|
| Dia da semana | sim, do P1 (curva de demanda) | sazonalidade semanal (período 7) |
| Mês/ano | só 1 ciclo | sem sazonalidade anual; mês como feature só em ablação, com aviso |
| Feriados BR/MX/CL | externos | fonte documentada; ver `ref_holiday` |
| Entrada de merchants | `activation_date` | regressor de "merchants ativos"; tendência decomposta no P2.4 |
| FX | série diária sintética | só como driver de desvio, não prevista |

## Grão e denominadores
- TPV, receita, custo: soma por dia no fuso local do merchant.
- Take rate e margem %: razão de somas no recorte (nunca média de razões).
- Dia sem venda de merchant ativo = 0 explícito; dia antes da ativação = ausente (não zero), para não penalizar o WAPE.
