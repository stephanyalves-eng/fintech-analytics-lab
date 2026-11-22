# P3 · Métodos, simulador e ressalvas

Dados 100% **sintéticos**. Parâmetros do protocolo: [`protocol.md`](protocol.md) (travado por SHA-256).

## Simulador (P3.2)
- `simulator.py` lê `configs/simulation.yaml` (efeito verdadeiro) e só as regras de atribuição do protocolo. A análise, a decisão, a economia, o Monte Carlo e o dashboard **não importam** o simulador nem leem esse YAML ou o `truth.json` (teste AST em `tests/p3/test_simulator_analysis.py`).
- Atribuição: SHA-256 com salt do protocolo, estável por usuário. Risco do usuário é latente e nunca exportado.
- Eventos: `exposure`, `checkout_start`, `payment_attempt` (até 3, retry só após falha), `payment_approved`, `chargeback`.
- Cenários: `null`, `positive`, `negative`, `srm` (8% dos B perdem o log de exposição), `missing` (10% dos eventos de tentativa em B e 1% em A não são logados). Seeds fixadas antes de qualquer análise.
- Trilha incompleta (detectável só pelos eventos): aprovação sem evento de tentativa ou lacuna na numeração das tentativas. Tentativas perdidas sem evento posterior são invisíveis, então a fração detectada é um piso.

## Motor estatístico (P3.3)
| Item | Método |
|---|---|
| P01 | z de duas proporções; p-value com SE combinado, IC 95% com SE Wald; relativo por delta em log(pB/pA) |
| G1, G2, G4 | razão de somas com variância robusta por usuário (delta); G4 relativo via log da razão |
| G3 | bootstrap por usuário (2000 reps, seed fixa) do p95 |
| G5 | duas proporções no grão usuário |
| Status | pass / fail / undetermined pela regra do protocolo |
| Multiplicidade | uma primária; guardrails por interseção-união; segmentos exploratórios |
| Sensibilidade | excluir trilhas incompletas; SE robusto HC1 (deve coincidir com P01) |

O MDE reportado é de **desenho** no n observado, não poder observado. O design effect observado é calculado por guardrail e fica em `results.json`.

## Monte Carlo (`reports/monte_carlo.csv`, 20.000 repetições; G4 com 2.000 e G3 com 300)
Usa os mesmos estimadores da análise sobre usuários simulados diretamente, com `mc_se` por linha. O poder conjunto cobre só P01, G1, G2 e G5 e supõe guardrails sem degradação.

| Verificação | Taxa (± EP) | Leitura |
|---|---|---|
| P01 erro tipo I | 0,0500 ± 0,0015 | calibrado |
| G5 / G1 / G4 "pass" na margem (tipo I) | 0,0243 / 0,0242 / 0,0235 | ≤ 0,025, ok |
| G2 "pass" na margem (tipo I) | 0,0282 ± 0,0012 | **~2,7 EP acima de 0,025**: excesso pequeno e real |
| G3 "pass" na margem (tipo I) | 0,033 ± 0,010 | grosseiro (300 simulações), inconclusivo |
| Poder de P01 no MDE / G5 / G2 / G1 | 0,996 / 0,999 / 0,997 / 0,869 | acima de 0,80 |
| **Poder de G4 sem degradação** | **0,35 ± 0,01** | **abaixo do alvo 0,80** |
| Poder conjunto P01+G1+G2+G5 | 0,866 | acima da aproximação 0,79 do protocolo |

- A taxa de 0,031 do G5 numa rodada de 2.000 repetições era ruído de Monte Carlo; com 20.000 ficou em 0,0243.
- **G2:** o intervalo por delta é levemente anticonservador (0,028 contra 0,025). O desvio é pequeno. Corrigir exigiria trocar o método do intervalo, o que é uma emenda ao protocolo e não foi feita.
- **G4 é o gargalo de "Launch".** O n do protocolo foi dimensionado por G1 e não cobre G4 (sem poder pré-experimento em forma fechada). Com a variância de ticket assumida no simulador, G4 fica `undetermined` na maioria dos experimentos sem diferença real. Como G4 precisa passar para lançar, o poder real de Launch é bem menor que 0,87, e o produto simples com G4 dá uma ordem de grandeza de ~0,3 (independência assumida, não simulada em conjunto). Resolver exige decisão: aumentar n, alargar a margem de 2% ou aceitar. Isso muda o protocolo e fica para você decidir.
- O poder de G1 (0,87) e o conjunto (0,87) superam a aproximação do protocolo porque o design effect de 1,2 é conservador para este simulador: o design effect observado em G1 e G2 nos cenários é ≈ 1,0 (`results.json`). Isso vale **por construção** (as tentativas de um usuário são independentes no simulador) e **não** valida nem refuta o 1,2 para dados reais.
- O texto de `protocol.md` ainda diz "G3/G4 [TO VERIFY]". Ele está travado e não foi editado; esta seção o substitui como registro do que foi verificado.

## Conformidade com o protocolo (auditoria)
- **Trilhas incompletas (§7.3):** usuários com trilha incompleta ficam no denominador e **não contam como conversão** (`converted = aprovação registrada e trilha completa`). A versão anterior contava; isso foi corrigido e o cenário `missing` regenerado (o sinal do P01 nesse cenário muda, mas o resultado é INVALID de qualquer forma).
- **Data de análise (dia 65):** o manifest agora registra `observation_end` e a análise recusa (`DataNotMatureError`) dados observados antes de última exposição + 7 d + 30 d, ou sem esse campo. Isso evita chargeback e conversão censurados sem aviso.
- **Resultado INVALID no dashboard:** as abas Results, Guardrails, Sensitivity e Decision mostram um aviso de que os números não devem ser interpretados.

## Decisão e economia (P3.4)
`decision.py` aplica a ordem INVALID → DO NOT LAUNCH → LAUNCH → INCONCLUSIVE. `economics.py` usa premissas hipotéticas (`configs/economics.yaml`, fora do lock) e **não altera** a decisão. Segmentos são exploratórios.

## Limitações
Efeito ITT na população simulada (BR, cartão); chargeback com maturação de 30 d; interferência entre usuários assumida desprezível; sem validade externa; não significativo não significa sem efeito.
