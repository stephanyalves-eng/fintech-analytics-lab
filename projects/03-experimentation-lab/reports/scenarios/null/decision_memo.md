# Memo de decisão · P3-EXP-001 · cenário `null`

> **Dados 100% sintéticos** (`synthetic`), seed 3101, protocolo v1.0.0 bloqueado (SHA-256, 0 emendas). Os valores econômicos são **hipotéticos** e dependem de premissas [TO VERIFY].

## Decisão: **INCONCLUSIVE** (section 8, step 4)
- P01 95% CI [-0.0115, +0.0052] includes 0; non-significance is not evidence of no effect

## Validade (antes de qualquer efeito)
- SRM: A=26560, B=26164, p=0.0846 (limite 0.001) → ok
- Integridade da atribuição: 0 duplicados, 0 divergências do hash → ok
- Eventos antes da exposição: 0
- Trilhas incompletas: A 0.00%, B 0.00% → ok

## Métrica primária P01 (conversão do usuário em 7 d, grão usuário, ITT)
- A 60.89% (n=26560) · B 60.58% (n=26164)
- Diferença -0.31 p.p., IC 95% [-1.15 p.p., +0.52 p.p.], p=0.4619
- Relativa -0.51% [-1.87%, +0.86%]
- MDE de desenho no n observado: +1.19 p.p. (não é poder observado)

## Guardrails (não inferioridade; d = B − A, maior é pior)
| ID | Métrica | A | B | d | IC 95% | Margem | Status |
|---|---|---|---|---|---|---|---|
| G1 | chargeback_rate | 0.004328 | 0.004354 | +0.003 p.p. | [-0.142 p.p., +0.147 p.p.] | +0.200 p.p. | **pass** |
| G2 | technical_failure_rate | 0.01966 | 0.01972 | +0.006 p.p. | [-0.246 p.p., +0.258 p.p.] | +0.500 p.p. | **pass** |
| G3 | auth_latency_p95_ms | 4119 ms | 4125 ms | +6 ms | [-70 ms, +84 ms] | +300 ms | **pass** |
| G4 | cost_per_approved_payment_brl | 3.814 | 3.761 | -1.40% | [-3.63%, +0.89%] | 2% | **pass** |
| G5 | checkout_abandonment | 0.2502 | 0.2532 | +0.302 p.p. | [-0.439 p.p., +1.043 p.p.] | +2.000 p.p. | **pass** |

## Sensibilidade (não decisória)
- Excluindo 0 usuários com trilha incompleta: -0.31 p.p. [-1.15 p.p., +0.52 p.p.]
- Erro-padrão robusto HC1: -0.31 p.p. [-1.15 p.p., +0.52 p.p.]

## Economia HIPOTÉTICA
- Valor por usuário: A R$ -0.76 · B R$ -0.69 · Δ R$ +0.077 [-0.195, +0.349]
- Anualizado (730,000 usuários/ano, premissa): Δ R$ 55,966 [R$ -142,669, R$ 254,600]
- Após custo de implementação assumido (R$ 150,000): R$ -94,034 [R$ -292,669, R$ 104,600]
- A regra de lançamento do protocolo **não** usa esta seção.

## Segmentos (exploratórios, sem correção de multiplicidade, não decidem nada)
| Segmento | Nível | n A | n B | Δ | IC 95% |
|---|---|---|---|---|---|
| card_type | credit_card | 18539 | 18191 | -0.50 p.p. | [-1.50 p.p., +0.50 p.p.] |
| card_type | debit_card | 8021 | 7973 | +0.12 p.p. | [-1.40 p.p., +1.63 p.p.] |
| new_vs_returning_user | new | 16007 | 15731 | -0.12 p.p. | [-1.19 p.p., +0.95 p.p.] |
| new_vs_returning_user | returning | 10553 | 10433 | -0.60 p.p. | [-1.93 p.p., +0.72 p.p.] |
| ticket_band | high | 6911 | 6895 | -0.19 p.p. | [-1.82 p.p., +1.44 p.p.] |
| ticket_band | low | 6222 | 6096 | -0.36 p.p. | [-2.09 p.p., +1.36 p.p.] |
| ticket_band | mid | 13427 | 13173 | -0.35 p.p. | [-1.52 p.p., +0.82 p.p.] |

## Limitações
- Efeito ITT de oferecer B, na população simulada (BR, cartão); sem validade externa.
- Chargeback simulado com maturação de 30 d; na prática pode levar 90 d ou mais.
- Interferência entre usuários assumida desprezível (não verificada).
- Não significativo ≠ sem efeito; um guardrail `undetermined` não prova segurança.
