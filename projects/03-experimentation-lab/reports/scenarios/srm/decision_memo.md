# Memo de decisão · P3-EXP-001 · cenário `srm`

> **Dados 100% sintéticos** (`synthetic`), seed 3104, protocolo v1.0.0 bloqueado (SHA-256, 0 emendas). Os valores econômicos são **hipotéticos** e dependem de premissas [TO VERIFY].

## Decisão: **INVALID** (section 8, step 1)
- validity gate failed: SRM; no effect is interpreted

## Validade (antes de qualquer efeito)
- SRM: A=26525, B=24109, p=6.836e-27 (limite 0.001) → FALHOU
- Integridade da atribuição: 0 duplicados, 0 divergências do hash → ok
- Eventos antes da exposição: 0
- Trilhas incompletas: A 0.00%, B 0.00% → ok

## Métrica primária P01 (conversão do usuário em 7 d, grão usuário, ITT)
- A 60.39% (n=26525) · B 63.28% (n=24109)
- Diferença +2.89 p.p., IC 95% [+2.04 p.p., +3.73 p.p.], p=2.458e-11
- Relativa +4.78% [+3.36%, +6.22%]
- MDE de desenho no n observado: +1.24 p.p. (não é poder observado)

## Guardrails (não inferioridade; d = B − A, maior é pior)
| ID | Métrica | A | B | d | IC 95% | Margem | Status |
|---|---|---|---|---|---|---|---|
| G1 | chargeback_rate | 0.003871 | 0.003736 | -0.013 p.p. | [-0.150 p.p., +0.123 p.p.] | +0.200 p.p. | **pass** |
| G2 | technical_failure_rate | 0.02058 | 0.01948 | -0.110 p.p. | [-0.368 p.p., +0.148 p.p.] | +0.500 p.p. | **pass** |
| G3 | auth_latency_p95_ms | 4122 ms | 3184 ms | -938 ms | [-1016 ms, -849 ms] | +300 ms | **pass** |
| G4 | cost_per_approved_payment_brl | 3.787 | 3.694 | -2.46% | [-4.69%, -0.18%] | 2% | **pass** |
| G5 | checkout_abandonment | 0.2502 | 0.2247 | -2.549 p.p. | [-3.290 p.p., -1.808 p.p.] | +2.000 p.p. | **pass** |

## Sensibilidade (não decisória)
- Excluindo 0 usuários com trilha incompleta: +2.89 p.p. [+2.04 p.p., +3.73 p.p.]
- Erro-padrão robusto HC1: +2.89 p.p. [+2.04 p.p., +3.73 p.p.]

## Economia HIPOTÉTICA
- Valor por usuário: A R$ -0.66 · B R$ -0.52 · Δ R$ +0.140 [-0.135, +0.416]
- Anualizado (730,000 usuários/ano, premissa): Δ R$ 102,558 [R$ -98,335, R$ 303,451]
- Após custo de implementação assumido (R$ 150,000): R$ -47,442 [R$ -248,335, R$ 153,451]
- A regra de lançamento do protocolo **não** usa esta seção.

## Segmentos (exploratórios, sem correção de multiplicidade, não decidem nada)
| Segmento | Nível | n A | n B | Δ | IC 95% |
|---|---|---|---|---|---|
| card_type | credit_card | 18685 | 16873 | +2.76 p.p. | [+1.75 p.p., +3.77 p.p.] |
| card_type | debit_card | 7840 | 7236 | +3.18 p.p. | [+1.63 p.p., +4.73 p.p.] |
| new_vs_returning_user | new | 15960 | 14324 | +2.97 p.p. | [+1.88 p.p., +4.06 p.p.] |
| new_vs_returning_user | returning | 10565 | 9785 | +2.78 p.p. | [+1.44 p.p., +4.12 p.p.] |
| ticket_band | high | 6897 | 6382 | +3.49 p.p. | [+1.84 p.p., +5.14 p.p.] |
| ticket_band | low | 6160 | 5505 | +3.35 p.p. | [+1.59 p.p., +5.12 p.p.] |
| ticket_band | mid | 13468 | 12222 | +2.36 p.p. | [+1.17 p.p., +3.55 p.p.] |

## Limitações
- Efeito ITT de oferecer B, na população simulada (BR, cartão); sem validade externa.
- Chargeback simulado com maturação de 30 d; na prática pode levar 90 d ou mais.
- Interferência entre usuários assumida desprezível (não verificada).
- Não significativo ≠ sem efeito; um guardrail `undetermined` não prova segurança.
