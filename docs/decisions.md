# Decision log

| Data | Decisão | Motivo |
|---|---|---|
| 2026-11-21 | Monorepo com um único `pyproject.toml` | Menos configuração duplicada; projetos separáveis depois |
| 2026-11-21 | Python 3.12 no `.venv` | 3.15 é recente demais; risco de falta de wheels (DuckDB, SciPy, Statsmodels) |
| 2026-11-21 | Código em `src/fintech_lab/`, artefatos por projeto em `projects/` | Pacote importável e testável; docs/SQL/app próximos de cada projeto |
| 2026-11-21 | Design tokens neutros até o design system SA ser fornecido | Não inventar ativos de marca |
| 2026-11-21 | P1: países BR/MX/CL com BRL/MXN/CLP; consolidação em BRL via FX sintético diário (data local de criação) | Multi-moeda realista sem somar moedas indevidamente |
| 2026-11-21 | P1: métodos crédito, débito e Pix (só BR, via `PIX_BR`); cada adquirente atua em 1 país | Simplifica custo/moeda por adquirente |
| 2026-11-21 | P1: máx. 3 tentativas; retry só após soft decline ou erro técnico | Ciclo de vida inequívoco e testável |
| 2026-11-21 | P1: settlement D+N simples, sem chargeback/refund | Escopo do MVP |
| 2026-11-21 | P1: take rate/net revenue marcadas `[TO VERIFY]` (MDR sintético) | Não apresentar receita fictícia como real |
