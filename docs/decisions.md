# Decision log

| Data | Decisão | Motivo |
|---|---|---|
| 2026-11-21 | Monorepo com um único `pyproject.toml` | Menos configuração duplicada; projetos separáveis depois |
| 2026-11-21 | Python 3.12 no `.venv` | 3.15 é recente demais; risco de falta de wheels (DuckDB, SciPy, Statsmodels) |
| 2026-11-21 | Código em `src/fintech_lab/`, artefatos por projeto em `projects/` | Pacote importável e testável; docs/SQL/app próximos de cada projeto |
| 2026-11-21 | Design tokens neutros até o design system SA ser fornecido | Não inventar ativos de marca |
