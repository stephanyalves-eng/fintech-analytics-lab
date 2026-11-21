# FINTECH ANALYTICS LAB
## Blueprint de implementação | Projetos prioritários 01–03

**Versão:** 1.0 | **Data:** 17/11/2026  
**Idioma:** Português (prompts técnicos em inglês)  
**Objetivo:** portfólio demonstrável para vagas de Data Analyst em fintechs, com evidências de SQL avançado, Python, estatística, forecasting, experimentação, métricas de pagamentos e comunicação executiva.  
**Restrição:** não contratar novas ferramentas ou assinaturas. Utilizar Claude Code conforme acesso e limites já disponíveis, ferramentas open source e execução local no Windows.

> **Princípio de evidência:** dados sintéticos são explicitamente rotulados; métricas, conclusões e ganhos não podem ser inventados. Resultados de modelos, benchmarks, screenshots e relatórios somente podem ser divulgados após execução e validação.

---

# 0. Diretrizes e arquitetura transversal

## 0.1 Tradução das vagas em entregas verificáveis

| Competência exigida | Evidência no portfólio |
|---|---|
| SQL intermediário/avançado | CTEs, window functions, agregações condicionais, joins, EXPLAIN, testes de reconciliação |
| Python e estatística | Pandas/Polars opcional, NumPy, SciPy, Statsmodels, notebooks e scripts reproduzíveis |
| Pagamentos e Product Analytics | authorization rate, success rate, declines, retry, funil, segmentação |
| Forecasting e planejamento | TPV, receita, take rate, cenários, backtesting, desvios e decomposição |
| Testes A/B | randomização, tamanho de amostra, MDE, intervalos de confiança, guardrails |
| BI | dashboards com filtros, definições de KPIs, estados vazios, documentação |
| Data warehouse | DuckDB, tabelas dimensionais, data contracts, qualidade e linhagem |
| Comunicação executiva | one-pager de decisão, recomendações, limitações, anexos metodológicos |

## 0.2 Ferramentas e custos

- **Python 3.11+**, **uv** (opcional) ou `venv` + pip, **DuckDB**, **Pandas**, **NumPy**, **SciPy**, **Statsmodels**, **scikit-learn**, **Plotly**, **Streamlit**, **pytest**, **Ruff**, **Git**, **VS Code**: gratuitos e locais.
- **Power BI Desktop**: gratuito para desenvolvimento local; compartilhamento online pode exigir licença. Dashboard público principal em Streamlit ou publicação de capturas, conforme disponibilidade.
- **GitHub**: repositórios públicos e CI dentro das cotas gratuitas; conferir limites antes de usar runners.
- **Claude Code**: aproveitar a assinatura existente **somente se o acesso ao Code estiver habilitado**; confirmar limites e eventuais cobranças por API antes de executar. Nunca inserir chave paga por padrão.
- **Hospedagem**: desenvolvimento e testes locais primeiro. Publicação opcional em Streamlit Community Cloud ou Hugging Face Spaces apenas após verificar elegibilidade, limites, suspensão e política de dados. Não depender de hospedagem para concluir os projetos.
- **BigQuery Sandbox**: extensão opcional, não dependência do MVP; validar limites e eventuais exigências de faturamento antes de usar.

## 0.3 Estrutura de repositórios

```text
fintech-analytics-lab/
  README.md
  LICENSE
  docs/portfolio-index.md
  shared/
    synthetic_data_contracts/
    metric_definitions/
    design_tokens/
    qa_templates/
  projects/
    01-payment-intelligence/
    02-tpv-revenue-forecasting/
    03-experimentation-lab/
```

**Para publicação:** é aceitável transformar os três projetos em repositórios independentes. Evitar cópia manual divergente: compartilhar apenas pacotes pequenos, versionados, ou duplicar contratos de maneira explicitamente controlada. Cada projeto deve rodar de forma independente.

### Estrutura mínima dentro de cada projeto

```text
README.md
pyproject.toml
.env.example
.gitignore
LICENSE
data/README.md
configs/
src/
sql/
tests/
notebooks/
app/
reports/
docs/
  architecture.md
  data_dictionary.md
  metric_catalog.md
  assumptions.md
  limitations.md
  decisions.md
  validation_report.md
  publication_checklist.md
assets/screenshots/
.github/workflows/ci.yml
```

**Não versionar:** dados pessoais, credenciais, `.env`, dumps grandes, cache, modelos pesados, logs sensíveis. Preferir geradores e amostras pequenas; datasets reais somente se licença e termos permitirem redistribuição.

## 0.4 Convenções de dados e qualidade

1. Registrar origem, licença, período, atualização, unidade monetária e granularidade.
2. Identificar explicitamente `observed`, `synthetic` e `derived` em cada dataset/tabela relevante.
3. Fixar seed, versão do gerador, esquema e parâmetros de simulação.
4. Diferenciar **pagamento** de **tentativa de autorização** e evitar duplicar TPV em retries.
5. Evitar leakage temporal em forecasting e experimentos.
6. Manter métricas em um catálogo único: nome, fórmula, numerador, denominador, filtros, unidade, timezone, exceções.
7. Executar validação de tipos, nulidade, unicidade, chaves, limites, reconciliação e testes estatísticos.
8. Proibir claims como “aumentou a receita em X%” quando X vem de simulação; usar “impacto estimado sob as premissas Y”.

## 0.5 Fluxo operacional com Claude Code

**Para cada etapa:** (a) fornecer o prompt; (b) solicitar plano + arquivos afetados + riscos; (c) aprovar; (d) implementar; (e) executar testes; (f) registrar evidências; (g) revisar diff; (h) fazer commit. Não pedir implementação de todas as fases em uma única chamada.

### PROMPT GLOBAL | Guardrails e padrão de trabalho

```text
Act as a Senior Fintech Analytics Engineer, Data Scientist, Product Analyst, and technical reviewer. You are implementing a portfolio project for fintech data analyst roles.

Constraints:
- Windows local-first; Python, DuckDB, SQL, Streamlit, Plotly, pytest, Ruff and other free/open-source packages only.
- Do not provision paid cloud resources, buy subscriptions, create API keys or trigger billable services.
- Treat all synthetic data as synthetic, document generation assumptions and do not invent analysis results, screenshots, benchmark numbers, model accuracy or business impact.
- Build reproducible pipelines, deterministic seeds, CLI commands, typed functions where useful, tests and readable documentation.
- Use explicit event grain and KPI denominators. Prevent double counting, leakage, look-ahead bias and invalid causal claims.
- Prefer simple, testable architecture to overengineering. Use a consistent, accessible, responsive visual system without generic AI-dashboard styling.
- For every phase: (1) inspect existing repository, (2) propose implementation plan and acceptance criteria, (3) wait for approval, (4) implement, (5) run commands/tests, (6) report actual evidence and limitations, (7) suggest commit message. Do not claim success unless commands were run.
- Keep a decision log and changelog. Never overwrite user edits without review.

Start by reporting repository state, dependency plan, project risks and the smallest verifiable next milestone. Do not implement until I approve the plan.
```

### PROMPT TRANSVERSAL | Design system

```text
Read the supplied SA personal-brand design system and reference images before writing UI code. Do not invent brand colors, typography, logos, spacing or visual assets when source tokens are missing. If the brand package is not available, create neutral semantic design tokens and list the exact missing assets needed for brand integration.

Create responsive desktop/mobile dashboard layouts, coherent information hierarchy, filter controls, loading/empty/error states, accessible contrast, keyboard navigation and visible metric definitions. Include an About the Data panel with provenance, synthetic-data disclosures, assumptions and update timestamp. Separate UI design from metric calculations. Provide screenshot instructions for both desktop and mobile. Validate contrast and responsiveness; document any checks not actually executed.
```

---

# 1. PROJETO 01 | Payment Intelligence & Transaction Optimization

**Prioridade:** 1 | **Estimativa:** 25–40 horas, variável conforme experiência e revisões.  
**Pergunta executiva:** Onde as tentativas de pagamento falham, por quê, e quais mudanças podem melhorar a taxa de aprovação sem deteriorar custo, risco e experiência?

## 1.1 Escopo do MVP

- Gerar **500.000 tentativas** sintéticas inicialmente, com opção de escalar para 2 milhões via configuração.
- Modelar merchant, payment, payment_attempt, acquirer, payment_method, decline_code e settlement (opcional para reconciliação).
- Métricas: attempt authorization rate, final payment success, decline rate, retry recovery, approved TPV, processing cost, take rate/estimated net revenue somente quando os pressupostos financeiros estiverem definidos.
- Cortes por merchant, país, método, adquirente, faixa de valor, dia/hora, dispositivo (se modelado) e código de falha.
- Cenário contrafactual de roteamento **simulado**, sem afirmar causalidade ou uplift realizado.

## 1.2 Modelo de dados mínimo

| Entidade | Chave | Grão | Campos-chave |
|---|---|---|---|
| `dim_merchant` | `merchant_id` | 1 merchant | setor, país, porte, data de ativação |
| `dim_acquirer` | `acquirer_id` | 1 adquirente | região, custo-base |
| `fact_payment` | `payment_id` | 1 pagamento iniciado | merchant, timestamp, amount, currency, final_status |
| `fact_attempt` | `attempt_id` | 1 tentativa | payment_id, attempt_no, acquirer, result, decline_code, latency |
| `fact_settlement` | `settlement_id` | 1 evento de liquidação | payment_id, gross_amount, fee, net_amount, settlement_date |

**Regras:** a soma de TPV aprovado deve contar pagamentos concluídos uma vez, não todas as tentativas aprovadas; retentativas devem ser ordenadas e vinculadas a um mesmo `payment_id`; preservar timezone e moedas (não somar moedas diferentes sem FX e data-base).

## 1.3 Etapas, subetapas e critérios de aceite

### Etapa P1.1 | Descoberta, contratos e desenho

1. **P1.1.a** Definir cenário operacional (fintech PSP), personas e perguntas de negócio.
2. **P1.1.b** Definir grão das tabelas, eventos e estados possíveis.
3. **P1.1.c** Criar catálogo de métricas e política de moedas.
4. **P1.1.d** Definir cenários simulados e suas limitações.

**Aceite:** `docs/problem_statement.md`, `docs/data_dictionary.md`, `docs/metric_catalog.md`, `docs/assumptions.md` revisados; nenhuma métrica ambígua.

**PROMPT P1.1**
```text
For Project 01 Payment Intelligence, design a PSP payment-event analytics MVP. Define stakeholders, business questions, event lifecycle, entity relationships, data contracts, metric definitions with numerator/denominator and grain, currency/timezone policies, edge cases and risks. Distinguish authorization attempts, initiated payments, successful payments, retries and settlements. Produce a concise ERD (Mermaid), assumptions and acceptance tests. Do not code the generator yet. Wait for approval.
```

### Etapa P1.2 | Gerador sintético reproduzível

1. **P1.2.a** Criar parâmetros YAML: `seed`, merchants, acquirers, countries, volume, seasonality, retry policies.
2. **P1.2.b** Gerar merchants e pagamentos com distribuição de valores plausível.
3. **P1.2.c** Gerar tentativas condicionadas a merchant, adquirente, horário, método e perfil de risco simulado.
4. **P1.2.d** Inserir falhas intencionais controladas em dataset separado para testes de qualidade.
5. **P1.2.e** Exportar Parquet e manifest com seed, schema, contagens e checksums.

**Aceite:** mesmo seed gera dados idênticos; IDs únicos; FK válidas; relações coerentes; testes passam; volumes configuráveis; dados claramente marcados como sintéticos.

**PROMPT P1.2**
```text
Implement a deterministic, configurable synthetic PSP payments data generator using Python and Parquet. Default to 500,000 authorization attempts, configurable to 2,000,000. Create realistic nonuniform distributions, merchant heterogeneity, seasonality, acquirer differences, retry policies, decline-code taxonomy and processing costs. Model one payment with potentially multiple attempts. Document synthetic assumptions; do not calibrate to unspecified real-world industry benchmarks. Create a separate deliberately corrupted fixture for data-quality tests. Write unit/property tests for reproducibility, referential integrity, temporal ordering, amount validity, status transitions and correct payment-level deduplication. Provide CLI usage and actual test outputs.
```

### Etapa P1.3 | SQL avançado e marts

1. **P1.3.a** Ingestão em DuckDB, views staging e tabelas dimensionais.
2. **P1.3.b** SQL com CTEs, `ROW_NUMBER`, `LAG`, `LEAD`, agregações condicionais.
3. **P1.3.c** Criar marts: autorização por dia, performance por adquirente, decline reasons, recuperação por retry, cohorts de merchants.
4. **P1.3.d** Conferir reconciliação attempt-level vs payment-level.
5. **P1.3.e** Avaliar `EXPLAIN ANALYZE` em queries selecionadas sem inventar ganhos de performance.

**Aceite:** 12–20 consultas documentadas; testes de reconciliação; query plans registrados; nenhuma duplicação de TPV.

**PROMPT P1.3**
```text
Build a DuckDB analytics layer for the payment generator with staging models, dimensional marts and 15 advanced SQL analyses. Include CTEs, window functions, conditional aggregation, deduplication, retry sequencing, segmentation, decline taxonomy and daily trend calculations. Add SQL reconciliation tests proving payment-level TPV is not inflated by retries. Benchmark only queries actually executed, report dataset size, hardware limitations and observed EXPLAIN ANALYZE output. Deliver metric-to-query traceability and a SQL walkthrough for interview discussion.
```

### Etapa P1.4 | Diagnóstico e simulação de intervenções

1. **P1.4.a** Analisar padrões de recusas e segmentos com pior performance.
2. **P1.4.b** Distinguir falhas técnicas, recusas de emissor e outras categorias sintéticas.
3. **P1.4.c** Construir cenários de rerouting e retentativa com premissas explícitas.
4. **P1.4.d** Fazer análise de sensibilidade de autorização, custo e margem.
5. **P1.4.e** Documentar vieses e por que correlação observacional não identifica causalidade.

**Aceite:** relatório de diagnóstico com tabelas reproduzíveis, cenários e limitações; nenhuma promessa de uplift real.

**PROMPT P1.4**
```text
Analyze the generated payments dataset and build a transparent scenario simulator for retry/routing decisions. Separate descriptive findings from hypothetical interventions. Quantify approval-rate changes, incremental fees and estimated net contribution under explicit assumptions, with sensitivity ranges. Explain selection bias, counterfactual limitations and why the simulator is not causal proof. Generate a reproducible executive memo using actual computed outputs only; if execution is unavailable, leave placeholders and label them.
```

### Etapa P1.5 | Dashboard e QA

1. **P1.5.a** Construir Streamlit com visão executiva, performance de adquirentes, falhas, retries e cenários.
2. **P1.5.b** Implementar filtros que preservem denominadores corretos.
3. **P1.5.c** Criar About the Data e tooltips de métricas.
4. **P1.5.d** Testar casos vazios, grandes volumes, responsividade e acessibilidade básica.
5. **P1.5.e** Exportar relatório e screenshots somente da aplicação executada.

**Aceite:** dashboard executável por instrução única, screenshots reais, testes passando e checklist de UX preenchido.

**PROMPT P1.5**
```text
Create a polished, responsive Streamlit/Plotly payments analytics dashboard using the approved brand design tokens (or neutral placeholders if brand assets are missing). Tabs: Executive Overview, Authorization & Declines, Acquirer Performance, Retry Recovery, Scenario Simulator, About the Data. Add defensible KPI formulas, visible filters, clear denominators, data provenance, synthetic-data labels and methodology. Implement loading/empty/error states, performance caching and testable data services. Run the app locally and document exact commands and QA evidence. Do not fabricate screenshots.
```

---

# 2. PROJETO 02 | Fintech Revenue & TPV Forecasting Engine

**Prioridade:** 2 | **Estimativa:** 30–45 horas.  
**Pergunta executiva:** Qual será o fechamento de TPV, receita e margem, com que incerteza, e quais fatores explicam os desvios em relação ao orçamento?

## 2.1 Dados e limites de interpretação

- **Opção A, recomendada:** reaproveitar os pagamentos sintéticos do P1, agregando por dia/merchant, acrescentando calendário e premissas de take rate, fees, refunds e chargebacks sintéticos.
- **Opção B, complementar:** dataset público Olist (`https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`) para sazonalidade e análise de pagamentos de e-commerce; **não** afirmar que ele contém TPV de PSP, receita de adquirência ou margens observadas. Respeitar licença/termos e separar atributos derivados ou simulados.
- Janela de observação e horizonte de previsão devem ser configuráveis. Não usar variáveis futuras não disponíveis no momento do forecast.

## 2.2 Métricas e fórmulas

- `TPV`: soma de valores de pagamentos aprovados e contabilizados conforme regra de negócio; definir bruto/líquido e data de referência.
- `Take Rate`: receita de processamento / TPV elegível.
- `Net Revenue`: receita bruta menos estornos, incentivos e itens definidos no contrato de métricas.
- `Contribution Margin`: receita líquida menos custos variáveis definidos; não confundir com lucro líquido.
- `WAPE = sum(abs(actual - forecast)) / sum(abs(actual))`, indefinido se denominador zero.
- `Bias = sum(forecast - actual) / sum(actual)`, com convenção de sinal explícita.
- `Variance = actual - plan` (valor e %; tratar denominador zero).
- Avaliar também MAE, RMSE e interval coverage; não usar MAPE quando há zeros ou valores muito baixos sem ressalva.

## 2.3 Etapas e prompts

### Etapa P2.1 | Modelagem financeira e contratos

1. **P2.1.a** Definir TPV, receita, taxas, refunds, margem, período contábil e moedas.
2. **P2.1.b** Mapear dependências de dados, calendário e sazonalidade.
3. **P2.1.c** Criar tabela de premissas versionadas e orçamento fixado por data.
4. **P2.1.d** Definir públicos e decisões esperadas (FP&A, Comercial, Operações).

**Aceite:** fórmulas e reconciliações aprovadas, dicionário de dados, definição de cut-off e data de previsão.

**PROMPT P2.1**
```text
Design the business and analytical specification for a fintech TPV, revenue and contribution-margin forecasting engine. Use Project 01 synthetic payments as the primary data source, and treat Olist only as an optional public e-commerce dataset with explicitly limited interpretation. Define financial metric contracts, revenue recognition assumptions, refunds/chargebacks treatment, FX policy, reporting cut-off, historical availability, forecast horizons, scenario inputs and reconciliation checks. Produce a decision log and wait for approval before coding.
```

### Etapa P2.2 | Dataset analítico e engenharia de atributos

1. **P2.2.a** Construir séries diárias por merchant, segmento e consolidado.
2. **P2.2.b** Incluir calendário, feriados relevantes (fonte documentada), dia da semana e eventos sintéticos.
3. **P2.2.c** Criar defasagens e médias móveis sem vazamento de futuro.
4. **P2.2.d** Separar treino, validação e teste em ordem temporal.
5. **P2.2.e** Gerar orçamento e premissas de cenários com versão e timestamp.

**Aceite:** testes anti-leakage, ausência de duplicidades, consistência diária/mensal e rastreabilidade.

**PROMPT P2.2**
```text
Implement a reproducible DuckDB/Python daily fintech forecasting mart for TPV, revenue, take rate and contribution margin. Derive series from payment-level data with explicit financial assumptions, calendar features, time-safe lags and rolling windows. Version the budget and scenario assumptions by as-of date. Create chronological train/validation/test splits and anti-leakage tests. Reconcile daily, monthly, merchant and total figures. Document all synthetic and observed fields.
```

### Etapa P2.3 | Modelos, baselines e backtesting

1. **P2.3.a** Implementar naive, seasonal naive e moving average como baselines.
2. **P2.3.b** Implementar ETS e SARIMA (Statsmodels); modelos extras só se justificarem.
3. **P2.3.c** Aplicar rolling-origin backtesting em múltiplas janelas.
4. **P2.3.d** Comparar MAE, WAPE, Bias, custo computacional e estabilidade por horizonte.
5. **P2.3.e** Construir intervalos de previsão e avaliar cobertura empírica.
6. **P2.3.f** Selecionar modelo por evidência fora da amostra, não pela sofisticação.

**Aceite:** tabela comparativa real, splits auditáveis, baselines, parâmetros e seeds registrados; previsão reproduzível.

**PROMPT P2.3**
```text
Build a forecasting benchmark with naive, seasonal-naive, moving-average, ETS and SARIMA models. Use rolling-origin time-series backtesting with strict as-of-date feature availability and multiple forecast horizons. Compare MAE, WAPE, bias, interval coverage, runtime and stability; handle zeros and intermittent series explicitly. Select a champion model only from out-of-sample evidence. Log configuration, data version, splits, model versions and actual computed results. Never invent performance improvements or claim a complex model is better without evidence.
```

### Etapa P2.4 | Cenários, desvios e explainability

1. **P2.4.a** Definir cenários conservador, base e otimista como premissas, não intervalos estatísticos.
2. **P2.4.b** Simular variações de merchants ativos, ticket, transações e take rate.
3. **P2.4.c** Implementar decomposição documentada de volume/mix/taxa com tratamento de interações.
4. **P2.4.d** Identificar riscos de fechamento e alertas com limites configuráveis.
5. **P2.4.e** Criar relatório de forecast versus realizado versus orçamento.

**Aceite:** cenários reproduzíveis; decomposição fecha com variação total (ou resíduo explicado); incerteza separada de hipóteses de negócio.

**PROMPT P2.4**
```text
Implement a configurable business scenario engine (conservative/base/optimistic) for merchant growth, transaction volume, average ticket, take rate, variable costs and refunds. Distinguish scenario assumptions from statistical prediction intervals. Add a mathematically reconciled variance bridge between budget, forecast and actual, documenting interaction terms and any residual. Generate risk alerts with transparent thresholds. Provide an executive closing report grounded in computed values only.
```

### Etapa P2.5 | Dashboard, auditoria e publicação

1. **P2.5.a** Visões de fechamento, histórico, previsão, comparação de modelos e cenários.
2. **P2.5.b** Filtros por período, segmento, merchant e modelo.
3. **P2.5.c** Exibir data do último treino, data de corte, erro histórico e incerteza.
4. **P2.5.d** Criar relatório mensal executivo e exportação CSV.
5. **P2.5.e** Executar QA de fórmulas, intervalos, mobile e desempenho.

**Aceite:** dashboard local e relatórios reproduzíveis, testes, metodologia, screenshots reais.

**PROMPT P2.5**
```text
Build a professional Streamlit forecasting cockpit with Actual vs Budget vs Forecast, historical trends, prediction intervals, backtest comparison, scenario controls, a reconciled variance bridge and executive risk alerts. Clearly show data cut-off, training date, model version, forecast horizon and historical errors. Integrate approved brand tokens and About the Data documentation. Run the app, validate KPI consistency and generate a reproducible executive one-pager. Do not create fabricated screenshots or financial claims.
```

---

# 3. PROJETO 03 | Fintech Experimentation & A/B Testing Lab

**Prioridade:** 3 | **Estimativa:** 20–35 horas.  
**Pergunta executiva:** Uma mudança no checkout ou na autenticação aumenta conversão sem elevar falhas, custo ou risco?

## 3.1 Desenho experimental sugerido

- **Unidade de randomização:** merchant ou usuário, definida antes da simulação. Para checkout, usuário é possível; para roteamento com interferência entre transações, avaliar cluster por merchant.
- **Variantes:** A = fluxo atual; B = fluxo proposto.
- **Métrica primária:** conversão por unidade elegível (ex.: usuários que concluíram pagamento / usuários elegíveis randomizados), com definição precisa de janela e exposição.
- **Guardrails:** falhas técnicas, latência, chargeback simulado, custo por pagamento e abandono.
- **Riscos:** sample ratio mismatch (SRM), múltiplas comparações, peeking, sazonalidade, contaminação e efeitos heterogêneos.
- **Método:** análise frequentista com teste de duas proporções quando adequado; intervalos de confiança e análise de poder. Não confundir significância com relevância econômica.

## 3.2 Etapas e prompts

### Etapa P3.1 | Protocolo pré-experimento

1. **P3.1.a** Formular hipótese nula/alternativa e efeito mínimo detectável (MDE).
2. **P3.1.b** Definir unidade de randomização, elegibilidade e atribuição.
3. **P3.1.c** Fixar métrica primária, guardrails, alfa, poder, janela e regra de parada.
4. **P3.1.d** Documentar plano de análise antes de gerar resultados.

**Aceite:** protocolo versionado e bloqueado antes da análise; critérios de decisão explícitos.

**PROMPT P3.1**
```text
Design a preregistered A/B testing protocol for a fintech checkout optimization experiment. Specify business hypothesis, estimand, eligible population, randomization unit, allocation, exposure definition, primary conversion metric, guardrails, minimum detectable effect, alpha, statistical power, planned duration, sample-size calculation, stopping rules and analysis plan. Address repeated transactions, clustering, interference, SRM, multiple testing and missing events. Do not generate outcomes or peek at results before the protocol is approved.
```

### Etapa P3.2 | Simulador de eventos e atribuição

1. **P3.2.a** Gerar unidades elegíveis e alocação aleatória reproduzível.
2. **P3.2.b** Gerar eventos de exposição, início de checkout, tentativa e conclusão.
3. **P3.2.c** Definir efeito verdadeiro simulado em configuração separada do analista.
4. **P3.2.d** Criar cenários nulo, positivo, negativo, SRM e dados ausentes.
5. **P3.2.e** Testar consistência de atribuição, elegibilidade e contagens.

**Aceite:** reprodutibilidade; nenhuma unidade em ambos os grupos; cenários auditáveis; gerador separado da análise.

**PROMPT P3.2**
```text
Implement a deterministic synthetic experimentation event generator with eligible units, random assignment, exposure events, checkout attempts, successful payments and guardrail events. Keep the data-generating true effect in a separate simulation configuration that the analysis pipeline does not access. Create null, positive, negative, SRM and missing-data scenarios. Include tests for stable assignment, no cross-group leakage, event ordering, sample counts and unit-level metric definitions. Label all data as synthetic.
```

### Etapa P3.3 | Motor estatístico

1. **P3.3.a** Validar SRM e qualidade dos eventos antes de testar efeito.
2. **P3.3.b** Calcular taxas por grupo, diferença absoluta e relativa.
3. **P3.3.c** Calcular IC e p-value com método justificado.
4. **P3.3.d** Analisar poder, tamanho de amostra e MDE.
5. **P3.3.e** Avaliar guardrails, múltiplos testes e sensibilidade.
6. **P3.3.f** Executar simulações Monte Carlo para checar erro tipo I e poder quando viável.

**Aceite:** testes com cenários conhecidos, checagens estatísticas, resultados reproduzíveis e ressalvas metodológicas.

**PROMPT P3.3**
```text
Implement an auditable frequentist A/B testing analysis engine in Python using SciPy and Statsmodels. Validate sample ratio mismatch and data quality before inference. Compute group rates, absolute and relative uplift, justified confidence intervals, p-values, MDE, sample size and power. Handle clustered/repeated units appropriately or explicitly limit the design. Include guardrail analysis, multiple-testing policy, sensitivity checks and Monte Carlo verification of Type I error/power for controlled synthetic scenarios. Never interpret non-significance as proof of no effect.
```

### Etapa P3.4 | Economia e decisão de rollout

1. **P3.4.a** Traduzir variação de conversão em impacto econômico **simulado**.
2. **P3.4.b** Descontar custos adicionais, falhas e riscos de guardrails.
3. **P3.4.c** Definir decisão `launch`, `do not launch` ou `inconclusive` conforme protocolo.
4. **P3.4.d** Analisar heterogeneidade por segmento como exploratória, salvo pré-registro.
5. **P3.4.e** Redigir one-pager de decisão com limitações.

**Aceite:** decisão rastreável às métricas e critérios pré-definidos, sem causalidade extrapolada além do experimento.

**PROMPT P3.4**
```text
Build an experiment decision layer that translates observed synthetic A/B outcomes into an explicitly hypothetical economic model. Apply the preregistered launch criteria, primary metric, guardrails and uncertainty; output Launch, Do Not Launch or Inconclusive with reasons. Separate confirmatory results from exploratory segment analyses. Explain practical significance, possible implementation costs, confidence limits and external validity. Produce an executive decision memo without fabricated business impact.
```

### Etapa P3.5 | Dashboard e reprodutibilidade

1. **P3.5.a** Criar visão de experimento, funil, resultados, guardrails e QA.
2. **P3.5.b** Exibir protocolo, versão, seed, janela e contagens.
3. **P3.5.c** Visualizar diferenças com intervalos de confiança, não apenas barras.
4. **P3.5.d** Testar cenários nulo, positivo, negativo e SRM.
5. **P3.5.e** Gerar relatório de experimento e screenshots reais.

**Aceite:** análise end-to-end executável, testes passando, relatório e README com interpretação responsável.

**PROMPT P3.5**
```text
Create a professional Streamlit A/B testing dashboard with experiment overview, eligibility/exposure funnel, group metrics, effect estimates with confidence intervals, SRM and data-quality diagnostics, guardrails, sensitivity analysis, and a decision panel. Clearly identify synthetic datasets and show the preregistered protocol. Support reproducible scenario selection without changing the analysis rules after seeing outcomes. Apply approved brand tokens; run QA and capture only real application screenshots.
```

---

# 4. Integração, testes e auditoria final

## 4.1 Sequência de implementação recomendada

| Marco | Dependências | Evidência de conclusão |
|---|---|---|
| M0: setup comum | nenhuma | ambiente local, CI, lint, testes básicos |
| M1: P1 dados e SQL | M0 | gerador + DuckDB + reconciliação |
| M2: P1 dashboard | M1 | app + screenshots + relatório |
| M3: P2 dados e modelos | M1 | backtesting + comparativo real |
| M4: P2 dashboard | M3 | cenários + variance bridge |
| M5: P3 protocolo e simulação | M0 | protocolo pré-registrado + fixtures |
| M6: P3 análise e dashboard | M5 | testes estatísticos + decisão |
| M7: auditoria/publicação | M2, M4, M6 | QA final, README, posts, ativos |

## 4.2 Comandos de QA sugeridos

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check .
pytest -q
streamlit run app/main.py
```

> O caminho do app e extras `dev` devem refletir o `pyproject.toml` realmente implementado. Não executar comandos copiados cegamente em repositórios com outra estrutura.

## 4.3 Checklist de aceitação por projeto

- [ ] README com objetivo, decisões, screenshots e comandos executáveis.
- [ ] Licenças de código e dados verificadas; proveniência documentada.
- [ ] Seed, ambiente, versões e configuração registrados.
- [ ] Catálogo de métricas e granularidade sem ambiguidade.
- [ ] Testes unitários, integridade e reconciliação passando.
- [ ] Estatística/forecast com metodologia e limitações verificáveis.
- [ ] Dashboard responsivo, acessível e com filtros corretos.
- [ ] Sem credenciais, dados privados ou artefatos grandes indevidos.
- [ ] Resultados reais da execução, nunca números inventados.
- [ ] Relatório executivo revisado e consistente com outputs.
- [ ] Links públicos e demonstrações testados, quando publicados.

### PROMPT DE AUDITORIA INDEPENDENTE

```text
Act as a skeptical Senior Data Science and Analytics Engineering reviewer. Audit this project against its business requirements, data contracts, statistical validity, SQL grain, leakage risks, KPI reconciliation, model evaluation, reproducibility, security, licenses, accessibility and publication readiness. Inspect code and run available checks. Produce a severity-ranked report (Critical/High/Medium/Low) with file paths, reproduction steps, actual evidence, proposed fixes and remaining risks. Do not change files until I approve remediation. Do not mark any check passed unless it was executed.
```

---

# 5. PROMPT FINAL | Materiais para publicação e posts multicanal

**Quando executar:** somente após os três projetos terem código funcional, QA aprovado, screenshots reais, relatórios com resultados verificados e repositórios revisados. O prompt abaixo deve ser executado **por projeto** e, depois, uma vez para a coleção completa.

```text
Act as a Senior Technical Content Strategist, Developer Relations Writer, Data Analytics Hiring Manager, and Portfolio Editor.

CONTEXT
I have completed the Fintech Analytics Lab portfolio with three projects:
01 Payment Intelligence & Transaction Optimization
02 Fintech Revenue & TPV Forecasting Engine
03 Fintech Experimentation & A/B Testing Lab

First, inspect the actual repositories, READMEs, test reports, dashboards, notebooks, data dictionaries, validation evidence, screenshots and the approved SA brand design system. Do not assume that a feature, metric, result, deployment, license or screenshot exists. List missing evidence and request it before writing claims.

GOAL
Prepare a complete, polished, technically accurate publication kit for each project and a portfolio-level launch campaign, in Brazilian Portuguese and English. Audience: fintech data analyst recruiters, analytics engineering leads, product analysts, FP&A/forecasting teams and technical peers.

DELIVERABLES PER PROJECT
1. GitHub README in English: problem, context, data provenance, synthetic-data disclosure, architecture, setup, reproducibility, key metrics, SQL techniques, statistical methods, actual findings, limitations, screenshots, demo and repository links.
2. GitHub short description (max 160 characters), topics/tags, pinned-repository summary and social preview text.
3. Portfolio case study in English and PT-BR: business problem, analytical approach, tradeoffs, verified results, recommendation, tech stack, links and next steps.
4. LinkedIn launch post in PT-BR and English: compelling but non-clickbait opening, context, methodology, 2–3 verified findings, skills demonstrated, limitations, CTA and 3–5 relevant hashtags. Provide concise and detailed variants.
5. LinkedIn follow-up technical post: one meaningful technical decision (SQL grain/retries; forecast backtesting; A/B test design), with a code or methodology excerpt drawn from the repository.
6. Medium/DEV.to technical article (English, 1,000–1,500 words) with code snippets, diagrams, screenshots, citations/links to datasets, tradeoffs and reproducibility instructions. Include title, subtitle, excerpt, tags and SEO description.
7. Kaggle notebook introduction and structured narrative, only when datasets and license permit publication. Never upload synthetic data without prominent labeling.
8. Peerlist project card: short summary, problem, role, stack, technical highlights, verified outcomes and links.
9. Hugging Face Space listing text and model/app card, only if a compatible and actually deployed demo exists; otherwise produce a deployment checklist, not a live-link claim.
10. Visual asset shot list: desktop hero screenshot, mobile screenshot, KPI close-up, SQL architecture diagram, methodology diagram, social carousel (6 slides) and cover thumbnail. Use the approved brand tokens; do not invent images or screenshots. Provide exact captions and alt text.
11. 60–90 second video walkthrough script with timestamps, on-screen actions, captions and narration, using only features that actually exist.
12. Recruiter-ready interview briefing: 90-second pitch, STAR narrative, five technical questions and evidence-backed answers, key tradeoffs, limitations and future roadmap.

PORTFOLIO-LEVEL DELIVERABLES
A. Fintech Analytics Lab landing page copy (PT-BR/EN) with three project cards and a consistent narrative.
B. LinkedIn launch post introducing the collection without overstating fintech employment experience.
C. A four-week editorial calendar with publication order, channel, asset, CTA, dependency and repurposing notes.
D. Cross-project skills matrix mapping SQL, Python, forecasting, statistics, payments analytics, experimentation, data quality and business storytelling to actual evidence.
E. Publication checklist with URL verification, accessibility, spelling, license, synthetic-data disclosures, reproducibility and no fabricated claims.
F. Proposed file tree for all publication assets under publication/pt-BR and publication/en.

CONTENT RULES
- Use verified repository outputs only. For unavailable findings, insert [TO VERIFY] and explain exactly how to obtain evidence.
- Explicitly distinguish synthetic scenarios from real-world performance or achieved revenue.
- No invented employer/customer names, live links, performance benchmarks, citations or model accuracy.
- Avoid generic AI marketing language. Write like a rigorous practitioner who can explain business decisions and statistical limitations.
- Prefer concrete architecture, actual SQL examples, validation evidence and defensible business interpretation.
- Do not use em dashes in the final authored marketing copy.
- Keep visuals aligned with the provided SA design system; if missing, list required assets instead of guessing.
- Create draft files only; request approval before any external publishing, commits, deployments or account actions.

PROCESS
Phase 1: Inventory and evidence audit. Output a table of verified claims, sources and missing artifacts. STOP for approval.
Phase 2: Create content strategy, channel matrix, positioning and editorial calendar. STOP for approval.
Phase 3: Draft all deliverables as editable Markdown files with clear filenames. STOP for approval.
Phase 4: Review factual accuracy, SEO, bilingual consistency, visual system and channel requirements. Provide a final QA report and publishing checklist. Do not claim publication occurred.
```

---

# 6. Publicação por ondas e posicionamento

| Onda | Momento | Material recomendado | Objetivo |
|---|---|---|---|
| 1 | P1 após QA | GitHub + LinkedIn launch + case study | Evidenciar pagamentos e SQL avançado |
| 2 | 3–5 dias após P1 | DEV.to/Medium sobre retry e grão | Demonstrar profundidade técnica |
| 3 | P2 após QA | GitHub + forecast dashboard + LinkedIn | Evidenciar FP&A e séries temporais |
| 4 | 3–5 dias após P2 | Artigo de backtesting | Mostrar rigor metodológico |
| 5 | P3 após QA | GitHub + relatório de experimento | Evidenciar estatística e produto |
| 6 | 3–5 dias após P3 | Artigo de testes A/B | Mostrar julgamento analítico |
| 7 | Todos publicados | Landing Fintech Analytics Lab + post síntese | Posicionar portfólio especializado |

**Regra:** cadência é sugestão, não automatização de publicação. Programar posts somente depois de aprovar texto, links e evidências.

## 6.1 Matriz de entrevista: como conectar a experiência anterior

- **Procurement Analytics → Payments:** governança de fornecedores, indicadores, análise de falhas e risco operacional; não alegar experiência profissional prévia com adquirência se não houve.
- **Dashboards e KPIs → Forecasting:** rastreabilidade de premissas, análise de desvios e comunicação executiva.
- **Kaizen e melhoria de processos → A/B Testing:** hipóteses, medição de resultados e disciplina de validação; distinguir melhoria operacional observacional de experimento randomizado.

## 6.2 Critérios para decidir que o portfólio está pronto

Um projeto está pronto para divulgação quando: (1) uma pessoa externa consegue reproduzir a demonstração com instruções claras; (2) cada métrica relevante tem definição auditável; (3) há pelo menos uma decisão de negócio sustentada por outputs executados; (4) limitações e natureza sintética dos dados estão visíveis; (5) todos os links e materiais publicados correspondem ao que foi realmente implementado.

---

# 7. Próxima ação prática

1. Criar repositório local `fintech-analytics-lab` e copiar este blueprint para `docs/BLUEPRINT.md`.
2. Executar o **PROMPT GLOBAL** no Claude Code e aprovar somente a preparação do ambiente.
3. Executar **P1.1**; revisar definições de pagamento, tentativa e TPV antes de gerar dados.
4. Seguir as etapas sequencialmente, com commits e evidências em cada marco.
5. Executar o prompt de auditoria ao concluir cada projeto.
6. Executar o **PROMPT FINAL** apenas quando os resultados e materiais estiverem verificáveis.

**Observação de escopo:** este arquivo é um plano de implementação e publicação, não uma declaração de que os projetos foram desenvolvidos, testados ou publicados.
