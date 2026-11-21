# P3 · Protocolo pré-registrado: P3-EXP-001 (3DS baseado em risco)

**Versão:** 1.0.0 · **Origem dos dados:** `synthetic`. Nenhum dado foi gerado e nenhum resultado foi calculado antes deste protocolo.
**Parâmetros:** [`configs/protocol.yaml`](../configs/protocol.yaml) é a fonte de verdade que o código lê. Se este texto divergir do YAML, vale o YAML.
**Bloqueio:** SHA-256 deste arquivo, do YAML e de [`reports/sample_size.csv`](../reports/sample_size.csv) em `configs/protocol.lock.json`. A análise (P3.3+) chama `verify_lock()` e aborta se algum hash não bater. Uma mudança depois do bloqueio só entra com `cli lock --amend "<motivo>"`, que fica registrada.

## 1. Pergunta e hipótese
- **Pergunta:** trocar o 3DS obrigatório (A, fluxo atual) pelo 3DS baseado em risco (B: sem desafio para baixo risco, desafio para alto risco) aumenta a conversão de checkout sem piorar fraude, falhas, latência, custo ou abandono?
- **Hipótese de negócio:** cada desafio 3DS adiciona atrito e faz parte dos usuários de baixo risco desistir. Tirar esse desafio deve aumentar as aprovações por usuário, com o risco de mais chargebacks.
- **H0:** p_B − p_A = 0 · **H1:** p_B − p_A ≠ 0 (bicaudal).
- **Estimando:** efeito ITT de *oferecer* B, entre os usuários elegíveis que dispararam o trigger de exposição, com o grupo tal como foi sorteado. Reportado como diferença absoluta e relativa (p_B / p_A − 1).

## 2. População, unidade e atribuição
| Item | Definição |
|---|---|
| Elegíveis | Usuários BR com checkout por cartão (`credit_card`, `debit_card`) iniciado na janela de entrada. Pix fica de fora porque não tem etapa 3DS |
| Exclusões | Contas internas/teste; usuários bloqueados por regra antifraude **antes** do checkout. A regra é pré-tratamento e vale igual para A e B |
| Unidade | `user_id`. A conversão é medida no mesmo grão, então compras repetidas não inflam o n |
| Alocação | 50/50 · `bucket = int(sha256(salt + ":" + user_id)[:15], 16) % 10000`; 0–4999 → A, 5000–9999 → B · salt `p3-exp-001-v1` |
| Persistência | O grupo é fixo por usuário durante todo o experimento; sessões seguintes herdam o grupo |
| Exposição | 1º `checkout_start` elegível na janela. O evento acontece **antes** da etapa 3DS e é registrado igual nos dois grupos, então o trigger não depende do tratamento |

**Interferência e clusters:** a unidade é o usuário e B não altera o roteamento entre merchants, então a interferência entre unidades é considerada desprezível. Isso é uma limitação declarada, não algo verificado. Um usuário com várias tentativas ou pagamentos forma um cluster. Por isso os guardrails no grão tentativa/pagamento usam inferência agrupada por usuário (método delta ou bootstrap por usuário).

## 3. Métrica primária
**P01 `user_conversion_7d`** = usuários expostos com ≥ 1 pagamento aprovado em até 7 dias após a 1ª exposição ÷ usuários expostos (grão usuário).
- Teste z de duas proporções: p-value com erro-padrão combinado (pooled); IC 95% de Δ com erro-padrão não combinado (Wald). α = 0,05 bicaudal, poder 0,80.
- Baseline assumido de 0,60 e MDE de +2,0 p.p. absolutos. Ambos são premissas sintéticas.

## 4. Guardrails (não inferioridade)
A degradação é d = B − A (ou B/A − 1 quando a margem é relativa); valor maior é pior. Cada guardrail é testado com α unilateral de 0,025.

| ID | Métrica | Grão | Margem | Inferência |
|---|---|---|---|---|
| G1 | Chargeback simulado em até 30 d ÷ pagamentos aprovados | pagamento aprovado | +0,20 p.p. (baseline assumido 0,40%) | delta, cluster por usuário |
| G2 | Tentativas com erro técnico ÷ tentativas | tentativa | +0,50 p.p. (baseline 2,0%) | delta, cluster por usuário |
| G3 | p95 da latência entre `checkout_start` e a decisão de autorização (ms) | tentativa | +300 ms | bootstrap por usuário (2000 reps, seed fixa) |
| G4 | Custo simulado (processamento + 3DS) ÷ pagamentos aprovados (BRL) | pagamento aprovado | +2% relativo | delta, cluster por usuário |
| G5 | Usuários expostos sem nenhuma tentativa em 7 d ÷ usuários expostos | usuário | +2,0 p.p. (baseline 25%) | duas proporções |

Cada guardrail recebe um destes três status:
- **pass:** o limite superior unilateral de 97,5% de d fica ≤ margem.
- **fail:** o limite inferior bicaudal de 95% de d fica > margem.
- **undetermined:** qualquer outro caso.

**Multiplicidade:** a métrica primária é uma só, então não há correção para ela. O lançamento exige que **todos** os guardrails passem. Isso é um teste interseção-união, que controla o erro de declarar falsamente "todos não inferiores" em α sem precisar de ajuste. Os segmentos são exploratórios e não entram na decisão.

## 5. Tamanho da amostra e duração
Calculados por `cli size` ([`power.py`](../../../src/fintech_lab/p3_experiments/power.py)). Os números abaixo foram copiados de `reports/sample_size.csv`, e um teste confere essa cópia.

| Métrica | Teste | Usuários/braço necessários | Poder no plano |
|---|---|---|---|
| P01 conversão | superioridade bicaudal, h de Cohen | 9335 | 0,9957 |
| G1 chargeback | não inferioridade, design effect 1,2 | **25016** | 0,8000 |
| G2 falha técnica | não inferioridade, design effect 1,2 | 10549 | 0,9907 |
| G5 abandono | não inferioridade | 8830 | 0,9971 |

- **Quem define o tamanho é o G1, não a métrica primária.** Com 9.335 usuários por braço, o G1 teria poder de cerca de 0,40 e o lançamento ficaria inconclusivo na maioria dos casos, mesmo com B seguro.
- **Planejado:** 25016 ÷ (1 − 0,05 de folga para eventos ausentes) = **26333 usuários/braço**, 52666 no total.
- **MDE da métrica primária no plano:** cerca de 1,22 p.p. (poder 0,80).
- **Poder conjunto aproximado de "Launch"** sob efeito verdadeiro igual ao MDE e guardrails sem degradação: 0,7869. É o produto dos poderes, supondo independência, e cobre só P01, G1, G2 e G5. G3 e G4 não têm poder pré-experimento em forma fechada; isso fica [TO VERIFY] por Monte Carlo no P3.3.
- **Duração:** com 2.000 novos elegíveis por dia (premissa), são **28 dias** de entrada (semanas inteiras, por causa da sazonalidade semanal). A análise roda no **dia 65**: entrada + 7 dias de conversão + 30 dias de maturação de chargeback.

## 6. Regras de parada
- Horizonte fixo e **nenhuma olhada interina por eficácia**. Os resultados de P01 e G1–G5 não são calculados antes do dia 65.
- **Parada de segurança** (só para proteger, sem inferência de efeito): monitoramento diário do G2. Se a taxa em B passar de 2 × a taxa em A, com ≥ 500 tentativas por braço, o experimento termina como `SAFETY_STOP`.

## 7. Portões de validade (antes de qualquer estimativa)
1. **SRM:** χ² de aderência contra 50/50 nos usuários expostos. Com p < 0,001, o resultado é **INVALID**.
2. Nenhuma unidade nos dois grupos; nenhum evento antes da exposição.
3. **Eventos ausentes:** a fração de expostos com trilha incompleta precisa ficar ≤ 2% em cada braço, e a diferença entre braços ≤ 0,5 p.p. Se não ficar, o resultado é **INVALID**. Usuários com trilha incompleta continuam no denominador (ITT) e não contam como conversão; uma análise de sensibilidade que os exclui é reportada à parte.

## 8. Regra de decisão (avaliada nesta ordem)
1. **INVALID:** algum portão de validade falhou.
2. **DO NOT LAUNCH:** algum guardrail com status `fail`, ou limite superior do IC 95% da P01 < 0.
3. **LAUNCH:** limite inferior do IC 95% da P01 > 0 **e** todos os guardrails com status `pass`.
4. **INCONCLUSIVE:** qualquer outro caso. Não significativo **não** quer dizer "sem efeito".

O impacto econômico (P3.4) é hipotético e informa o memo, mas não muda esta regra.

## 9. Plano de análise
1. `verify_lock()` → portões de validade → contagens por braço.
2. P01: taxas, Δ absoluto e relativo, IC 95% e p-value.
3. G1–G5: estimativa de d, IC e status pass/fail/undetermined.
4. Decisão pela regra da seção 8.
5. Sensibilidades (não decisórias): excluir trilhas incompletas; erro-padrão agrupado para P01 (deve coincidir, porque P01 já está no grão usuário).
6. Exploratório: segmentos `card_type`, `new_vs_returning_user`, `ticket_band`, rotulados como exploratórios e sem correção usada para decidir.
7. Verificação Monte Carlo (P3.3) do erro tipo I e do poder sob os cenários do simulador.

## 10. Premissas e limitações
- Baselines, margens, tráfego, design effect (1,2) e unidades por usuário são **premissas sintéticas**, não observadas. O design effect real vai ser estimado e reportado no P3.3.
- O chargeback é simulado e tem maturação de 30 dias, que na prática é curta (chargebacks reais chegam a 90 dias ou mais).
- A validade externa se limita à população simulada (BR, cartão, usuários novos na janela). O resultado não se generaliza para Pix, outros países ou outro mix de risco.
- O efeito verdadeiro do simulador (P3.2) fica numa configuração separada que a análise não lê.
