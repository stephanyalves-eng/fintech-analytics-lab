# P2 — Contratos de métricas

Convenções: valores em **BRL** (consolidação via `dim_fx_rate` do P1, FX da **data local de criação** do pagamento, igual ao M07 do P1). Data de referência = **data local de criação** do pagamento (accrual por transação). Moeda local só em tabelas marcadas.

## Métricas financeiras
| ID | Métrica | Grão | Numerador / fórmula | Denominador | Origem | Notas |
|---|---|---|---|---|---|---|
| F01 | TPV aprovado | pagamento → dia | Σ `amount × rate_to_brl` dos `final_status = succeeded` | — | derived (P1 M07) | Por pagamento; retries nunca somam. `failed` fora. Bruto: antes de refund/chargeback |
| F02 | Refunds | pagamento → dia | Σ valor reembolsado, na **data do refund** | — | synthetic | Reduz receita no dia do evento, não retroage o TPV |
| F03 | TPV líquido | dia | F01 − F02 | — | derived | Só para análise; F01 é o TPV oficial do forecast |
| F04 | Receita bruta (fees) | pagamento → dia | Σ `fee` do settlement convertido em BRL (FX da data de criação) | — | derived (P1 M13/M14) | Reconhecida na data de criação, não de settlement. `[TO VERIFY]` |
| F05 | Take rate | dia/mês/segmento | F04 | F01 do mesmo recorte | derived | Razão de somas, nunca média de razões diárias. `[TO VERIFY]` |
| F06 | Chargebacks | pagamento → dia | Σ perda de chargeback, na **data do chargeback** (atraso D+k após criação) | — | synthetic | Chargebacks de pagamentos de T4 podem cair depois do horizonte; relatório diz isso |
| F07 | Incentivos | dia | `incentive_rate × F01` | — | synthetic | Taxa em `configs/assumptions.yaml` |
| F08 | Net revenue | dia | F04 − F02b − F06 − F07 | — | derived | F02b = fee devolvida em refunds = `refund_fee_return_ratio × fee do pagamento original × (refund/amount)`. O principal devolvido (F02) afeta o TPV líquido, não a receita |
| F09 | Custo de processamento | tentativa → dia | Σ `processing_cost` (BRL) de **todas** as tentativas, na **data de criação local do pagamento** (regra de período do P1; R06 depende disso) | — | derived (P1 M08) | Inclui declinadas e retries |
| F10 | Outros custos variáveis | dia | `var_cost_rate × F01` | — | synthetic | Ex.: antifraude, suporte |
| F11 | Margem de contribuição | dia | F08 − F09 − F10 | — | derived | Não é lucro líquido; sem custos fixos |
| F12 | Margem de contribuição % | recorte | F11 | F08 | derived | Indefinida se F08 = 0 |

Regra de fee em refund: fração da fee devolvida ao merchant = `refund_fee_return_ratio` (padrão 1,0 = devolve toda a fee proporcional; ver assumptions).

## Métricas de erro e desvio
| ID | Métrica | Fórmula | Convenção |
|---|---|---|---|
| E01 | MAE | mean(\|actual − forecast\|) | Mesma unidade da série |
| E02 | RMSE | sqrt(mean((actual − forecast)²)) | — |
| E03 | WAPE | Σ\|actual − forecast\| / Σ\|actual\| | Indefinido se Σ\|actual\| = 0 (reportar `n/a`) |
| E04 | Bias | Σ(forecast − actual) / Σ actual | **Positivo = superprevisão**. Indefinido se Σ actual = 0 |
| E05 | Cobertura do intervalo | fração de pontos reais dentro do IC nominal (80% e 95%) | Reportar também a largura média |
| E06 | Variance vs. plano | `actual − plan` em R$ e `(actual − plan)/plan` | Positivo = acima do orçamento. % indefinido se plan = 0 |
| E07 | Variance vs. forecast | `actual − forecast` | Mesmo sinal de E06 |

MAPE **não** é usado (zeros em séries por merchant). Agregar erros por soma antes da razão ao comparar séries diferentes.

## Reconciliações (checks de contrato — todos devem passar)
| ID | Check | Tolerância |
|---|---|---|
| R01 | Σ F01 diário = Σ F01 mensal = F01 total do período | 0,00 (decimal) |
| R02 | Σ F01 por merchant = F01 consolidado, por dia | 0,00 |
| R03 | F01 do P2 = M07 do P1 (`mart` do P1) para o mesmo período e fuso | 0,00 |
| R04 | Nº de linhas de pagamento `succeeded` no P2 = P1; sem `payment_id` duplicado | exato |
| R05 | Σ F04 do P2 = Σ `fee` do settlement convertido, mesmas regras de FX | 0,00 |
| R06 | Σ F09 do P2 = M08 do P1 | 0,00 |
| R07 | Chave única (dia, merchant) na tabela diária; dias sem venda = 0 explícito após ativação | exato |
| R08 | Nenhuma feature com data > as-of no conjunto de treino do cut-off | exato (teste anti-leakage no P2.2) |
| R09 | F11 = F08 − F09 − F10 em toda linha | 0,00 |
| R10 | Orçamento v1 não muda após a data fixa (hash no manifest) | hash |

## Política de FX
Taxa sintética diária do P1 por moeda; data de referência = data local de criação. O forecast é feito **em BRL** sobre a série consolidada; não se prevê câmbio. Variação cambial entra como fator explicativo do desvio (P2.4), separada do efeito volume e do efeito take rate.
