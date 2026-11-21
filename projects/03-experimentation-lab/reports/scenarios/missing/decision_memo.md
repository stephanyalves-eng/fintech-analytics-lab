# Memo de decisão · P3-EXP-001 · cenário `missing`

> **Dados 100% sintéticos** (`synthetic`), seed 3105, protocolo v1.0.0 bloqueado (SHA-256, 0 emendas). Os valores econômicos são **hipotéticos** e dependem de premissas [TO VERIFY].

## Decisão: **INVALID** (section 8, step 1)
- validity gate failed: missing events; no effect is interpreted

## Validade (antes de qualquer efeito)
- SRM: A=26498, B=26203, p=0.1988 (limite 0.001) → ok
- Integridade da atribuição: 0 duplicados, 0 divergências do hash → ok
- Eventos antes da exposição: 0
- Trilhas incompletas: A 0.73%, B 7.64% → FALHOU

## Métrica primária P01 (conversão do usuário em 7 d, grão usuário, ITT)
- A 60.47% (n=26498) · B 63.71% (n=26203)
- Diferença +3.23 p.p., IC 95% [+2.41 p.p., +4.06 p.p.], p=2e-14
- Relativa +5.35% [+3.95%, +6.76%]
- MDE de desenho no n observado: +1.19 p.p. (não é poder observado)

## Guardrails (não inferioridade; d = B − A, maior é pior)
| ID | Métrica | A | B | d | IC 95% | Margem | Status |
|---|---|---|---|---|---|---|---|
| G1 | chargeback_rate | 0.004244 | 0.004193 | -0.005 p.p. | [-0.146 p.p., +0.135 p.p.] | +0.200 p.p. | **pass** |
| G2 | technical_failure_rate | 0.02092 | 0.01974 | -0.118 p.p. | [-0.379 p.p., +0.142 p.p.] | +0.500 p.p. | **pass** |
| G3 | auth_latency_p95_ms | 4058 ms | 3160 ms | -898 ms | [-958 ms, -824 ms] | +300 ms | **pass** |
| G4 | cost_per_approved_payment_brl | 3.782 | 3.275 | -13.39% | [-15.40%, -11.34%] | 2% | **pass** |
| G5 | checkout_abandonment | 0.257 | 0.2893 | +3.232 p.p. | [+2.471 p.p., +3.992 p.p.] | +2.000 p.p. | **fail** |

## Sensibilidade (não decisória)
- Excluindo 2194 usuários com trilha incompleta: +0.77 p.p. [-0.08 p.p., +1.63 p.p.]
- Erro-padrão robusto HC1: +3.23 p.p. [+2.41 p.p., +4.06 p.p.]

## Economia HIPOTÉTICA
- Valor por usuário: A R$ -0.73 · B R$ -0.41 · Δ R$ +0.320 [+0.021, +0.619]
- Anualizado (730,000 usuários/ano, premissa): Δ R$ 233,624 [R$ 15,143, R$ 452,105]
- Após custo de implementação assumido (R$ 150,000): R$ 83,624 [R$ -134,857, R$ 302,105]
- A regra de lançamento do protocolo **não** usa esta seção.

## Segmentos (exploratórios, sem correção de multiplicidade, não decidem nada)
| Segmento | Nível | n A | n B | Δ | IC 95% |
|---|---|---|---|---|---|
| card_type | credit_card | 18572 | 18374 | +3.80 p.p. | [+2.81 p.p., +4.79 p.p.] |
| card_type | debit_card | 7926 | 7829 | +1.91 p.p. | [+0.39 p.p., +3.42 p.p.] |
| new_vs_returning_user | new | 16013 | 15710 | +3.27 p.p. | [+2.21 p.p., +4.34 p.p.] |
| new_vs_returning_user | returning | 10485 | 10493 | +3.18 p.p. | [+1.86 p.p., +4.49 p.p.] |
| ticket_band | high | 6940 | 6792 | +2.18 p.p. | [+0.55 p.p., +3.80 p.p.] |
| ticket_band | low | 6044 | 6041 | +3.03 p.p. | [+1.30 p.p., +4.75 p.p.] |
| ticket_band | mid | 13514 | 13370 | +3.86 p.p. | [+2.70 p.p., +5.02 p.p.] |

## Limitações
- Efeito ITT de oferecer B, na população simulada (BR, cartão); sem validade externa.
- Chargeback simulado com maturação de 30 d; na prática pode levar 90 d ou mais.
- Interferência entre usuários assumida desprezível (não verificada).
- Não significativo ≠ sem efeito; um guardrail `undetermined` não prova segurança.
