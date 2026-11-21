# Memo de decisão · P3-EXP-001 · cenário `positive`

> **Dados 100% sintéticos** (`synthetic`), seed 3102, protocolo v1.0.0 bloqueado (SHA-256, 0 emendas). Os valores econômicos são **hipotéticos** e dependem de premissas [TO VERIFY].

## Decisão: **LAUNCH** (section 8, step 3)
- P01 95% CI lower bound +0.0191 > 0
- all guardrails pass (non-inferiority shown)

## Validade (antes de qualquer efeito)
- SRM: A=26488, B=26146, p=0.136 (limite 0.001) → ok
- Integridade da atribuição: 0 duplicados, 0 divergências do hash → ok
- Eventos antes da exposição: 0
- Trilhas incompletas: A 0.00%, B 0.00% → ok

## Métrica primária P01 (conversão do usuário em 7 d, grão usuário, ITT)
- A 60.43% (n=26488) · B 63.17% (n=26146)
- Diferença +2.74 p.p., IC 95% [+1.91 p.p., +3.57 p.p.], p=9.753e-11
- Relativa +4.54% [+3.14%, +5.95%]
- MDE de desenho no n observado: +1.19 p.p. (não é poder observado)

## Guardrails (não inferioridade; d = B − A, maior é pior)
| ID | Métrica | A | B | d | IC 95% | Margem | Status |
|---|---|---|---|---|---|---|---|
| G1 | chargeback_rate | 0.004623 | 0.004238 | -0.038 p.p. | [-0.183 p.p., +0.106 p.p.] | +0.200 p.p. | **pass** |
| G2 | technical_failure_rate | 0.02048 | 0.01961 | -0.087 p.p. | [-0.341 p.p., +0.167 p.p.] | +0.500 p.p. | **pass** |
| G3 | auth_latency_p95_ms | 4125 ms | 3192 ms | -933 ms | [-1002 ms, -857 ms] | +300 ms | **pass** |
| G4 | cost_per_approved_payment_brl | 3.797 | 3.649 | -3.91% | [-6.07%, -1.70%] | 2% | **pass** |
| G5 | checkout_abandonment | 0.2512 | 0.2248 | -2.643 p.p. | [-3.370 p.p., -1.916 p.p.] | +2.000 p.p. | **pass** |

## Sensibilidade (não decisória)
- Excluindo 0 usuários com trilha incompleta: +2.74 p.p. [+1.91 p.p., +3.57 p.p.]
- Erro-padrão robusto HC1: +2.74 p.p. [+1.91 p.p., +3.57 p.p.]

## Economia HIPOTÉTICA
- Valor por usuário: A R$ -0.95 · B R$ -0.68 · Δ R$ +0.270 [-0.088, +0.628]
- Anualizado (730,000 usuários/ano, premissa): Δ R$ 196,822 [R$ -64,477, R$ 458,122]
- Após custo de implementação assumido (R$ 150,000): R$ 46,822 [R$ -214,477, R$ 308,122]
- A regra de lançamento do protocolo **não** usa esta seção.

## Segmentos (exploratórios, sem correção de multiplicidade, não decidem nada)
| Segmento | Nível | n A | n B | Δ | IC 95% |
|---|---|---|---|---|---|
| card_type | credit_card | 18629 | 18235 | +1.72 p.p. | [+0.73 p.p., +2.72 p.p.] |
| card_type | debit_card | 7859 | 7911 | +5.11 p.p. | [+3.60 p.p., +6.62 p.p.] |
| new_vs_returning_user | new | 15870 | 15699 | +2.97 p.p. | [+1.89 p.p., +4.04 p.p.] |
| new_vs_returning_user | returning | 10618 | 10447 | +2.40 p.p. | [+1.10 p.p., +3.71 p.p.] |
| ticket_band | high | 6803 | 6675 | +2.83 p.p. | [+1.20 p.p., +4.47 p.p.] |
| ticket_band | low | 6226 | 6213 | +1.98 p.p. | [+0.27 p.p., +3.69 p.p.] |
| ticket_band | mid | 13459 | 13258 | +3.05 p.p. | [+1.89 p.p., +4.22 p.p.] |

## Limitações
- Efeito ITT de oferecer B, na população simulada (BR, cartão); sem validade externa.
- Chargeback simulado com maturação de 30 d; na prática pode levar 90 d ou mais.
- Interferência entre usuários assumida desprezível (não verificada).
- Não significativo ≠ sem efeito; um guardrail `undetermined` não prova segurança.
