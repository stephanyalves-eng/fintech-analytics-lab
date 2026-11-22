# P2 — TPV, receita e margem: problema e escopo

## Pergunta executiva
Qual será o fechamento de TPV, net revenue e margem de contribuição do trimestre, com que incerteza, e quais fatores explicam o desvio em relação ao orçamento?

## Fonte e rótulos
- Fonte primária: pagamentos sintéticos do P1 (`data/p1/default`, seed 20261121). Rótulo: `synthetic`.
- Valores calculados a partir deles (TPV em BRL, take rate, margem): `derived`.
- Refund, chargeback, incentivos, custo variável adicional e orçamento: `synthetic` (criados no P2, parâmetros em `configs/`).
- Nada aqui é `observed`. Todo número de receita e margem é estimado e carrega `[TO VERIFY]` até haver dado real.
- Olist: **fora do MVP** (decisão D1). Se entrar depois, só para sazonalidade de e-commerce, sem afirmar TPV de PSP.

## Datas-chave
| Item | Valor |
|---|---|
| Histórico disponível | 2025-01-01 a 2025-12-31 (jan/2026 tem 422 pagamentos por fuso; excluído) |
| **Data de previsão (as-of / cut-off)** | **2025-09-30** (fim do dia, fuso do merchant) |
| Treino/histórico visível ao modelo | 2025-01-01 a 2025-09-30 (273 dias) |
| Horizonte de referência | 2025-10-01 a 2025-12-31 (92 dias, T4/2025) |
| Horizontes de backtest | 7, 30 e 90 dias |
| Versão do orçamento (as-of) | 2024-12-31 (v1), fixa |

O realizado de T4 só é lido para avaliação e para a análise de desvio (P2.4). Nenhum atributo com data > cut-off entra no forecast.

## Limites de interpretação
1. **Um ano de histórico**: sazonalidade semanal é estimável; anual não. Dezembro e as datas de varejo aparecem uma vez. Nenhum modelo pode afirmar sazonalidade anual.
2. **Tendência ≠ crescimento orgânico**: parte do crescimento vem da entrada de merchants (`activation_date`). O consolidado mistura os dois efeitos; a decomposição fica para o P2.4.
3. **T4 é um holdout difícil**: o volume mensal de pagamentos no P1 sobe de 45.066 (out) para 58.413 (nov) e 65.104 (dez). Um modelo treinado só até set pode subestimar T4. Isso é um fato dos dados, não um resultado de modelo; o tamanho do erro só será conhecido após o P2.3.
4. **Séries por merchant são intermitentes** (zeros, dias antes da ativação): usar WAPE/MAE somados, nunca MAPE.
5. Não é lucro líquido, não é receita contábil auditada, não é previsão para produção.

## Públicos e decisões
| Público | Decisão que a previsão apoia | Saída |
|---|---|---|
| FP&A | Revisar a projeção do trimestre vs. orçamento | TPV, net revenue, margem com intervalo; desvio R$ e % |
| Comercial | Priorizar merchants/segmentos com maior desvio | Desvio por país, método e tier |
| Operações | Antecipar carga e custo de processamento | TPV e custo por dia/semana; picos |

## Fora de escopo
Previsão por transação, risco de crédito, câmbio real, IFRS 15, settlement/caixa (só mencionado como visão alternativa), churn de merchants (herdado do P1: retenção ≈ 1).
