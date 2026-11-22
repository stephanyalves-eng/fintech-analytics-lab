# P2.5 — QA do dashboard, relatório e auditoria

Tudo abaixo foi executado nesta máquina; os números vêm das execuções.

## Testes automatizados (`pytest -q tests/p2`)
- Pipeline completo (mart → backtest → holdout → orçamento v2 → fechamento) sobre um P1 pequeno em diretórios temporários: os arquivos congelados são criados no temporário, e um segundo run os **verifica e reutiliza** (campeões e one-pager idênticos).
- **Consistência de KPI:** TPV de T4 do relatório = soma do total diário; histórico sem filtro = total; soma por país = total; semana/mês preservam TPV e net revenue; net/contribuição derivados = colunas do mart; seleção de merchants é subconjunto estrito; pontes com resíduo < 1e-3.
- **AppTest (Streamlit):** 8 abas, selo SYNTHETIC, faixa de cut-off/treino/horizonte/versões, filtros (país, grão, métrica, alvo, modelo), presets e slider de cenário, estado de artefatos ausentes (erro claro, sem exceção).
- **Auditoria independente** (`cli audit`, `reports/audit_p2.md`): recalcula do Parquet bruto do P1 com pandas (sem DuckDB/SQL do P2) TPV, fee e custo (ano e T4, por país), refaz o nível e o take rate do orçamento v1 (só janeiro) e o crescimento do v2 (abril→setembro), confere que o backtest não avalia datas após o as-of, que os campeões decorrem do WAPE composto recalculado, que o WAPE do holdout bate e que nenhuma tabela é `observed`. Base real: **17/17 PASS**. A tolerância de A2a é meio centavo por pagamento: o mart arredonda o valor em BRL por pagamento (contrato do P1) e o recálculo em float não.

## Intervalos
Cobertura medida, não assumida (backtest, validação): SARIMA/TPV total 77–80% (nominal 80%) e 93–94% (95%). No holdout T4 a cobertura de 80% cai para 19,6% no TPV total: o intervalo só vê o ruído do histórico. A aba "Forecast & intervals" mostra isso ao lado do aviso.

## Mobile e visual
Screenshots reais (Edge headless, app rodando) em `assets/screenshots/`: 9 desktop (1440 px) e 2 mobile (390 px: Closing e Variance bridge). Na revisão visual a faixa de métricas do topo truncava valores (`2025-0...`); foi trocada por cartões HTML e recapturada. Uma captura intermediária saiu quebrada (módulos JS falharam durante a recarga do servidor); foi descartada, o servidor reiniciado e tudo recapturado. Em mobile as tabelas largas rolam na horizontal.

## Desempenho (medido)
Carga dos artefatos + recálculo das tabelas de fechamento: 1,4 s; primeira renderização completa (AppTest): 3,7 s; re-execução após mudar um filtro: 0,3 s; filtro de histórico: 3,6 ms (total) e 6,7 ms (20 merchants); reagrupar para mês: 4,5 ms. Pipeline completo na base real: ~36 s (backtest 24 s com 8 processos).

## Acessibilidade (axe-core 4.10.2, WCAG 2.0/2.1 A e AA, 8 abas)
Duas execuções consecutivas: 0 violações e 1 item `incomplete` por aba (revisão manual). Uma execução anterior, feita logo após o servidor recarregar, reportou 1 regra `color-contrast` por aba sem registrar os nós; não reproduziu nas duas seguintes (provável estado transitório de renderização) `[TO VERIFY]`. Navegação por teclado e leitor de tela: ver a seção seguinte.

## Relatório e exportações
`cli close` gera `executive_closing_report.md`, `executive_one_pager.html` (HTML autônomo, imprimível, só valores calculados), `monthly_actual_vs_budget.csv` e `p24_*.csv`; o dashboard exporta CSV por tabela e o one-pager. Marca neutra (tokens provisórios) até o design system ser fornecido.

## Teclado (automatizado, parcial)
67 candidatos interativos na primeira aba; 174 pressionamentos de Tab, 58 paradas de foco distintas, nenhuma armadilha (a maior sequência foi de 9 Tab no mesmo `canvas`: as tabelas do Streamlit são grades em canvas que usam Tab para percorrer as células e depois liberam o foco), ArrowRight move o foco entre abas. A heurística de indicador de foco não detectou mudança de estilo no contêiner `main` e em 2 `canvas` (falsos negativos possíveis; um screenshot com foco em um combobox mostrou o anel azul visível). Teste de teclado **automatizado e parcial** (`python -m fintech_lab.shared.keyboard_smoke`, relatório em `reports/keyboard_smoke.md`): sem armadilha de teclado, setas movem o foco entre abas, foco alcança os controles por Tab. Navegação humana por teclado e leitor de tela seguem `[TO VERIFY]`.
