# Relatório do experimento P3-EXP-001 (todos os cenários)

> Dados sintéticos. Cada linha é uma execução real do pipeline travado.

| Cenário | Decisão | P01 Δ [IC 95%] | p | SRM p | Trilhas inc. B−A | Guardrails |
|---|---|---|---|---|---|---|
| null | **INCONCLUSIVE** | -0.31 p.p. [-1.15 p.p., +0.52 p.p.] | 0.462 | 0.0846 | +0.00% | G1:p G2:p G3:p G4:p G5:p |
| positive | **LAUNCH** | +2.74 p.p. [+1.91 p.p., +3.57 p.p.] | 9.75e-11 | 0.136 | +0.00% | G1:p G2:p G3:p G4:p G5:p |
| negative | **DO NOT LAUNCH** | -3.33 p.p. [-4.17 p.p., -2.49 p.p.] | 7.16e-15 | 0.181 | +0.00% | G1:f G2:f G3:p G4:u G5:f |
| srm | **INVALID** | +2.89 p.p. [+2.04 p.p., +3.73 p.p.] | 2.46e-11 | 6.84e-27 | +0.00% | G1:p G2:p G3:p G4:p G5:p |
| missing | **INVALID** | -3.44 p.p. [-4.29 p.p., -2.60 p.p.] | 1.12e-15 | 0.199 | +6.91% | G1:p G2:p G3:p G4:p G5:f |

Legenda dos guardrails: p = pass, f = fail, u = undetermined.
Memos por cenário em `reports/scenarios/<cenário>/decision_memo.md`.
