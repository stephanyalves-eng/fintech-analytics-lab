# Fintech Analytics Lab — instruções para o Claude

Portfólio de Data Analyst para fintechs: P1 Payment Intelligence, P2 TPV/Revenue Forecasting, P3 A/B Testing Lab.
Plano completo em `docs/BLUEPRINT.md` — **não ler inteiro**; ler só a seção da etapa citada (ex.: "P1.2").
Estado atual em `PROGRESS.md`; decisões em `docs/decisions.md`. Ler esses dois no início de cada sessão.

## Guardrails
- Windows, local-first. Python 3.12 (`.venv`), DuckDB, SQL, Pandas, SciPy, Statsmodels, Plotly, Streamlit, pytest, Ruff. Só ferramentas gratuitas.
- Nunca provisionar nuvem paga, criar API keys, usar conectores externos (Lovable, Canva etc.) ou serviços cobrados.
- Dados sintéticos sempre rotulados (`observed` / `synthetic` / `derived`). Seeds fixas, geradores determinísticos.
- Nunca inventar resultados, métricas, screenshots, benchmarks, acurácia ou impacto. Sem execução → placeholder `[TO VERIFY]`.
- Grão e denominador explícitos em todo KPI. Evitar double counting (retries não inflam TPV), leakage e claims causais indevidos.
- Arquitetura simples e testável. Não declarar sucesso sem rodar os comandos.

## Economia de créditos
- Etapas de desenho (P1.1, P2.1, P2.3, P3.1): propor plano e esperar aprovação. Demais etapas: implementar direto contra os critérios de aceite.
- Respostas curtas; não reimprimir arquivos inteiros; não usar subagentes sem pedido.
- Saída de comandos enxuta: `pytest -q`, `ruff check --quiet`.
- Ao fim de cada etapa: atualizar `PROGRESS.md` (≤ 10 linhas por etapa) e sugerir mensagem de commit.

## Estrutura
- Código: `src/fintech_lab/{shared,p1_payments,p2_forecasting,p3_experiments}`
- Por projeto: `projects/<nn-nome>/{sql,app,configs,reports,docs,assets}`
- Testes: `tests/{shared,p1,p2,p3}`; dados gerados em `data/` (não versionados)

## Comandos
```powershell
.\.venv\Scripts\Activate.ps1
ruff check --quiet .
pytest -q
```
