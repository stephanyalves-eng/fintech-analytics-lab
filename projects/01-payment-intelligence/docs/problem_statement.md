# P1 · Problem statement

> Todos os dados deste projeto são **sintéticos** (`synthetic`). O PSP, os merchants e os adquirentes são fictícios.

## Cenário operacional
Um PSP (Payment Service Provider) fictício processa pagamentos online de merchants em **Brasil, México e Chile**.
Cada pagamento iniciado pelo comprador gera uma ou mais **tentativas de autorização** (até 3), roteadas para um adquirente
(cartões) ou para um provider Pix (só BR). Pagamentos bem-sucedidos são **liquidados** ao merchant em D+N, conforme o método.

**Pergunta executiva:** onde as tentativas de pagamento falham, por quê, e quais mudanças podem melhorar a aprovação
sem piorar custo, risco e experiência?

## Personas
| Persona | Decisão que toma | O que precisa ver |
|---|---|---|
| Head of Payments | Prioridades de roadmap (roteamento, retries, parceiros) | Final success, approved TPV, tendência, top alavancas |
| Payment Ops Analyst | Investigar quedas e acionar adquirentes | Auth rate por adquirente/código/hora, latência, erros técnicos |
| Finance | Custo e margem do processamento | Processing cost, custo por pagamento bem-sucedido, receita estimada |
| Risk | Equilíbrio entre aprovação e fraude | Hard declines por motivo (fraude, cartão inválido), retries em hard decline |

## Perguntas de negócio
| # | Pergunta | Métricas (ver `metric_catalog.md`) |
|---|---|---|
| Q1 | Qual a taxa de sucesso final dos pagamentos e como ela varia por país, método e merchant? | M02, M06 |
| Q2 | Qual a taxa de autorização por tentativa e onde ela diverge do sucesso final? | M01, M02 |
| Q3 | Quais códigos de recusa concentram as falhas, e quanto delas é soft (recuperável) vs hard? | M03, M04 |
| Q4 | Quanto os retries recuperam, e quanto custam? | M05, M08, M09 |
| Q5 | Algum adquirente tem pior aprovação ou latência para o mesmo mix de transações? | M01, M10, M11 |
| Q6 | Existem padrões por faixa de valor, dia/hora local ou dispositivo? | M01, M02 |
| Q7 | Quanto TPV aprovado consolidado (BRL) o PSP processa, e com que custo por pagamento bem-sucedido? | M06, M07, M09 |
| Q8 | Em cenários **simulados** de roteamento ou de política de retry, qual seria a ordem de grandeza do efeito? | Cenários S1/S2 (`assumptions.md`) |

## Fora do escopo do MVP
- Chargebacks, refunds, disputas e fraude confirmada (só existe recusa por *suspeita* de fraude).
- 3DS/autenticação, tokenização, parcelamento e antecipação de recebíveis.
- Afirmações causais ou de uplift realizado: os cenários são simulações sobre dados sintéticos.
