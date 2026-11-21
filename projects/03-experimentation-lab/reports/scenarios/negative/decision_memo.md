# Memo de decisão · P3-EXP-001 · cenário `negative`

> **Dados 100% sintéticos** (`synthetic`), seed 3103, protocolo v1.0.0 bloqueado (SHA-256, 0 emendas). Os valores econômicos são **hipotéticos** e dependem de premissas [TO VERIFY].

## Decisão: **DO NOT LAUNCH** (section 8, step 2)
- P01 95% CI upper bound -0.0249 < 0 (conversion fell)
- guardrail(s) failed (harm beyond margin): G1, G2, G5

## Validade (antes de qualquer efeito)
- SRM: A=26522, B=26215, p=0.1813 (limite 0.001) → ok
- Integridade da atribuição: 0 duplicados, 0 divergências do hash → ok
- Eventos antes da exposição: 0
- Trilhas incompletas: A 0.00%, B 0.00% → ok

## Métrica primária P01 (conversão do usuário em 7 d, grão usuário, ITT)
- A 60.76% (n=26522) · B 57.43% (n=26215)
- Diferença -3.33 p.p., IC 95% [-4.17 p.p., -2.49 p.p.], p=7.163e-15
- Relativa -5.48% [-6.82%, -4.13%]
- MDE de desenho no n observado: +1.19 p.p. (não é poder observado)

## Guardrails (não inferioridade; d = B − A, maior é pior)
| ID | Métrica | A | B | d | IC 95% | Margem | Status |
|---|---|---|---|---|---|---|---|
| G1 | chargeback_rate | 0.004778 | 0.01262 | +0.784 p.p. | [+0.577 p.p., +0.992 p.p.] | +0.200 p.p. | **fail** |
| G2 | technical_failure_rate | 0.01988 | 0.02893 | +0.905 p.p. | [+0.622 p.p., +1.188 p.p.] | +0.500 p.p. | **fail** |
| G3 | auth_latency_p95_ms | 4083 ms | 4125 ms | +42 ms | [-45 ms, +124 ms] | +300 ms | **pass** |
| G4 | cost_per_approved_payment_brl | 3.785 | 3.884 | +2.62% | [+0.31%, +4.98%] | 2% | **undetermined** |
| G5 | checkout_abandonment | 0.2496 | 0.2776 | +2.799 p.p. | [+2.047 p.p., +3.550 p.p.] | +2.000 p.p. | **fail** |

## Sensibilidade (não decisória)
- Excluindo 0 usuários com trilha incompleta: -3.33 p.p. [-4.17 p.p., -2.49 p.p.]
- Erro-padrão robusto HC1: -3.33 p.p. [-4.17 p.p., -2.49 p.p.]

## Economia HIPOTÉTICA
- Valor por usuário: A R$ -0.76 · B R$ -2.07 · Δ R$ -1.310 [-1.745, -0.875]
- Anualizado (730,000 usuários/ano, premissa): Δ R$ -956,233 [R$ -1,273,784, R$ -638,681]
- Após custo de implementação assumido (R$ 150,000): R$ -1,106,233 [R$ -1,423,784, R$ -788,681]
- A regra de lançamento do protocolo **não** usa esta seção.

## Segmentos (exploratórios, sem correção de multiplicidade, não decidem nada)
| Segmento | Nível | n A | n B | Δ | IC 95% |
|---|---|---|---|---|---|
| card_type | credit_card | 18621 | 18408 | -3.11 p.p. | [-4.11 p.p., -2.11 p.p.] |
| card_type | debit_card | 7901 | 7807 | -3.85 p.p. | [-5.38 p.p., -2.31 p.p.] |
| new_vs_returning_user | new | 15881 | 15869 | -3.23 p.p. | [-4.31 p.p., -2.15 p.p.] |
| new_vs_returning_user | returning | 10641 | 10346 | -3.49 p.p. | [-4.82 p.p., -2.16 p.p.] |
| ticket_band | high | 6967 | 6750 | -4.61 p.p. | [-6.25 p.p., -2.96 p.p.] |
| ticket_band | low | 6161 | 6121 | -3.10 p.p. | [-4.84 p.p., -1.36 p.p.] |
| ticket_band | mid | 13394 | 13344 | -2.79 p.p. | [-3.96 p.p., -1.61 p.p.] |

## Limitações
- Efeito ITT de oferecer B, na população simulada (BR, cartão); sem validade externa.
- Chargeback simulado com maturação de 30 d; na prática pode levar 90 d ou mais.
- Interferência entre usuários assumida desprezível (não verificada).
- Não significativo ≠ sem efeito; um guardrail `undetermined` não prova segurança.
