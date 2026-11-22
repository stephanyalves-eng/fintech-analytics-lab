# P2.3 — Métodos, resultados e limites

Todos os números abaixo vêm de `reports/backtest_summary.md`, `reports/backtest_metrics.csv` e `reports/holdout_t4.md`, gerados por `python -m fintech_lab.p2_forecasting.cli backtest --freeze` e `... holdout`. Dados: sintéticos (P1) + refund/chargeback sintéticos; nada aqui é desempenho real.

## Protocolo (fixado em `configs/backtest.yaml` antes da execução)
- **Alvos (6):** TPV, net revenue e margem de contribuição consolidados; TPV por país (BR, MX, CL). Diário, BRL.
- **Modelos:** naive, seasonal naive (7 d), média móvel 7 e 28 d, ETS (aditivo, tendência amortecida, sazonalidade 7) e SARIMA (grade de 3 ordens por AIC, sazonal (0,1,1,7)). Sem aleatoriedade; mesma entrada ⇒ mesma saída.
- **Backtest:** rolling-origin, 26 origens semanais (2025-04-01 a 2025-09-23), janela expansiva; cada modelo só vê `y ≤ origem`; os reais são lidos truncados em 2025-09-30. Horizontes 7/30/90 d, só janelas completas dentro do as-of (26, 22 e 14 origens).
- **Métricas:** WAPE e Bias agrupados por origens × dias; MAE, RMSE, cobertura 80/95%, largura, WAPE entre origens (estabilidade), erro do total da janela, segundos por fit. Sem MAPE.
- **Intervalos:** ETS/SARIMA pelo modelo; baselines por quantis dos erros k-passos dentro da amostra (≥ 20 resíduos, senão `n/a`).
- **Seleção (só validação):** composite = média do WAPE em 7/30/90 d (pesos iguais). Um modelo complexo só vira campeão se superar o melhor baseline por mais de 1 erro-padrão pareado (aproximação: horizontes tratados como independentes); caso contrário fica o baseline. Campeões congelados em `configs/champions_b1.yaml` (hash da config e dos dados; não sobrescreve).
- **Holdout T4:** executado uma vez depois do congelamento; falha se a config mudou. Não alimenta nenhuma escolha.

## Resultado da validação (WAPE composite, menor é melhor)
| Alvo | Campeão | Composite | Melhor baseline |
|---|---|---|---|
| tpv_total | SARIMA | 6,2% | snaive 9,1% |
| tpv_BR | SARIMA | 8,3% | ma7 11,2% |
| tpv_MX | SARIMA | 13,4% | ma7 15,5% |
| tpv_CL | SARIMA | 15,2% | ma28 15,7% |
| net_revenue_total | SARIMA | 11,2% | ma7 13,5% |
| contribution_total | ma7 (baseline) | 42,0% | ma7 |

Margem de contribuição é ruidosa (chargebacks e custos sintéticos), e nenhum modelo complexo superou o ma7 com margem suficiente. Cobertura de TPV total no SARIMA: 77–80% (nominal 80%) e 93–94% (nominal 95%).

## Holdout T4/2025 (92 dias, uma execução)
| Alvo | Campeão | Erro do total (previsão) | Erro do total (orçamento v1) | WAPE diário | Cobertura 80% |
|---|---|---|---|---|---|
| tpv_total | SARIMA | −20,8% | −34,6% | 21,7% | 19,6% |
| net_revenue_total | SARIMA | −19,0% | −29,4% | 22,4% | 40,2% |
| contribution_total | ma7 | −25,2% | +231,4% | 51,0% | 62,0% |
| tpv_BR | SARIMA | −21,5% | −39,5% | 23,3% | 19,6% |
| tpv_MX | SARIMA | −16,5% | −31,9% | 18,9% | 50,0% |
| tpv_CL | SARIMA | −20,7% | −17,8% | 22,8% | 42,4% |

## Como ler isto
1. **Todos os seis modelos subestimam T4** (−10% a −39% no total, por alvo); o campeão errou por −21% no TPV, melhor que o orçamento (−35%). A validação (WAPE 6%) não antecipa esse erro: o histórico até setembro não contém o salto de novembro/dezembro, e um modelo não aprende o que nunca viu. A causa mecânica (sazonalidade mensal e picos no gerador do P1) está no código do gerador, mas a atribuição quantitativa fica para o P2.4.
2. **Intervalos curtos fora do padrão:** a cobertura de 80% cai para ~20% no TPV total no T4. Os intervalos medem só o ruído visto na amostra, não mudança de regime.
3. **Erro de curto prazo continua razoável:** WAPE do campeão em TPV total nos primeiros 7 e 30 dias de T4 foi 7,4% e 6,4%; o erro explode nos meses seguintes.
4. A margem do orçamento (+231%) mostra um orçamento muito acima do realizado; a decomposição (volume, take rate, custo, refund/chargeback) é o P2.4.
5. Limites: um ano de histórico; ETS/SARIMA com 273 dias de treino; teste de significância pareado aproximado; só um holdout (um trimestre), então a comparação com o orçamento é um caso, não uma estatística.

## Orçamento v2 (reforecast no cut-off)
Regras em `configs/budget_v2_rules.yaml`; números calculados só com dados ≤ 2025-09-30 e congelados em `configs/budget_v2.yaml` (hash, não sobrescreve): nível = TPV de setembro por dia e país; crescimento composto abril→setembro por país; take rate, refund+chargeback/fee e processamento/TPV dos últimos 90 dias. Erro do TPV de T4: v1 −34,6%, v2 −17,1%; da margem: v1 +231,4%, v2 −10,1% ((plano − realizado)/realizado). As regras do v2 foram escolhidas depois de o v1 ter falhado no T4 (os números usam só dados ≤ 30/09, a escolha das regras não foi cega). O v2 é uma projeção de ritmo e, como os demais modelos, não vê a sazonalidade de novembro/dezembro.

## Sensibilidade pós-hoc da regra do campeão (L8)
A regra congelada usa um erro-padrão pareado aproximado (horizontes e origens tratados como independentes). `cli sensitivity` (`reports/champion_sensitivity.{csv,md}`) reamostra as mesmas diferenças pareadas por bootstrap (iid e blocos circulares de 4 origens), **só com dados de validação** e sem alterar nada congelado. Resultado: as **18 linhas** (6 alvos × 3 métodos) mantêm a decisão congelada. Em 4 alvos (net revenue, TPV BR, TPV MX, TPV total) o SARIMA vence com folga (intervalo de 95% inteiramente abaixo de zero). Em `tpv_CL` a vantagem é frágil: ΔWAPE composto −0,49 p.p., intervalo de 95% de −0,97 a +0,01 p.p. (iid) e −1,11 a +0,10 p.p. (blocos), isto é, **inclui zero**; o SARIMA segue campeão pela regra, mas a evidência é fraca. Em `contribution_total` o SARIMA é pior que a média móvel de 7 dias nos três métodos. A regra do congelamento não foi mudada: alterá-la depois de ver o holdout seria ajuste pós-hoc.
