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

## Monte Carlo (`reports/monte_carlo.csv`, 2000 reps)
Usa os mesmos estimadores da análise sobre usuários simulados diretamente. Não cobre G3 e G4 [TO VERIFY]. O poder conjunto cobre P01, G1, G2 e G5 e supõe guardrails sem degradação.
- Erro tipo I de P01 ≈ 0,043 (esperado ~0,05). Nos guardrails de não inferioridade, a taxa de "pass" com degradação igual à margem ficou em 0,027 (G1), 0,0185 (G2) e 0,031 (G5), contra 0,025 esperado. Com 2000 repetições o erro-padrão é ≈ 0,0035, então G5 está cerca de 1,7 EP acima: **limítrofe, não conclusivo**. Aumentar as repetições antes de afirmar controle de erro.
- O poder simulado de G1 (0,85) e o conjunto (0,86) ficaram acima da aproximação do protocolo (0,79), porque o design effect simulado é menor que o 1,2 assumido. Isso não valida o 1,2.

## Decisão e economia (P3.4)
`decision.py` aplica a ordem INVALID → DO NOT LAUNCH → LAUNCH → INCONCLUSIVE. `economics.py` usa premissas hipotéticas (`configs/economics.yaml`, fora do lock) e **não altera** a decisão. Segmentos são exploratórios.

## Limitações
Efeito ITT na população simulada (BR, cartão); chargeback com maturação de 30 d; interferência entre usuários assumida desprezível; sem validade externa; não significativo não significa sem efeito.
