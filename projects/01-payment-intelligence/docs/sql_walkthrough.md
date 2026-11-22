# P1 · SQL walkthrough (P1.3)

Camada analítica em DuckDB sobre o Parquet sintético. Os resultados são `derived` de dados `synthetic`.

```powershell
python -m fintech_lab.p1_payments.cli build      # data/p1/p1.duckdb
python -m fintech_lab.p1_payments.cli check      # 14 checks de contrato + 5 de reconciliação
python -m fintech_lab.p1_payments.cli explain    # EXPLAIN ANALYZE -> reports/query_plans/
```

## Camadas
| Camada | Arquivo | Objetos | Grão |
|---|---|---|---|
| Staging | `sql/staging/01_staging.sql` | `stg_*` (views 1:1 sobre o Parquet, só tipagem) | igual à fonte |
| Core | `sql/marts/01_core.sql` | `dim_*`, `int_payment`, `fct_attempt`, `fct_payment` | pagamento / tentativa |
| Marts | `sql/marts/02_marts.sql` | `mart_auth_daily` | dia local × país × moeda × método |
| | | `mart_acquirer_performance` | mês × adquirente × método × faixa de valor |
| | | `mart_decline_reasons` | mês × país × método × código |
| | | `mart_retry_recovery` | país × método × categoria da 1ª falha × 1º adquirente |
| | | `mart_merchant_cohorts` | tipo de cohort × mês de ativação × meses desde o cohort |
| Checks | `sql/checks/contract.sql`, `reconciliation.sql` | blocos `-- name:` que retornam linhas violadoras | — |
| Análises | `sql/analyses/analyses.sql` | q01–q15 | por query |

Decisões que valem discutir em entrevista:
- **Anti double counting:** `fct_payment` agrega as tentativas por `payment_id` **antes** do join. A q15 mostra o erro do caminho ingênuo: no dataset padrão, somar `amount` depois de `payment ⋈ attempt` infla o TPV em 9,0% (BRL), 14,6% (MXN) e 16,2% (CLP), valores observados.
- **Dedup defensivo:** `int_payment` usa `QUALIFY ROW_NUMBER() … = 1`, então uma linha duplicada na fonte não se multiplica nos joins. O check c01 continua acusando a duplicata.
- **Fuso e FX:** a data local vem de `timezone(m.timezone, timezone('UTC', ts))`; o FX é o da data local de criação, também aplicado a custos e fees.
- **Taxas rolantes:** razão das somas rolantes, nunca média das razões; a q01 usa um calendário denso (date spine) para que o `LAG(…, 7)` seja de fato 7 dias.
- **Percentis** (M11) são calculados direto das tentativas, porque não dá para re-agregar percentis vindos de marts.

## Rastreabilidade métrica → query
| Métrica | Onde |
|---|---|
| M01 attempt auth rate | `mart_auth_daily`, `mart_acquirer_performance`; q01, q03, q04, q06 |
| M02 payment success rate | `mart_auth_daily`, `mart_merchant_cohorts`; q01, q03, q14 |
| M03 decline rate por categoria | `mart_acquirer_performance` (`declined_soft/hard ÷ attempts`) |
| M04 decline share | `mart_decline_reasons`; q05 |
| M05 retry recovery | `mart_retry_recovery`; q07 |
| M06 TPV local | `mart_auth_daily`; q02, q15; check r01 |
| M07 TPV BRL | `mart_auth_daily`, `mart_merchant_cohorts`; q02, q11 |
| M08 / M09 custo | `mart_*` (`m08_processing_cost_brl`); q07, q13 |
| M10 erro técnico | `mart_acquirer_performance`; q09 |
| M11 latência p50/p95 | `mart_acquirer_performance`; q10 |
| M12 tentativas por pagamento | q03 |
| M13 / M14 `[TO VERIFY]` | q13 (MDR sintético; não é receita real) |

## As 15 análises
| ID | Pergunta | Técnicas |
|---|---|---|
| q01 | Tendência diária de M01/M02 com janela de 7 dias e variação semanal | date spine, janela RANGE, LAG |
| q02 | TPV mensal por moeda, participação em BRL e crescimento MoM | CTE, janela por partição, LAG |
| q03 | Diferença M02 − M01 e M12 por país × método | agregação condicional |
| q04 | M01 por adquirente, bruto × ajustado pelo mix (padronização direta) | CTEs, janela sobre agregado, RANK |
| q05 | Top-5 códigos de falha por país e participação por categoria | janelas de participação, QUALIFY + ROW_NUMBER |
| q06 | M01 marginal por nº da tentativa, categoria anterior e troca de adquirente | LAG (em `fct_attempt`) |
| q07 | M05 e custo de retry por pagamento recuperado | CTEs, FILTER |
| q08 | Taxa de retry, intervalo até o retry e aprovação da próxima tentativa | LEAD, percentis |
| q09 | M10 no pico (19–22h local) × fora do pico, por adquirente | agregação condicional |
| q10 | Latência p50/p95 por adquirente × resultado | quantile_cont |
| q11 | Concentração de TPV por decil de merchant (Pareto) | NTILE, soma acumulada |
| q12 | Matriz de retenção de cohorts por mês de **ativação** (meses 0–6); `pre_window` = merchants já ativos antes da janela (censura à esquerda). Retenção ≈ 1 por construção (o gerador não tem churn): demonstra o SQL, não é achado | pivot com FILTER |
| q13 | M08, M09 e M13/M14 estimados `[TO VERIFY]` | join 1:1 no grão de pagamento |
| q14 | Dias anômalos de M02 (\|z\| ≥ 3 contra a janela anterior de 28 dias) | janela ROWS, STDDEV_SAMP |
| q15 | Demonstração de double counting: TPV via join × TPV correto | CTEs |

Limites de leitura: q04, q06 e q09 são **observacionais**. Roteamento e retry não são aleatorizados, então nada aqui mede efeito causal. Na q14 são ~1.095 testes (365 dias × 3 países), e alguns \|z\| ≥ 3 aparecem só por acaso; o resultado serve de triagem, não de prova. Como os padrões foram plantados pelo gerador, "encontrá-los" valida o pipeline, não o mercado.

## Testes de reconciliação (SQL)
| Check | Garante |
|---|---|
| r01_tpv_not_inflated | M06 do mart = Σ `amount` dos `succeeded` na fonte = `fct_payment`, por moeda (decimal exato) |
| r02_grain_preserved | `fct_payment` = nº de `payment_id` distintos; `fct_attempt` = nº de tentativas da fonte |
| r03_attempt_vs_payment | tentativas, aprovações e falhas batem entre fonte e marts; pagamentos `succeeded` = tentativas aprovadas |
| r04_settlement_vs_tpv | Σ `gross_amount` liquidado = TPV por moeda |
| r05_shares_and_funnel | as participações de M04 somam 1 por partição; o funil de M05 é monótono |

## Query plans (observados)
Arquivos em `reports/query_plans/`, gerados por `cli explain` em 2026-11-21. Ambiente: DuckDB 2.0.1, Python 3.12.10, Windows 11, Intel (20 núcleos lógicos, 20 threads), notebook pessoal, sem isolamento de carga. Dataset: 447.090 pagamentos e 500.000 tentativas.

| Query | Wall time (2ª execução) |
|---|---|
| q04_acquirer_mix_adjusted | 10,3 ms |
| q08_retry_timing | 68,4 ms |
| q11_merchant_concentration | 8,8 ms |

Os tempos são de uma única medição, sem repetição estatística, e não devem ser lidos como benchmark. Não houve otimização comparativa, então nenhum ganho de performance é reivindicado. No plano observado da q08, o operador `Window` (LEAD sobre as 500.000 tentativas) acumula 860 ms de tempo de operador, somado entre threads e por isso acima do wall time, contra 30 ms do `Hash Group By` com os percentis. O filtro `result != 'approved'` só entra depois da janela, porque o LEAD precisa da sequência completa. A q04 lê um mart já agregado e a q11 lê `fct_payment`.
