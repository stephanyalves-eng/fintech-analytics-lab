# Auditoria independente final (M7) — P1, P2, P3

Revisão cética feita em 2026-11-21 contra o HEAD `997ed56`. **Nada foi corrigido**: este arquivo é o único artefato novo (além da linha no `PROGRESS.md`). Só marquei como PASS o que foi executado; o que não foi executado aparece em "Riscos remanescentes".

## Resumo
| Severidade | Qtde |
|---|---|
| Crítico | 0 |
| Alto | 1 |
| Médio | 4 |
| Baixo | 9 |

Nenhum número publicado nos três projetos falhou na reprodução. Os problemas são de **afirmações e documentação** (um README desatualizado e alegações de "pré-registro" que a história do git não sustenta), de **licença** e de **processo** (CI nunca executado).

## O que foi executado (evidência)
| Verificação | Resultado |
|---|---|
| Clone limpo do HEAD (`git clone`), `PYTHONPATH` no clone, sem `data/` | `ruff check .` limpo; `pytest -q`: **164 passed em 121 s** |
| P1 no clone: `generate` → `check` → `build` | 18 PASS, 0 FAIL; hashes das tabelas do manifest **idênticos** aos do ambiente original |
| P2 no clone: `cli pipeline` (23 s, 0 fits falhos) e `cli audit` | 17/17 PASS; hashes das 6 tabelas do mart **idênticos** ao original; campeões e orçamento v2 verificados e reutilizados |
| P3 no clone: `verify`, `generate`, `analyze` | `PASS protocol matches lock`; decisões: null INCONCLUSIVE, positive LAUNCH, negative DO NOT LAUNCH, srm e missing INVALID, como nos relatórios versionados (sem diferença de conteúdo) |
| Recálculo independente do backtest (série bruta em pandas → mesmos modelos) | 6 previsões (snaive, ETS, SARIMA × 2 origens) batem com as armazenadas, erro relativo máx. 5,6e-5 (arredondamento por pagamento) |
| Métricas do backtest recalculadas com numpy a partir das previsões diárias | 108 células, **0 divergências** |
| Vazamento: previsões com `date ≤ origin` no backtest | 0 linhas |
| `pip check`; `requirements-lock.txt` vs instalado (12 pacotes-chave) | sem conflito; versões idênticas |
| Segredos, PII, caminhos absolutos nos arquivos versionados | nenhum (único nome próprio: titular da LICENSE) |
| Artefatos grandes/dados versionados | nenhum `.parquet`/`.duckdb`; maior arquivo 544 KB (axe-core) |

## Alto
**H1 · README raiz desatualizado.** `README.md:7-8` lista P2 e P3 como "Planned", e P1 como "MVP done, audited (CI not yet run)". Os três projetos estão implementados e testados. Viola o critério de prontidão do blueprint (materiais publicados correspondem ao que foi implementado). *Evidência:* leitura do arquivo contra `PROGRESS.md`. *Correção:* atualizar a tabela (status, links para os READMEs de P2 e P3, comandos `pipeline`/`dashboard`).

## Médio
**M1 · Alegações de pré-registro sem respaldo na história do git.** O texto diz que limites de alerta e valores de cenário foram "fixados antes de olhar o T4". O commit `f0e985c` (P2.3) já contém `holdout_t4.csv/.md`; `scenarios.yaml` e `alerts.yaml` só aparecem em `ac884fc` (P2.4). O mesmo vale para as regras do orçamento v2, desenhadas depois de ver o fracasso do v1 (o `decisions.md` diz "sem olhar o T4"). Os números do v2 usam só dados ≤ 30/09 (verificado: A3a/A3b e teste de perturbação), mas **a escolha das regras foi informada pelo T4**. *Onde:* `configs/alerts.yaml:1`, `configs/scenarios.yaml:2`, `docs/scenarios_bridge.md`, `reports/executive_closing_report.md` (§2, §5), `app/app.py:319,382`, `closing.py:305`, `docs/decisions.md` (linha P2.5/orçamento v2). *Correção:* reescrever como "valores redondos escolhidos depois do holdout do P2.3 ter sido visto; não ajustados para cobrir o realizado" e qualificar o v2 como "regras escolhidas após observar a falha do v1". O que **é** verdadeiro e verificado: campeões congelados antes do holdout (`champions_b1.yaml` em `f0e985c` junto com o resultado, gerados na ordem backtest → freeze → holdout; o holdout recusa config ou dados alterados).

**M2 · Especificação P2 divergente do implementado.** `docs/assumptions.md` §E descreve cenários (volume −10%, take rate −5%, refund/chargeback ×1,5, **estresse de FX ±10%**) que não existem; foram implementados conservador/base/otimista em `scenarios.yaml`, sem estresse de FX. `docs/data_dictionary.md` cita tabelas inexistentes (`fct_forecast`, `ref_holiday`, `ref_events`; os arquivos reais são `fct_backtest_forecast`, `fct_holdout_forecast`, `dim_calendar`). *Correção:* alinhar os dois documentos ao código ou marcar o FX como não implementado.

**M3 · Aviso de terceiros ausente para o axe-core vendorizado.** Duas cópias de `axe.min.js` (MPL-2.0, Deque) em `projects/02-…/assets/vendor/` e `projects/03-…/assets/vendor/` (a do P2 duplica a do P3, 544 KB cada). O cabeçalho do arquivo preserva o copyright, mas nenhum documento do repositório declara a licença. Item "Licenças de código e dados verificadas" do checklist. *Correção:* `THIRD_PARTY_NOTICES.md` (axe-core, MPL-2.0, versão, origem, SHA-256) e, de preferência, uma única cópia compartilhada.

**M4 · CI nunca executado e cobertura parcial.** `.github/workflows/ci.yml` roda ruff, pytest e um smoke do P1; não roda `p2 pipeline/audit` nem `p3 analyze`. `git remote -v` vazio: nenhuma execução em runner Linux. Tudo foi validado só em Windows. *Correção:* publicar o repositório, acompanhar a primeira execução e acrescentar os smokes de P2/P3.

## Baixo
- **L1 · Low do P1 ainda abertos (L1–L6 da auditoria P1).** Confirmados por leitura: `diagnostics.py:434` usa `date.today()` no memo (diff diário sem mudança de dados); `.env.example` define `FAL_SEED=42` e `FAL_DATA_DIR` que nenhum código lê (a seed real é 20261121); nenhum check confere `settlement_date` = data local + lag do método (L6). L3–L5 seguem como descritos em `projects/01-…/reports/audit_report.md`.
- **L2 · Ruído de versionamento.** `reports/backtest_metrics.csv` contém `sec_per_fit` (tempo de máquina): toda reexecução suja o `git status` (216 linhas alteradas no clone, 108 linhas, só essa coluna). Além disso, 16 arquivos de relatório do P3 aparecem como modificados após regenerar no clone, mas `git diff --stat` não mostra mudança de conteúdo (só fim de linha; não há política `eol` no `.gitattributes`).
- **L3 · Código sem uso.** `features.py` (`make_features`, `assign_split`, `validate_splits` parcialmente) só é usado em testes: nenhum modelo consome as features anti-vazamento do P2.2; os modelos usam apenas a série `y`. Documentar como infraestrutura reservada ou remover.
- **L4 · Rótulo "as-of 2024-12-31" do orçamento v1.** A âncora usa janeiro/2025 (declarado em `assumptions.md` §D, mas não repetido no relatório nem no dashboard).
- **L5 · Aba "Closing" ignora os filtros laterais** (por desenho: trimestre congelado); a legenda lateral diz apenas "Filters change what is displayed".
- **L6 · Acessibilidade.** Teclado e leitor de tela não testados nos três dashboards (`[TO VERIFY]`); tema escuro não configurado; no P2 a primeira execução do axe reportou `color-contrast` que não reproduziu em duas execuções seguintes; mobile do P2 verificado só por 2 screenshots.
- **L7 · Portabilidade das ferramentas de captura.** `capture_screenshots.py`/`a11y_audit.py` procuram Edge/Chrome com caminhos de Windows (com fallback por nome de executável); o P2 importa o helper CDP do P3 por caminho de arquivo. Não testado em Linux/macOS.
- **L8 · Estatística aproximada, declarada.** Erro-padrão pareado da regra de campeão trata horizontes como independentes e origens se sobrepõem; um único trimestre de holdout. Está em `docs/methods.md`; permanece como limite.
- **L9 · Varredura de vulnerabilidades de dependências não realizada** (ferramenta não instalada; exigiria rede).

## Riscos remanescentes (não verificados)
CI em runner real; Linux/macOS; teclado e leitor de tela; varredura de vulnerabilidades; revisão jurídica de licenças além do `pip check`/cabeçalhos; qualquer afirmação publicada fora do repositório (posts, kits) — nenhuma foi criada ou conferida aqui.

## Ordem de correção sugerida (aguarda aprovação)
H1 → M1 → M2 → M3 → L2 (separar `sec_per_fit` do CSV versionado e fixar `eol`) → L1/L3/L4 → M4 (depois de publicar o repositório).

## Remediação (H1, M1–M3) — aplicada após aprovação
| Achado | Correção | Verificação executada |
|---|---|---|
| H1 | `README.md` raiz reescrito: status dos três projetos, links, comandos de execução, aviso de terceiros | leitura contra o estado real; comandos iguais aos dos READMEs dos projetos |
| M1 | Alegações "fixados antes de olhar o T4" reescritas em `alerts.yaml`, `scenarios.yaml`, `budget_v2_rules.yaml`, `app.py` (2), `scenarios_bridge.md` (2), `closing.py`, `decisions.md`, `methods.md`, README do P2; relatório de fechamento regenerado (`cli close`: 1 linha mudou) | `grep` por "fixados antes / before looking / sem olhar" em `projects`, `src`, `docs/decisions.md`: 0 ocorrências |
| M2 | `assumptions.md` §E descreve os cenários implementados e declara o estresse de FX como **não implementado**; `data_dictionary.md` lista as tabelas reais de `data/p2/` e remove `ref_holiday`, `ref_events`, `fct_forecast`, `assumptions_vN` | tabelas do dicionário conferidas contra `ls data/p2 data/p2/backtest` |
| M3 | `THIRD_PARTY_NOTICES.md` (axe-core MPL-2.0, versão, origem, SHA-256; licenças das dependências lidas do metadata instalado); **uma única** cópia em `shared/vendor/axe.min.js` (a duplicata do P2 foi removida); os dois `a11y_audit.py` e o `.gitattributes` apontam para ela | SHA-256 da cópia compartilhada confere com o fixado nos dois scripts |

Os demais achados (M4 e L1–L9) continuam abertos.

## Remediação dos baixos (L1–L9) — aplicada após aprovação
| Achado | Resultado | Verificação executada |
|---|---|---|
| L1 · Low do P1 | **L1** memo sem `date.today()` (usa o hash do dataset; teste de determinismo); **L2** `.env.example` não promete variáveis não usadas; **L3** teste numérico do custo S2 cap 4 calculado à mão (+ multiplicadores); **L4** rótulo/legenda de que M09 inclui tentativas do outro adquirente sob filtro; **L6** novo check `c14_settlement_date_lag` (+ 15º defeito injetado `settlement_date_wrong`); **L5** (teclado/leitor de tela) tratado em L6 abaixo | `cli check` na base real: 14 contrato + 5 reconciliação = 19 PASS; `cli diagnose` regenerado: só a linha da data mudou; `pytest tests/p1`: 65 passed |
| L2 · ruído de versionamento | `sec_per_fit` fora do CSV versionado (permanece no parquet); `.gitattributes` com `* text=auto eol=lf` (o ruído vinha de arquivos gerados com CRLF no Windows sobre índice LF) | `git status` após `pipeline` e `close`: só mudam os relatórios com conteúdo novo |
| L3 · código sem uso | `features.py` e o dicionário de dados declaram que é infraestrutura reservada, não consumida pelos modelos | leitura; nenhum resultado depende dela (`grep` em `src`) |
| L4 · rótulo do orçamento v1 | "as-of 2024-12-31, âncora em jan/2025" explicitado no relatório de fechamento, no About do dashboard, no one-pager e no README do P2 | `cli close` regenerou o relatório |
| L5 · aba Closing | legenda na aba e na barra lateral dizem quais abas respondem aos filtros; screenshots do P2 recapturados | screenshot revisado; AppTest passa |
| L6 · acessibilidade | **Parcial.** Novo `shared/keyboard_smoke.py` (Tab/setas via CDP) rodado nos 3 dashboards: sem armadilha de teclado, setas movem entre abas, relatórios em `reports/keyboard_smoke.md`. A grade de dados usa Tab internamente (até 9 presses no mesmo canvas). **Não resolvido:** passagem humana por teclado, leitor de tela, tema escuro | resultados nos três relatórios; uma 1ª versão da sonda (com blur/refocus) criou um falso "trap" no P2 e foi substituída por comparação de estilo sem alterar o foco |
| L7 · portabilidade | CDP/descoberta de navegador centralizados em `fintech_lab/shared/browser_cdp.py` (variável `FAL_BROWSER`, caminhos Windows/macOS/Linux, nomes no PATH); P1, P2 e P3 usam o módulo (P2 não importa mais o P3 por caminho de arquivo) | capturas e axe rodaram de novo nos 3 projetos com o módulo novo; screenshots de P1/P3 restaurados do git; **Linux/macOS continuam sem teste** |
| L8 · estatística aproximada | **Não alterado de propósito.** Trocar a regra de seleção do campeão depois de ver o holdout seria ajuste pós-hoc; o limite permanece documentado em `docs/methods.md` | — |
| L9 · vulnerabilidades | `pip-audit 2.10.1` (instalado num diretório temporário, fora do `.venv`) sobre `requirements-lock.txt` com `--no-deps --disable-pip`: **49 pacotes auditados, 0 vulnerabilidades conhecidas, 0 ignorados** na base de avisos do PyPI no momento da execução (2026-11-21). Só nomes e versões de pacotes saíram da máquina | saída JSON lida; resultado é pontual e deve ser repetido antes de publicar |
