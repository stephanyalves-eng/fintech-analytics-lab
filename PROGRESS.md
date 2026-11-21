# Progresso

| Marco | Status | Evidência |
|---|---|---|
| M0 setup comum | concluído (sem commit) | ruff ok; pytest 6 passed (py3.12) |
| M1 P1 dados e SQL | concluído (P1.1–P1.3) | pytest 42 passed; `cli check` 18/18 PASS em 500k tentativas |
| M2 P1 dashboard | pendente | |
| M3 P2 dados e modelos | pendente | |
| M4 P2 dashboard | pendente | |
| M5 P3 protocolo e simulação | pendente | |
| M6 P3 análise e dashboard | pendente | |
| M7 auditoria/publicação | pendente | |

## Próximo passo
P1.4: diagnóstico e simulação de intervenções (S1/S2 de `assumptions.md`), seção P1.4 do blueprint.

## Log
- 2026-11-21 M0: estrutura do monorepo, pyproject, ruff, pytest e CI criados.
- 2026-11-21 P1.1: plano aprovado; problem_statement, data_dictionary (ERD Mermaid), metric_catalog (M01–M14) e assumptions (S1/S2, 11 testes de aceite) criados. Sem código.
- 2026-11-21 P1.2: gerador vetorizado + YAML (`configs/generator.yaml`), Parquet decimal + manifest (seed, schema, contagens, SHA-256). 500k em 3,5 s; 2M em 17,0 s; mesma seed ⇒ mesmo hash. Fixture corrompida com 14 defeitos, todos detectados. Ver `docs/generator.md`.
- 2026-11-21 P1.3: DuckDB staging → core → 5 marts; 13 checks de contrato + 5 de reconciliação (TPV não inflado); 15 análises; EXPLAIN ANALYZE de q04/q08/q11 em `reports/query_plans/`. Ver `docs/sql_walkthrough.md`.
