# P1 · Dashboard: execução e QA (P1.5)

## Como rodar (instrução única)
```powershell
.\.venv\Scripts\Activate.ps1
python -m fintech_lab.p1_payments.cli dashboard      # gera e faz o build se faltar; abre :8501
```
Screenshots reais do app em execução (Edge headless via CDP; o script falha se a aba não abrir ou se houver exceção na tela):
```powershell
python projects/01-payment-intelligence/app/capture_screenshots.py
```
Saída: `assets/screenshots/0N_<aba>_{desktop,mobile}.png` (1440 px e 390 px).

## Arquitetura
- `src/fintech_lab/p1_payments/dashboard_data.py`: serviços de dados puros (filtros → SQL parametrizado), testáveis sem Streamlit.
- `app/app.py`: só UI. DuckDB em modo `read_only`, conexão em `st.cache_resource` e consultas em `st.cache_data`.
- Simulador: `scenarios.py` (S1/S2), o mesmo código do memo `reports/diagnostic_memo.md`.

## Checklist de UX/QA (evidência de 2026-11-21)
| Item | Status | Evidência |
|---|---|---|
| 6 abas: Executive, Authorization & Declines, Acquirer, Retry, Scenario, About | ok | `tests/p1/test_app.py::test_renders_all_tabs`; screenshots 01–06 |
| Denominadores preservados sob filtro | ok | `test_dashboard_data.py`: partição por país soma ao total; M02 = razão de somas; filtro de adquirente por grão |
| Denominador visível | ok | legenda "Denominators: M02 = N payments · M01 = N attempts"; o card do M05 mostra o denominador |
| Tooltips de métricas | ok | `help=` nos KPIs (teste verifica os 4 principais) e no filtro de data |
| Rótulo de dado sintético e proveniência | ok | badge no topo; About mostra seed, SHA-256 e linhas do manifest |
| Estado vazio | ok | `test_empty_state` (cartão de crédito + PIX_BR ⇒ 0 linhas, mensagem `st.info`) |
| Estado de erro (sem warehouse) | ok | `test_missing_db_error_state` |
| Estado de carregamento | ok | `st.spinner` na consulta principal |
| Grandes volumes (2M tentativas) | ok | build 27,4 s; consultas do dashboard sem cache de 12 a 62 ms (kpis 36 ms, declines 62 ms). Máquina local; não é benchmark |
| Responsividade | ok | `01_executive_overview_mobile.png` (390 px): os KPIs empilham e os gráficos se ajustam à largura |
| Acessibilidade básica | parcial | paleta categórica validada (CVD ΔE ≥ 9,1 entre adjacentes); 3 cores com contraste < 3:1 ⇒ cada gráfico tem tabela de dados; legenda + rótulos (cor nunca é o único canal). Leitor de tela e teclado **não auditados** [TO VERIFY] |
| Sem dual axis; cor segue a entidade | ok | mapas fixos país/adquirente/categoria no `app.py` |

## Limitações conhecidas
- O simulador roda sobre o dataset inteiro; os filtros da barra lateral não se aplicam nele (o aviso aparece na aba).
- O `st.cache_data` não invalida quando o código de `dashboard_data.py` muda: reinicie o servidor após editar.
- Tema escuro não foi configurado (o tema claro é fixado via `--theme.base light`).

## Teclado (automatizado, parcial)
55 candidatos interativos na primeira aba; 150 pressionamentos de Tab, 39 paradas de foco distintas, nenhuma armadilha de teclado, ArrowRight move o foco entre abas. Os botões da barra de ferramentas das tabelas (mostrar/ocultar colunas, baixar CSV, buscar, tela cheia) não receberam foco por Tab nesta execução (causa não investigada). Teste de teclado **automatizado e parcial** (`python -m fintech_lab.shared.keyboard_smoke`, relatório em `reports/keyboard_smoke.md`): sem armadilha de teclado, setas movem o foco entre abas, foco alcança os controles por Tab. Navegação humana por teclado e leitor de tela seguem `[TO VERIFY]`.
