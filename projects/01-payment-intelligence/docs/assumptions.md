# P1 · Assumptions, cenários e testes de aceite

## Pressupostos do gerador (P1.2)
| Tema | Pressuposto |
|---|---|
| Volume | 500.000 tentativas por padrão; escala para 2M via config. O nº de pagamentos é derivado do volume |
| Reprodutibilidade | Seed fixa em `configs/`; mesma seed + mesma config ⇒ mesmos dados |
| Países/moedas | BR/BRL, MX/MXN, CL/CLP; 1 moeda por merchant |
| Métodos | `credit_card`, `debit_card` em todos os países; `pix` só BR, via `PIX_BR` |
| Retries | Máx. 3 tentativas; retry só após soft decline ou erro técnico |
| Probabilidades | As taxas de aprovação variam por adquirente, método, faixa de valor, hora e país. Os parâmetros ficam em config, rotulados `synthetic` |
| Custos/MDR | `fee_fixed_local`, `fee_bps_approved` e o MDR por método × porte são parâmetros sintéticos e não representam preços reais |
| Settlement | D+N por método; sem chargeback, refund ou falha de liquidação |
| FX | Série diária sintética para MXN e CLP em BRL |

## Cenários simulados (P1.4)
| ID | Cenário | Mecânica | Limitações |
|---|---|---|---|
| S1 | Roteamento alternativo de soft declines | Reprocessar com o adquirente alternativo, usando a taxa de aprovação observada **no dado sintético** para o segmento comparável | Assume que a aprovação do segmento se transfere ao novo adquirente (sem viés de seleção); ignora capacidade e contrato; **não é uplift causal** |
| S2 | Mudança no limite de retries (2 vs 3 vs 4) | Recalcular sucesso e custo usando a recuperação marginal por `attempt_no` | Extrapolar para 4 tentativas está fora do suporte dos dados; ignora o atrito do usuário e as regras de bandeira |

Os relatórios apresentam os resultados como "estimativa simulada sob pressupostos X", com faixa de sensibilidade, e nunca como impacto realizado.

## Edge cases e tratamento
| Caso | Tratamento |
|---|---|
| Pagamento sem tentativas | Inválido: o teste de contrato falha |
| `attempt_no` duplicado ou com lacuna | Inválido |
| Tentativa após uma aprovação | Inválido |
| Retry após hard decline | Inválido no gerador; nos marts é sinalizado como anomalia |
| Timeout | `result = error`, `category = technical`; entra em M10, não em M03 |
| Valor ≤ 0 ou CLP com decimais | Inválido |
| Moeda do settlement ≠ moeda do pagamento | Inválido |
| Settlement de pagamento `failed` | Inválido |
| Pagamento na virada do dia UTC × local | O período usa a data local do merchant |

## Riscos analíticos
- **Double counting:** TPV calculado por tentativa aprovada (mitigado por M06 + teste).
- **Confusão M01 × M02:** regra anti-ambiguidade no catálogo.
- **Simpson/mix:** a comparação entre adquirentes precisa controlar país, método e faixa de valor.
- **Circularidade:** os padrões "descobertos" foram plantados pelo gerador. O relatório declara isso.

## Testes de aceite (a implementar na P1.2/P1.3)
1. PKs únicas e FKs válidas em todas as tabelas.
2. Cada `payment_id` tem ≥ 1 tentativa; `attempt_no` = 1..n sem lacunas; timestamps crescentes.
3. ≤ 1 tentativa `approved` por pagamento, e ela é a última.
4. `final_status = succeeded` ⇔ existe tentativa `approved`.
5. Sem retry após `hard`; nº de tentativas ≤ 3.
6. Coerência `result` × `decline_code` × `category`.
7. `pix` só em BR e só com `PIX_BR`; adquirente do mesmo país do merchant.
8. Settlement: 1 por pagamento `succeeded`; `gross = amount`; `net = gross − fee`; mesma moeda.
9. Anti-double-counting: M06 do mart = Σ `amount` de `fact_payment` com `succeeded`, calculado direto na tabela (o join payment × attempt não pode multiplicar linhas no TPV).
10. Nenhuma agregação monetária soma moedas sem FX.
11. Mesma seed ⇒ hash idêntico dos dados gerados.
