# P2 — Premissas (todas `synthetic`, versionadas)

Valores abaixo são **propostas iniciais**, não calibradas contra dado real. Ficam em `configs/assumptions.yaml` (P2.2), com `version`, `as_of` e hash no manifest. Mudar um valor exige nova versão.

## A. Refunds e chargebacks (camada sintética sobre pagamentos `succeeded`)
| Premissa | Valor inicial | Observação |
|---|---|---|
| Taxa de refund (% do TPV, por método) | crédito 2,0% · débito 1,0% · Pix 0,5% | Sorteio por pagamento, seed fixa, determinístico |
| Atraso do refund | 1–14 dias após a criação (uniforme) | Reconhecido na data do refund |
| `refund_fee_return_ratio` | 1,0 | Fee proporcional devolvida |
| Taxa de chargeback (% do TPV) | crédito 0,25% · débito 0,10% · Pix 0% | Pix sem chargeback (contestação é outro fluxo, fora do escopo) |
| Atraso do chargeback | 15–60 dias após a criação | Reconhecido na data do chargeback; parte cai fora do horizonte |
| Perda por chargeback | valor do pagamento + `chargeback_fee` fixa de R$ 15 (equiv. em BRL) | Parâmetro sintético |
| Pagamento não pode ter refund **e** chargeback | exclusão mútua | Evita dupla perda |

## B. Incentivos e custos
| Premissa | Valor inicial |
|---|---|
| `incentive_rate` (% do TPV) | 0,05% |
| `var_cost_rate` (% do TPV) | 0,10% |
| Custo de processamento | `processing_cost` do P1, sem alteração |

## C. Reconhecimento e período
- Reconhecimento por **data de criação local** do pagamento (accrual por transação). A data de settlement não define receita; a visão de caixa fica como análise opcional.
- Período contábil: mês-calendário no fuso do merchant. Para o consolidado, cada pagamento fica no mês do seu fuso local; **não** reagrupar por UTC.
- Eventos de refund/chargeback pertencem ao mês em que ocorrem.

## D. Orçamento (versão v1, as-of 2024-12-31)
O orçamento é um **plano fixado antes** do histórico, sintético, com **erro proposital** para dar desvios a explicar no P2.4.

| Parâmetro | Valor inicial | Papel |
|---|---|---|
| Base | O P1 não tem 2024. Âncora = TPV médio diário de **jan/2025** (primeiros 31 dias), gravado como constante `budget_base_daily_tpv_brl` | Simplificação declarada: a âncora usa só jan/2025, nunca T4; o valor é congelado em config |
| Crescimento mensal planejado | **+4,0%** a.m. composto | **Erro proposital (subestima)**: o P1 cresce muito mais rápido (volume de pagamentos de jan para dez/25 triplica, 20.737 → 65.104). A magnitude do erro em TPV só será conhecida após medir |
| Take rate planejado | **mesmo take rate estimado de P1 (M13) arredondado por país**, sem variação | Erro proposital de mix: orçamento ignora mudança de mix de método/país |
| Refund + chargeback planejados | 2,0% da receita bruta | Sem sazonalidade |
| Custos | `incentive_rate` e `var_cost_rate` da seção B + processamento = 0,35% do TPV | Processamento orçado como % fixo, ignora retries |
| Granularidade | mensal por país | Diário só por distribuição proporcional ao calendário |

Regras:
1. `budget_base_daily_tpv_brl` e o take rate planejado são **definidos em config antes** de qualquer leitura do realizado de T4 e registrados com timestamp; o commit que os cria é a prova.
2. O orçamento não é ajustado depois. Reforecast é uma versão nova (`v2`, as-of 2025-09-30), separada.
3. O erro proposital é declarado aqui e nos relatórios: todo desvio é **sintético por construção**, não evidência de gestão real.
4. A calibração da base e do take rate por país fica para o P2.2, usando só jan/2025; este documento só fixa a regra.

## E. Cenários (implementados no P2.4)
Definidos em `configs/scenarios.yaml` (variações relativas sobre 7 drivers; premissas de negócio, não intervalos). Base = previsão composta do campeão de TPV por país × razões dos últimos 90 dias até o as-of.

| Driver | Conservador | Base | Otimista |
|---|---|---|---|
| Merchants ativos | −3% | 0 | +3% |
| Pagamentos por merchant | −5% | 0 | +5% |
| Ticket médio | −2% | 0 | +2% |
| Take rate | −3% | 0 | +3% |
| Refund + chargeback / fee | +30% | 0 | −15% |
| Custo de processamento / TPV | +10% | 0 | −5% |
| Outros custos variáveis / TPV | +10% | 0 | −5% |

TPV = merchants × pagamentos/merchant × ticket (produto; a interação é explícita). Sensibilidade: um driver por vez ±10%. Os valores são redondos e ilustrativos, escolhidos depois de o holdout do P2.3 ter sido visto, sem ajuste ao resultado. **O estresse de FX previsto na especificação original (±10% nas moedas não-BRL) não foi implementado**; o FX entra apenas na conversão para BRL dos valores realizados.

## F. Riscos conhecidos
- Refund e chargeback são ruído sintético independente: não há correlação com risco, setor ou valor. Conclusões sobre sua previsibilidade não valem para dado real.
- Take rate do P1 é MDR sintético (`[TO VERIFY]`).
- Com 273 dias de treino, intervalos de previsão para 90 dias têm pouca base empírica; a cobertura será medida, não assumida.
