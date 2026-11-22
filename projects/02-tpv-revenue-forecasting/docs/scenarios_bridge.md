# P2.4 — Cenários, ponte de variância, alertas

Comando: `python -m fintech_lab.p2_forecasting.cli close` (lê `data/p2/`, campeões congelados e holdout). Saídas: `reports/p24_*.csv` e `reports/executive_closing_report.md`. Todos os valores são sintéticos.

## Cenários vs. incerteza estatística
- **Cenário** (`configs/scenarios.yaml`): premissa de negócio sobre 7 drivers, em variação relativa: merchants ativos, pagamentos por merchant, ticket, take rate, refund+chargeback/fee, custo de processamento/TPV, outros custos/TPV. TPV = merchants × volume/merchant × ticket (produto, não soma: a interação é explícita). Valores redondos e ilustrativos, fixados antes da comparação com o T4; **não** calibrados para cobrir o realizado.
- **Base** = previsão do campeão de TPV por país × razões dos últimos 90 dias até o as-of. É a "previsão composta"; difere da previsão direta do campeão de cada alvo (as duas aparecem no relatório).
- **Banda estatística** (separada): previsão direta do campeão ± quantis 10–90% dos erros relativos da soma de 90 dias no backtest (14 origens sobrepostas). Mede só o erro histórico do modelo.
- **Sensibilidade:** um driver por vez ±10% e a interação do cenário conservador (efeito conjunto − soma dos individuais).

## Ponte (fecha sem resíduo)
Receita de fee = T · Σ s_c · r_c. Contra um estado de referência: `volume = ΔT · r̄`, `mix = T_b · Σ Δs · r_b`, `taxa = T_b · Σ s_b · Δr`, e **interação** = demais termos (ΔT·Σ Δs·r_b + ΔT·Σ s_b·Δr + T_b·Σ Δs·Δr + ΔT·Σ Δs·Δr). Soma = ΔFee por álgebra; o código verifica numericamente e falha se não fechar. Custos: parte de volume (ΔT × custo/TPV de referência) e parte de taxa/mix. Pontes calculadas: Orçamento→Previsão, Previsão→Realizado e Orçamento→Realizado (por país). Decomposição descritiva Jul–Set→Out–Dez do TPV por LMDI (merchants × pagamentos/merchant × ticket), exata.

## Alertas (`configs/alerts.yaml`)
Limites amber/red genéricos (10/20%, etc.), configuráveis e fixados antes de olhar o T4: previsão vs orçamento, run-rate YTD, confiabilidade do modelo (WAPE), cobertura do intervalo, deriva de take rate, deriva de refund+chargeback/fee, concentração top-10 merchants; ex-post: realizado vs orçamento. Avaliados ex-ante (só informação ≤ 30/09) e ex-post.

## Achado sobre o próprio orçamento v1
A ponte e o quadro de razões mostram que as premissas de **custo de processamento (0,35% do TPV)** e de **refund+chargeback (2% da fee)**, escritas no P2.1, ficaram muito abaixo das razões observadas (≈ 1,5% e ≈ 7%). Não eram erros propositais declarados (esses são crescimento +4% a.m. e take rate sem mix). Os alertas ex-ante já apontavam o desvio. O orçamento v1 permanece congelado; corrigir exige um v2.
