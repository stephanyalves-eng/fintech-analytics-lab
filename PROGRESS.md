# Progresso

| Marco | Status | Evidência |
|---|---|---|
| M0 setup comum | concluído (sem commit) | ruff ok; pytest 6 passed (py3.12) |
| M1 P1 dados e SQL | concluído (P1.1–P1.3) | pytest 42 passed; `cli check` 18/18 PASS em 500k tentativas |
| M2 P1 dashboard | concluído (P1.4–P1.5) | pytest 59 passed; ruff ok; 7 screenshots reais; 2M tentativas: consultas ≤ 62 ms |
| M3 P2 dados e modelos | pendente | |
| M4 P2 dashboard | pendente | |
| M5 P3 protocolo e simulação | pendente | |
| M6 P3 análise e dashboard | pendente | |
| M7 auditoria/publicação | pendente | |

## Próximo passo
P2.1: desenho do forecasting (propor plano e esperar aprovação). Pendências do P1: publicar o repo para o CI rodar (M4) e os Low L1–L6 da auditoria.

## Log
- 2026-11-21 M0: estrutura do monorepo, pyproject, ruff, pytest e CI criados.
- 2026-11-21 P1.1: plano aprovado; problem_statement, data_dictionary (ERD Mermaid), metric_catalog (M01–M14) e assumptions (S1/S2, 11 testes de aceite) criados. Sem código.
- 2026-11-21 P1.2: gerador vetorizado + YAML (`configs/generator.yaml`), Parquet decimal + manifest (seed, schema, contagens, SHA-256). 500k em 3,5 s; 2M em 17,0 s; mesma seed ⇒ mesmo hash. Fixture corrompida com 14 defeitos, todos detectados. Ver `docs/generator.md`.
- 2026-11-21 P1.3: DuckDB staging → core → 5 marts; 13 checks de contrato + 5 de reconciliação (TPV não inflado); 15 análises; EXPLAIN ANALYZE de q04/q08/q11 em `reports/query_plans/`. Ver `docs/sql_walkthrough.md`.
- 2026-11-21 P1.4: `diagnostics.sql` (d01–d03, bases S1/S2), `scenarios.py` (S1 rerouting com mistura θ + IC 95%; S2 cap 2/3/4 com δ), sensibilidade θ × take rate e δ × take rate. `cli diagnose` gera `reports/diagnostic_memo.md` + 9 CSVs, só com números calculados. S1: IC exclui zero nas 6 direções (3 positivas, 3 negativas); trade-off: mais aprovações ⇒ contribuição menor nas 3 positivas.
- 2026-11-21 P1.5: Streamlit com 6 abas, filtros com denominadores por grão, tooltips, About/proveniência e estados vazio/erro/carregamento. `cli dashboard` faz tudo com uma instrução. AppTest + testes de serviço. Screenshots reais via `app/capture_screenshots.py`. QA em `docs/dashboard_qa.md`. Teclado e leitor de tela [TO VERIFY].
- 2026-11-21 Auditoria P1: ruff ok; pytest 59 passed; hash determinístico; check 18/18 (corrompido: 16 FAIL); memo/CSVs refeitos idênticos; S1 recalculado de forma independente (6/6). Achados: H1 README do P1 ausente; M1 build não bloqueia contrato; M2 contribuição S1 sem IC; M3 sem lock; M4 CI nunca rodou; M5 cohorts degenerados. Nenhuma correção aplicada (aguarda aprovação).
- 2026-11-21 Remediação P1 (H1, M1–M5): README do P1; build bloqueado por checks; IC bootstrap em S1 (ACQ_MX_A: sinal da contribuição agora indefinido); lock + versões no manifest (venv novo reproduz o hash); cohorts por ativação. ruff ok; pytest 69 passed; check 18/18; screenshots recapturados. CI segue sem rodar (sem remote).
