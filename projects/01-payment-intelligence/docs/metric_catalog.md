# P1 · Metric catalog

Cada métrica tem grão, numerador e denominador explícitos. Todos os resultados são `derived` de dados `synthetic`.
Período padrão: data de **criação do pagamento** (`created_at_utc` convertido para a data local do merchant).

## Métricas
| ID | Métrica | Grão | Numerador | Denominador | Armadilhas |
|---|---|---|---|---|---|
| M01 | Attempt authorization rate | tentativa | nº tentativas `approved` | nº tentativas (todas, incl. `error`) | Diferente de M02: retries inflam o denominador |
| M02 | Final payment success rate | pagamento | nº pagamentos `succeeded` | nº pagamentos iniciados | Métrica principal de conversão |
| M03 | Decline rate (por categoria) | tentativa | nº tentativas `declined` da categoria (soft/hard) | nº tentativas | `error` fica fora do numerador (ver M10) |
| M04 | Decline share por código | tentativa | nº tentativas com o código X | nº tentativas `declined` + `error` | Soma 100% entre códigos |
| M05 | Retry recovery rate | pagamento | nº pagamentos `succeeded` com `attempt_no` final > 1 | nº pagamentos cuja 1ª tentativa falhou (soft ou technical) | Hard declines ficam fora do denominador, porque não se retentam |
| M06 | Approved TPV (moeda local) | pagamento | Σ `amount` dos pagamentos `succeeded` | — | Contar **por pagamento**, nunca somar tentativas; nunca somar moedas diferentes |
| M07 | Approved TPV consolidado (BRL) | pagamento | Σ `amount × rate_to_brl` (FX da data local de criação) dos `succeeded` | — | Valor `derived` que depende do FX sintético |
| M08 | Processing cost | tentativa | Σ `processing_cost` (convertido em BRL na consolidação) | — | Inclui o custo de tentativas recusadas e de retries |
| M09 | Cost per successful payment | pagamento | M08 (BRL) | nº pagamentos `succeeded` | Mede quanto os retries custam |
| M10 | Technical error rate | tentativa | nº tentativas `error` | nº tentativas | Responsabilidade do adquirente/PSP, não do emissor |
| M11 | Latency p50 / p95 | tentativa | percentil de `latency_ms` | — | Usar percentil, não média |
| M12 | Avg attempts per payment | pagamento | nº tentativas | nº pagamentos | — |
| M13 | Take rate (estimada) | pagamento | Σ `fee` (settlement, BRL) | M07 do mesmo período | `[TO VERIFY]`: depende dos parâmetros sintéticos de MDR; rotular como "estimada / sintética" |
| M14 | Net revenue (estimada) | — | Σ `fee` − M08 (BRL) | — | `[TO VERIFY]`: idem M13; não é receita real |

## Política de moedas
- Valores armazenados na moeda original (`BRL`, `MXN`, `CLP`). Cortes por país podem mostrar a moeda local.
- **Consolidação em BRL:** `amount × dim_fx_rate.rate_to_brl` na **data local de criação do pagamento**. Settlement e fees usam a mesma taxa do pagamento, para não criar variação cambial artificial.
- É proibido somar valores de moedas diferentes sem conversão (há teste de contrato para isso).
- O FX é `synthetic` e não representa cotações reais.

## Política de fuso horário
- Armazenamento em UTC. Cortes por **dia e hora usam a hora local do merchant** (`timezone`).
- Datas de período (dia/semana/mês) também em hora local do merchant.

## Dimensões de corte
merchant, setor, porte, país, método, adquirente, faixa de valor (em BRL: <50, 50–200, 200–1000, ≥1000), dia da semana, hora local,
dispositivo e código/categoria de recusa.

## Regras anti-ambiguidade
- "Taxa de aprovação" sem qualificador é proibida nos relatórios: usar sempre M01 (por tentativa) ou M02 (por pagamento).
- O denominador de M01 e de M03 inclui todas as tentativas. Quando um filtro (ex.: adquirente) muda o denominador, o relatório informa.
- O TPV de M06/M07 conta só pagamentos `succeeded`; pagamentos `failed` não entram, mesmo que tenham alguma tentativa com valor.
