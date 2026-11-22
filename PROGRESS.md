# Progresso

| Marco | Status | Evidência |
|---|---|---|
| M0 setup comum | concluído (sem commit) | ruff ok; pytest 6 passed (py3.12) |
| M1 P1 dados e SQL | concluído (P1.1–P1.3) | pytest 42 passed; `cli check` 18/18 PASS em 500k tentativas |
| M2 P1 dashboard | concluído (P1.4–P1.5) | pytest 59 passed; ruff ok; 7 screenshots reais; 2M tentativas: consultas ≤ 62 ms |
| M3 P2 dados e modelos | pendente | |
| M4 P2 dashboard | pendente | |
| M5 P3 protocolo e simulação | concluído (P3.1–P3.2) | ver log P3.2 |
| M6 P3 análise e dashboard | concluído (P3.3–P3.5) | ver log P3.3–P3.5 |
| M7 auditoria/publicação | pendente | |

## Próximo passo
P2.1 (desenho do forecasting) ou auditoria independente do P3 (M7). Pendências do P1: publicar o repo para o CI rodar (M4) e os Low L1–L6 da auditoria.

## Log
- 2026-11-21 M0: estrutura do monorepo, pyproject, ruff, pytest e CI criados.
- 2026-11-21 P1.1: plano aprovado; problem_statement, data_dictionary (ERD Mermaid), metric_catalog (M01–M14) e assumptions (S1/S2, 11 testes de aceite) criados. Sem código.
- 2026-11-21 P1.2: gerador vetorizado + YAML (`configs/generator.yaml`), Parquet decimal + manifest (seed, schema, contagens, SHA-256). 500k em 3,5 s; 2M em 17,0 s; mesma seed ⇒ mesmo hash. Fixture corrompida com 14 defeitos, todos detectados. Ver `docs/generator.md`.
- 2026-11-21 P1.3: DuckDB staging → core → 5 marts; 13 checks de contrato + 5 de reconciliação (TPV não inflado); 15 análises; EXPLAIN ANALYZE de q04/q08/q11 em `reports/query_plans/`. Ver `docs/sql_walkthrough.md`.
- 2026-11-21 P1.4: `diagnostics.sql` (d01–d03, bases S1/S2), `scenarios.py` (S1 rerouting com mistura θ + IC 95%; S2 cap 2/3/4 com δ), sensibilidade θ × take rate e δ × take rate. `cli diagnose` gera `reports/diagnostic_memo.md` + 9 CSVs, só com números calculados. S1: IC exclui zero nas 6 direções (3 positivas, 3 negativas); trade-off: mais aprovações ⇒ contribuição menor nas 3 positivas.
- 2026-11-21 P1.5: Streamlit com 6 abas, filtros com denominadores por grão, tooltips, About/proveniência e estados vazio/erro/carregamento. `cli dashboard` faz tudo com uma instrução. AppTest + testes de serviço. Screenshots reais via `app/capture_screenshots.py`. QA em `docs/dashboard_qa.md`. Teclado e leitor de tela [TO VERIFY].
- 2026-11-21 Auditoria P1: ruff ok; pytest 59 passed; hash determinístico; check 18/18 (corrompido: 16 FAIL); memo/CSVs refeitos idênticos; S1 recalculado de forma independente (6/6). Achados: H1 README do P1 ausente; M1 build não bloqueia contrato; M2 contribuição S1 sem IC; M3 sem lock; M4 CI nunca rodou; M5 cohorts degenerados. Nenhuma correção aplicada (aguarda aprovação).
- 2026-11-21 Remediação P1 (H1, M1–M5): README do P1; build bloqueado por checks; IC bootstrap em S1 (ACQ_MX_A: sinal da contribuição agora indefinido); lock + versões no manifest (venv novo reproduz o hash); cohorts por ativação. ruff ok; pytest 69 passed; check 18/18; screenshots recapturados. CI segue sem rodar (sem remote).
- 2026-11-21 P3.1: protocolo pré-registrado P3-EXP-001 (3DS por risco vs. obrigatório): `docs/protocol.md` + `configs/protocol.yaml`; `power.py` (Cohen h; NI para guardrails com design effect 1,2) gera `reports/sample_size.csv`. G1 chargeback define o n: 26.333 usuários/braço, 28 dias, análise no dia 65; poder conjunto ≈ 0,79 (aprox.). Lock SHA-256 (LF) em `configs/protocol.lock.json`; `verify_lock()` obrigatório no P3.3. G3/G4 sem poder pré-experimento [TO VERIFY] (Monte Carlo no P3.3). Nenhum dado gerado.
- 2026-11-21 P3.2: simulador determinístico (`simulator.py`, `assignment.py`) com efeito verdadeiro em `configs/simulation.yaml`, separado da análise (teste AST). 5 cenários (null/positive/negative/srm/missing), eventos em Parquet + manifest + `truth.json`.
- 2026-11-21 P3.3: `analysis.py` (lock → portões → P01 → G1–G5 → sensibilidade); G1/G2/G4 com variância por usuário, G3 bootstrap. `montecarlo.py`: tipo I de P01 0,043; guardrails na margem 0,027/0,0185/0,031 (limítrofe, ver `docs/methods.md`). G3/G4 [TO VERIFY].
- 2026-11-21 P3.4: `decision.py` (regra travada), `economics.py` (hipotética), memos por cenário. Resultado: null INCONCLUSIVE, positive LAUNCH, negative DO NOT LAUNCH, srm e missing INVALID.
- 2026-11-21 P3.5: dashboard Streamlit (7 abas, 5 cenários), AppTest e 8 screenshots reais. Teclado e leitor de tela [TO VERIFY].
- 2026-11-21 P3 ressalvas: MC com 20.000 reps. Tipo I ok em P01/G1/G4/G5; G2 0,028 (leve excesso). G5 0,031 era ruído. G4 tem poder 0,35 sem degradação: gargalo do Launch, decisão de protocolo pendente. Design effect observado ≈ 1,0 (por construção). G3 grosseiro (300 sims).
- 2026-11-21 P3 a11y: axe-core 4.10.2 (vendored, SHA-256 fixado) nas 7 abas + cenário SRM (`app/a11y_audit.py`, `reports/a11y_axe.md`). Corrigido: contraste das legendas (cor `muted` + opacity 1) e `st.dataframe` solto que renderizava `stHelpDoc`; `deepl-input-controller` (extensão do navegador) excluído. Resultado: 0 violações automáticas, 1 item `incomplete` por tela para revisão manual. Teclado e leitor de tela seguem [TO VERIFY].
- 2026-11-21 Auditoria P3 (só relatório, nada corrigido): recálculo independente em DuckDB bate nos 5 cenários (P01, SRM, G1–G5); hash determinístico; protocolo travado inalterado desde o P3.1; IC cobre o efeito analítico verdadeiro nos 3 cenários válidos. Achados: M1 protocolo §7.3 diz que trilha incompleta não conta como conversão, mas o código conta (2.118 de 2.194 no cenário `missing`); L1 data de análise/maturação de 30 d não é imposta; L2 aba Results sem aviso quando o resultado é INVALID; L3 `decide()` sem teste unitário com entradas sintéticas.
- 2026-11-21 Remediação auditoria P3 (M1, L1–L3): trilha incompleta não conta como conversão (protocolo §7.3); `observation_end` no manifest e análise recusa dados imaturos; aviso INVALID em 4 abas; testes unitários de `decide()` (ordem e bordas). Relatórios regenerados: só `missing` mudou (P01 −3,44 p.p., INVALID). Screenshots e auditoria axe não refeitos (valid scenarios inalterados; banners novos só em INVALID).
