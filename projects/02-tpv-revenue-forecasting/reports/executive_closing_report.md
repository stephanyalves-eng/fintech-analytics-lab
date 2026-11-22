# P2 — Relatório executivo de fechamento T4/2025

> Dados 100% sintéticos (P1 + refund/chargeback/orçamento sintéticos). Receita e margem são estimativas `[TO VERIFY]`. Todos os números abaixo foram calculados por `python -m fintech_lab.p2_forecasting.cli close`; o texto só descreve esses valores. Nenhuma afirmação causal.

## 1. Resultado do trimestre (01/10–31/12/2025, BRL)
O TPV realizado foi 28,142,909: +53.0% em relação ao orçamento v1 (18,399,499) e +25.7% em relação à previsão composta feita em 2025-09-30 (22,394,835). A margem de contribuição realizada foi 88,336, contra 292,787 orçados (-69.8%) e 76,070 previstos.

| metric | budget | forecast_composed | forecast_direct_champion | actual | actual_vs_budget | actual_vs_budget_pct | forecast_err_pct | budget_err_pct | actual_vs_forecast_pct |
|---|---|---|---|---|---|---|---|---|---|
| TPV | 18,399,499 | 22,394,835 | 22,294,593 | 28,142,909 | 9,743,410 | 53.0% | -20.4% | -34.6% | 25.7% |
| Net revenue | 375,585 | 434,192 | 430,972 | 532,028 | 156,443 | 41.7% | -18.4% | -29.4% | 22.5% |
| Contribution margin | 292,787 | 76,070 | 66,064 | 88,336 | -204,452 | -69.8% | -13.9% | 231.4% | 16.1% |

*Previsão composta* = previsão do campeão de TPV por país × razões dos últimos 90 dias até o as-of (take rate, refund+chargeback/fee, custos/TPV). *Previsão direta* = campeão de cada alvo (P2.3). As duas diferem por construção; a ponte e os cenários usam a composta.

## 2. O que o as-of de 30/09 já sinalizava (alertas ex-ante)
8 alertas vermelhos e 2 amarelos, com limites em `configs/alerts.yaml` (números redondos escolhidos depois de o holdout do P2.3 ter sido visto; não ajustados ao resultado).

| alert | scope | value | amber | red | severity | evidence |
|---|---|---|---|---|---|---|
| forecast_vs_budget | TPV | 21.7% | 10.0% | 20.0% | red | forecast 22,394,835 vs budget 18,399,499 |
| forecast_vs_budget | Net revenue | 15.6% | 10.0% | 20.0% | amber | forecast 434,192 vs budget 375,585 |
| forecast_vs_budget | Contribution margin | -74.0% | 10.0% | 20.0% | red | forecast 76,070 vs budget 292,787 |
| forecast_vs_budget | TPV BR | 29.7% | 10.0% | 20.0% | red | forecast 14,341,694 vs budget 11,056,790 |
| forecast_vs_budget | TPV MX | 22.5% | 10.0% | 20.0% | red | forecast 4,556,636 vs budget 3,719,938 |
| ytd_run_rate_gap | TPV Jan-Sep | 10.5% | 10.0% | 20.0% | amber | actual 47,936,806 vs budget 43,379,513 |
| model_reliability | Contribution margin | 42.0% | 15.0% | 30.0% | red | champion ma7, validation composite WAPE |
| refund_cb_share_drift | BR | 229.7% | 25.0% | 50.0% | red | last-90d refund+cb/fee 0.0659 vs budget 0.0200 |
| refund_cb_share_drift | CL | 257.9% | 25.0% | 50.0% | red | last-90d refund+cb/fee 0.0716 vs budget 0.0200 |
| refund_cb_share_drift | MX | 270.4% | 25.0% | 50.0% | red | last-90d refund+cb/fee 0.0741 vs budget 0.0200 |

Alertas ex-post (realizado vs orçamento):

| alert | scope | value | amber | red | severity | evidence |
|---|---|---|---|---|---|---|
| actual_vs_budget | TPV | 53.0% | 10.0% | 20.0% | red | actual 28,142,909 vs budget 18,399,499 |
| actual_vs_budget | Net revenue | 41.7% | 10.0% | 20.0% | red | actual 532,028 vs budget 375,585 |
| actual_vs_budget | Contribution margin | -69.8% | 10.0% | 20.0% | red | actual 88,336 vs budget 292,787 |
| take_rate_drift | BR | -1.1% | 10.0% | 20.0% | ok | T4 take 0.0188 vs budget 0.0190 |
| take_rate_drift | CL | 3.0% | 10.0% | 20.0% | ok | T4 take 0.0246 vs budget 0.0239 |
| take_rate_drift | MX | -0.6% | 10.0% | 20.0% | ok | T4 take 0.0256 vs budget 0.0258 |

## 3. Ponte da margem de contribuição
Convenção: efeitos puros sobre o estado de referência (volume ao take rate médio de referência; mix = mudança de participação entre países às taxas de referência; taxa = mudança de take rate às participações de referência) e uma linha explícita de **interação** (termos de 2ª e 3ª ordem). A ponte fecha com a variação total; resíduo = 0 dentro da tolerância numérica. Custos: parte de volume (ΔTPV × custo/TPV de referência) e parte de taxa/mix.

**Orçamento → Realizado.** Maiores efeitos: Processing cost: rate/mix (-317,049); Fee: TPV volume (+207,920); Processing cost: volume (-34,102).

| step | effect | kind |
|---|---|---|
| Contribution (reference) | 292,787 | start |
| Fee: TPV volume | 207,920 | fee |
| Fee: country mix | -4,658 | fee |
| Fee: take rate | -282 | fee |
| Fee: interaction (vol x mix x rate) | -3,691 | fee |
| Refund + chargeback: volume | -4,158 | cost |
| Refund + chargeback: rate/mix | -33,817 | cost |
| Incentives: volume | -4,872 | cost |
| Incentives: rate/mix | -0 | cost |
| Processing cost: volume | -34,102 | cost |
| Processing cost: rate/mix | -317,049 | cost |
| Other variable cost: volume | -9,743 | cost |
| Other variable cost: rate/mix | -0 | cost |
| Residual | -0 | residual |
| Contribution (compared) | 88,336 | end |

**Orçamento → Previsão** (diferença entre os dois planos): Processing cost: rate/mix (-257,345); Fee: TPV volume (+85,259); Refund + chargeback: rate/mix (-23,410).

**Previsão → Realizado** (decomposição do erro de previsão): Fee: TPV volume (+122,780); Processing cost: volume (-86,171); Refund + chargeback: volume (-8,462).

| step | effect | kind |
|---|---|---|
| Contribution (reference) | 76,070 | start |
| Fee: TPV volume | 122,780 | fee |
| Fee: country mix | -1,242 | fee |
| Fee: take rate | -5,933 | fee |
| Fee: interaction (vol x mix x rate) | -2,033 | fee |
| Refund + chargeback: volume | -8,462 | cost |
| Refund + chargeback: rate/mix | -4,399 | cost |
| Incentives: volume | -2,874 | cost |
| Incentives: rate/mix | 0 | cost |
| Processing cost: volume | -86,171 | cost |
| Processing cost: rate/mix | 6,348 | cost |
| Other variable cost: volume | -5,748 | cost |
| Other variable cost: rate/mix | 0 | cost |
| Residual | 0 | residual |
| Contribution (compared) | 88,336 | end |

**Premissas de razão do orçamento v1 vs. observado.** O orçamento fixou, no P2.1, custo de processamento e refund+chargeback sem calibrá-los contra o P1; os dados mostram:

| ratio | budget_v1 | trailing_90d_at_as_of | actual_t4 | actual_vs_budget_rel |
|---|---|---|---|---|
| take_rate (fee/TPV) | 0.0213 | 0.0214 | 0.0210 | -1.4% |
| refund+chargeback / fee | 0.0200 | 0.0690 | 0.0774 | 287.1% |
| incentives / TPV | 0.0005 | 0.0005 | 0.0005 | 0.0% |
| processing cost / TPV | 0.0035 | 0.0150 | 0.0148 | 321.9% |
| other variable cost / TPV | 0.0010 | 0.0010 | 0.0010 | 0.0% |

Isto é uma diferença aritmética entre premissas e razões observadas. Os efeitos "rate/mix" de processamento e de refund+chargeback na ponte acima vêm dessa diferença. Esse erro **não** estava entre os erros propositais declarados (crescimento e mix de take rate); a ponte de TPV (volume) reflete o erro declarado de crescimento.

Receita de fee, Orçamento → Realizado (puros + interação): volume +207,920, mix -4,658, rate -282, interaction -3,691.

**Orçamento v2 (reforecast congelado em 30/09, só com dados ≤ 30/09).** Regras em `configs/budget_v2_rules.yaml`: nível = TPV de setembro por dia e país, crescimento composto de abril a setembro, razões dos últimos 90 dias. Erro do TPV no trimestre: v1 -34.6%, v2 -17.1%, previsão composta -20.4%. Erro da margem: v1 +231.4%, v2 -10.1%, previsão composta -13.9% (erro = (plano − realizado) / realizado).

| metric | actual | budget_v1 | budget_v2 | v1_err_pct | v2_err_pct | forecast_composed | forecast_err_pct |
|---|---|---|---|---|---|---|---|
| TPV | 28,142,909 | 18,399,499 | 23,327,645 | -34.6% | -17.1% | 22,394,835 | -20.4% |
| Net revenue | 532,028 | 375,585 | 451,743 | -29.4% | -15.1% | 434,192 | -18.4% |
| Contribution margin | 88,336 | 292,787 | 79,430 | 231.4% | -10.1% | 76,070 | -13.9% |

Ponte Orçamento v2 → Realizado:

| step | effect | kind |
|---|---|---|
| Contribution (reference) | 79,430 | start |
| Fee: TPV volume | 102,734 | fee |
| Fee: country mix | -720 | fee |
| Fee: take rate | -6,257 | fee |
| Fee: interaction (vol x mix x rate) | -1,527 | fee |
| Refund + chargeback: volume | -7,078 | cost |
| Refund + chargeback: rate/mix | -4,458 | cost |
| Incentives: volume | -2,408 | cost |
| Incentives: rate/mix | -0 | cost |
| Processing cost: volume | -72,037 | cost |
| Processing cost: rate/mix | 5,473 | cost |
| Other variable cost: volume | -4,815 | cost |
| Other variable cost: rate/mix | -0 | cost |
| Residual | 0 | residual |
| Contribution (compared) | 88,336 | end |


## 4. O que mudou no volume: Jul–Set → Out–Dez (LMDI, descritivo)
TPV = merchants com venda × pagamentos/merchant × ticket médio. Os efeitos somam exatamente a variação de TPV entre os dois trimestres (interações repartidas simetricamente).

| driver | from | to | effect |
|---|---|---|---|
| active_merchants | 278.00 | 300.00 | 1,775,759 |
| payments_per_merchant | 337.23 | 453.55 | 6,909,302 |
| avg_ticket_brl | 203.46 | 206.83 | 382,958 |

Merchants com venda: 278 → 300; pagamentos por merchant: 337.2 → 453.6; ticket médio: 203.46 → 206.83.

Fator sazonal mensal configurado no gerador sintético do P1 (`seasonality.month`): média Out-Dez 1.200 vs Jul-Set 1.007, razão 1.192. É um parâmetro do gerador (verdade conhecida só porque os dados são sintéticos), não uma estimativa a partir dos dados.

## 5. Cenários (hipóteses de negócio) e banda estatística (separadas)
**Cenários** (`configs/scenarios.yaml`) são premissas sobre merchants, volume/merchant, ticket, take rate, refund+chargeback, custos. Não são intervalos de probabilidade nem foram calibrados para cobrir o realizado.

| scenario | tpv | fee | rc | inc | proc | var | net | contribution |
|---|---|---|---|---|---|---|---|---|
| conservative | 20,224,103 | 419,030 | 37,542 | 10,112 | 333,503 | 22,247 | 371,375 | 15,626 |
| base | 22,394,835 | 478,357 | 32,968 | 11,198 | 335,726 | 22,395 | 434,192 | 76,070 |
| optimistic | 24,704,414 | 543,520 | 31,840 | 12,352 | 351,832 | 23,469 | 499,328 | 124,027 |

Posição do realizado frente aos cenários:

| metric | actual | conservative | base | optimistic | actual_inside_scenarios |
|---|---|---|---|---|---|
| TPV | 28,142,909 | 20,224,103 | 22,394,835 | 24,704,414 | False |
| Net revenue | 532,028 | 371,375 | 434,192 | 499,328 | False |
| Contribution margin | 88,336 | 15,626 | 76,070 | 124,027 | True |

**Banda estatística** (previsão direta do campeão ± erros empíricos da soma de 90 dias no backtest; quantis 10–90%; as janelas se sobrepõem, n pequeno):

| metric | champion | n_origins | err_q_lo | err_q_hi | implied_lo | point | implied_hi | actual | actual_inside_band |
|---|---|---|---|---|---|---|---|---|---|
| TPV | sarima | 14 | -0.031 | 0.051 | 21,208,502 | 22,294,593 | 23,015,914 | 28,142,909 | False |
| Net revenue | sarima | 14 | -0.084 | 0.066 | 404,474 | 430,972 | 470,401 | 532,028 | False |
| Contribution margin | ma7 | 14 | -0.324 | 0.240 | 53,297 | 66,064 | 97,661 | 88,336 | True |

Cenário e banda medem coisas diferentes: o cenário muda hipóteses de negócio; a banda mede só o erro histórico de previsão do modelo dentro do padrão visto até setembro.

## 6. Sensibilidade (um driver por vez, ±10%)
| driver | change | d_tpv | d_net | d_contribution |
|---|---|---|---|---|
| merchants | -0.10 | -2,239,483 | -43,419 | -7,607 |
| merchants | 0.10 | 2,239,483 | 43,419 | 7,607 |
| volume_per_merchant | -0.10 | -2,239,483 | -43,419 | -7,607 |
| volume_per_merchant | 0.10 | 2,239,483 | 43,419 | 7,607 |
| ticket | -0.10 | -2,239,483 | -43,419 | -7,607 |
| ticket | 0.10 | 2,239,483 | 43,419 | 7,607 |
| take_rate | -0.10 | 0 | -44,539 | -44,539 |
| take_rate | 0.10 | 0 | 44,539 | 44,539 |
| refund_cb | -0.10 | 0 | 3,297 | 3,297 |
| refund_cb | 0.10 | 0 | -3,297 | -3,297 |
| proc_cost | -0.10 | 0 | 0 | 33,573 |
| proc_cost | 0.10 | 0 | 0 | -33,573 |
| var_cost | -0.10 | 0 | 0 | 2,240 |
| var_cost | 0.10 | 0 | 0 | -2,240 |

Interação do cenário conservador (efeito conjunto − soma dos efeitos individuais): TPV +68,752; net revenue +3,855; margem +6,227.

## 7. Limites
- Um ano de histórico sintético; um único trimestre de teste. Nada aqui é desempenho real nem estatística de longo prazo.
- Refund, chargeback, incentivos, custo variável e orçamento são premissas sintéticas (`assumptions.yaml`), e o orçamento v1 tem erro proposital declarado: toda variação contra ele é sintética por construção.
- Custo de processamento é tratado como proporção do TPV (as retentativas não são modeladas como driver separado).
- A previsão composta usa razões dos últimos 90 dias; chargebacks têm atraso de 15–60 dias, então a razão no as-of é uma leitura em base de data de evento.
- O orçamento v1 é rotulado as-of 2024-12-31, mas seu nível e take rate usam janeiro/2025 (o P1 não tem 2024): simplificação declarada, sem uso de T4.
- Pontes explicam a diferença aritmética; não provam causa.
