# P1 · Relatório de auditoria independente

- Data: 2026-11-21 · Commit auditado: `de8aa1e` · Escopo: P1.1–P1.5 contra `docs/BLUEPRINT.md` §1 e checklist §4.3.
- Regra: nenhum arquivo do projeto foi alterado (só este relatório). Item só consta como "ok" se foi executado nesta auditoria.
- Reprodução: dados em pasta temporária com `generate`, `build`, `check`, `diagnose`, `corrupt` (comandos abaixo).

## Resumo
| Severidade | Qtde |
|---|---|
| Critical | 0 |
| High | 1 |
| Medium | 5 |
| Low | 6 |

## Evidência executada (passou)
| Verificação | Resultado |
|---|---|
| `ruff check --quiet .` | exit 0 |
| `pytest -q` | 59 passed (24 s), Python 3.12.10 |
| Determinismo | 2 execuções de `generate` com a seed 20261121 ⇒ mesmo `dataset_content_sha256` `fa2f4dc4…6dcf6` |
| `cli check` (dados limpos) | 18/18 PASS |
| `cli check` (fixture corrompida) | 16 FAIL; os 14 defeitos injetados estão listados no manifest |
| `cli diagnose` refeito | 9 CSVs e `diagnostic_memo.md` idênticos byte a byte aos versionados |
| Recálculo independente de S1 (SQL próprio, sem `scenarios.py`) | 6/6 direções iguais (ex.: ACQ_BR_A −435, ACQ_BR_B +321; cobertura 5.980 / 5.061) |
| TPV BRL | Σ `amount_brl` succeeded em `fct_payment` = Σ `m07_tpv_brl` em `mart_auth_daily` = 76.079.714,40; 0 FX nulo |
| Afirmação do memo "troca no retry independe do risco" | confirmada no código (`generator.py`, sorteio de `sw_p` só depende da categoria) |
| Segredos/credenciais nos arquivos versionados | nenhum encontrado (busca por api key, secret, token, password, caminhos de usuário) |
| Licença | MIT (código); dados 100% sintéticos gerados localmente |

**Não executado nesta auditoria:** escala 2M, Streamlit ao vivo, captura de screenshots, CI (sem remote). Os números de PROGRESS para esses itens continuam sendo os da sessão anterior.

## Achados

### High
**H1 · Projeto não está pronto para publicação: falta README do P1 e o README raiz está desatualizado**
- Arquivos: `README.md` (P1 aparece como "Planned"); não existe `projects/01-payment-intelligence/README.md`.
- Evidência: o checklist §4.3, item 1, pede README com objetivo, decisões, screenshots e comandos. Hoje isso está espalhado em `docs/dashboard_qa.md`, `reports/diagnostic_memo.md` e `docs/sql_walkthrough.md`.
- Correção: criar o README do P1 (pergunta executiva, arquitetura, comandos de uma linha, 2–3 screenshots, link para memo/QA/limitações) e atualizar o status no README raiz.

### Medium
**M1 · `build` e `dashboard` não bloqueiam dados que violam o contrato**
- Arquivos: `src/fintech_lab/p1_payments/cli.py` (`_build`, `_dashboard`), `sql/marts/01_core.sql` (dedup defensivo em `int_payment`).
- Reprodução: `cli corrupt --out <tmp>/c` e depois `cli build --data <tmp>/c --db <tmp>/c.duckdb` ⇒ `exit 0`.
- Risco: o `ROW_NUMBER` em `int_payment` esconde `payment_id` duplicado em silêncio, e o dashboard abriria sobre marts errados.
- Correção: rodar os checks de contrato dentro do `build` e falhar com exit ≠ 0 (com uma flag `--skip-checks` explícita para o fixture).

**M2 · Conclusões de contribuição em S1 sem incerteza**
- Arquivos: `scenarios.py::simulate_s1`, memo §2 (S1).
- Evidência: o IC 95% cobre só Δ pagamentos aprovados. O memo afirma que "a contribuição estimada cai" em 3 direções com magnitudes de R$ 350 a R$ 1.606, sem intervalo. A variância amostral de `cost_gap_per_payment` e do ticket não entra.
- Correção: bootstrap estratificado (seed fixa) para Δ TPV e Δ contribuição e, no memo, reportar o sinal só quando o IC exclui zero.

**M3 · Ambiente não fixado; reprodutibilidade entre máquinas não garantida**
- Arquivos: `pyproject.toml` (só limites inferiores, p. ex. `pandas>=2.2`), sem lock; manifest registra só `generator_version`.
- Evidência: o ambiente local usa pandas 3.1.1, numpy 2.5.5, duckdb 2.0.1 e streamlit 1.67.0. Um `pip install` com pandas 2.2 é permitido e não foi testado. O hash do dataset depende do RNG do numpy e da escrita do pyarrow.
- Correção: gerar `requirements-lock.txt` (`pip freeze`) e registrar as versões de numpy/pandas/pyarrow/duckdb no manifest.

**M4 · CI nunca rodou**
- Arquivos: `.github/workflows/ci.yml`; `git remote -v` vazio.
- Evidência: o PROGRESS diz "CI criado", mas não há execução no Ubuntu. Diferenças entre Linux e Windows (timezone, paths) não foram testadas.
- Correção: publicar o repo e anexar o link da primeira execução verde. Até lá, descrever como "CI configurado, não executado".

**M5 · Mart de cohorts é degenerado**
- Arquivos: `sql/marts/02_marts.sql` (`mart_merchant_cohorts`), `sql/analyses/analyses.sql` q12, `docs/sql_walkthrough.md`.
- Evidência: `merchant_retention` = 1,0 em todos os cohorts e meses consultados, porque o gerador não modela churn. O cohort 2025-01 tem 185 merchants que já estavam ativos antes do período (censura à esquerda) misturados com os novos.
- Correção: modelar churn no gerador ou rotular q12 como "demonstração de SQL; retenção = 1 por construção", e usar `activation_date` para separar os merchants pré-existentes.

### Low
- **L1 · Memo não determinístico:** `diagnostics.py` grava `date.today()` no memo; rodar em outro dia gera diff sem mudança nos dados. Usar a data do manifest ou aceitar `--as-of`.
- **L2 · `.env.example` engana:** `FAL_DATA_DIR`/`FAL_SEED` não são lidos por nenhum código, e `FAL_SEED=42` contradiz a seed 20261121. Remover ou implementar.
- **L3 · S2 cap 4 sem teste numérico do custo:** o custo usa a taxa média do país (inclui a parte fixa) × ticket elegível. Só há teste de monotonia em δ. Adicionar um caso calculado à mão, como existe para S1.
- **L4 · Custo sob filtro de adquirente (grão pagamento):** M08/M09 incluem tentativas feitas no outro adquirente. A regra está documentada para o filtro, mas o rótulo do KPI de custo não avisa.
- **L5 · Acessibilidade parcial:** teclado e leitor de tela continuam `[TO VERIFY]`; tema escuro não configurado (`docs/dashboard_qa.md`).
- **L6 · Settlement sem check de data:** nenhum check confere `settlement_date` = data local + `settlement_lag_days` do método.

## Riscos remanescentes (aceitos por desenho)
- Circularidade: todos os efeitos "descobertos" foram plantados no YAML (o memo já declara isso).
- S1 é quase não viesado só porque o gerador sorteia a troca de adquirente; em produção, a comparação seria confundida.
- Take rate/contribuição dependem de MDR sintético `[TO VERIFY]`.
- 436 tentativas caem em data local diferente da do pagamento; pela regra do catálogo, contam na data de criação do pagamento.

## Comandos usados
```powershell
python -m fintech_lab.p1_payments.cli generate --out <tmp>/a      # 2x, comparar sha256
python -m fintech_lab.p1_payments.cli build --data <tmp>/a --db <tmp>/a.duckdb
python -m fintech_lab.p1_payments.cli check --data <tmp>/a
python -m fintech_lab.p1_payments.cli diagnose --db <tmp>/a.duckdb --data <tmp>/a --out <tmp>/rep
python -m fintech_lab.p1_payments.cli corrupt --out <tmp>/c
python -m fintech_lab.p1_payments.cli check --data <tmp>/c
python -m fintech_lab.p1_payments.cli build --data <tmp>/c --db <tmp>/c.duckdb   # M1
```

## Remediação (2026-11-21, aprovada: H1 e M1–M5)
| Achado | Status | Correção | Evidência executada |
|---|---|---|---|
| H1 | corrigido | `projects/01-payment-intelligence/README.md` (objetivo, comandos, decisões, limitações, screenshot); README raiz com status e link | arquivos revisados; screenshots recapturados do app em execução (`capture_screenshots.py`) |
| M1 | corrigido | `cli build` roda checks de contrato antes dos marts e de reconciliação depois; em falha remove o `.duckdb` e sai com 1; `--skip-checks` explícito; `dashboard` não sobe se o build falhar | `tests/p1/test_cli.py` (4 testes); build no dataset padrão imprime "contract + reconciliation checks passed" |
| M2 | corrigido | `s1_payments` (grão pagamento) + `scenarios.s1_bootstrap`: 500 reamostragens dentro de estrato × braço, seed 20261121; IC de Δ TPV/fee/custo/contribuição em `s1_result.csv` e no memo; o memo só afirma o sinal quando o IC exclui zero | agregação de `s1_payments` = `s1_reroute_base` (teste); bootstrap determinístico e degenerado sem variação (testes). **Mudou uma conclusão:** a queda de contribuição em ACQ_MX_A agora é indefinida (IC R$ −1.725 a R$ 895); ACQ_BR_B e ACQ_CL_B continuam abaixo de zero |
| M3 | corrigido | `requirements-lock.txt` (pip freeze); manifest grava `environment` (python, SO, numpy, pandas, pyarrow, duckdb, pyyaml, scipy) | venv novo criado só a partir do lock: `pip check` ok e `generate` reproduz `fa2f4dc4…6dcf6` |
| M4 | parcial | CI instala pelo lock e roda `generate` + `check` + `build` do P1; status declarado como "não executado" no README | **não executado**: o repositório continua sem remote; Linux não testado [TO VERIFY] |
| M5 | corrigido (rotulado) | cohort = mês de **ativação**; merchants anteriores à janela ficam no cohort `pre_window` (177 de 300); `cohort_size` vem de `dim_merchant`; retenção ≈ 1 rotulada como "por construção" (sem churn no gerador) no SQL, no walkthrough e no README | `test_cohorts_use_activation_and_flag_left_censoring` |

Pós-remediação: `ruff check` ok; `pytest -q` com 69 passed (61 s; o bootstrap aumentou o tempo da suíte). `cli check` passou 18/18, e o hash do dataset não mudou. Os Low L1–L6 continuam abertos.
