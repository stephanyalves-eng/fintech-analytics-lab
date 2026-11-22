# Passagem manual de acessibilidade (teclado e leitor de tela)

O repositório só tem verificação **automatizada e parcial** (axe-core e `keyboard_smoke`, ambos no CI). Esta lista descreve a passagem humana que falta; ela não foi executada e nenhum resultado abaixo foi preenchido. Quem executar deve registrar data, navegador, leitor de tela e versão na tabela final.

## Preparação
```powershell
python -m fintech_lab.p1_payments.cli dashboard     # :8501
python -m fintech_lab.p3_experiments.cli dashboard  # :8502
python -m fintech_lab.p2_forecasting.cli dashboard  # :8503
```
Leitores de tela gratuitos: NVDA (Windows), Narrator (Windows, já instalado), VoiceOver (macOS). Teste sem mouse.

## A. Teclado (para cada dashboard, cada aba)
1. `Tab` percorre filtros, abas, botões de ajuda, expansores e botões das tabelas em ordem lógica (esquerda→direita, cima→baixo) e nunca fica preso.
2. Setas ←/→ trocam de aba; `Enter`/`Espaço` ativam; o conteúdo da aba selecionada recebe foco de forma previsível.
3. O foco é **sempre visível** (anel, borda ou fundo distinto) em: seletores, datas, rádios, sliders, botões de download, expansores.
4. Seletores com busca (combobox) abrem e fecham só com teclado (`↓`, `Enter`, `Esc`).
5. Tabelas (grades em canvas): `Tab` entra, setas percorrem células, `Esc`/`Tab` saem; alternativa em texto existe (botão "Download as CSV" e/ou tabela em "Data table").
6. Gráficos Plotly: a informação principal também está em tabela ou texto (verificar cada gráfico).
7. Zoom do navegador em 200% e largura de 320 px: sem perda de conteúdo nem rolagem horizontal da página inteira.

## B. Leitor de tela
1. Título da página e selo **SYNTHETIC DATA** são lidos logo no início.
2. Cada controle tem nome acessível (rótulo, não só "combobox"); estados (selecionado, expandido) são anunciados.
3. Cards de KPI são lidos como "rótulo, valor, variação" na ordem correta; setas/cores de variação têm equivalente em texto (+/−).
4. Mensagens de erro, aviso e estado vazio (`st.error`, `st.warning`, `st.info`) são anunciadas.
5. Alertas de risco: a severidade é lida como texto (red/amber/ok), não só por cor.
6. Gráficos: ao menos o título e uma descrição/tabela equivalente são encontrados.

## C. Cor e tema
1. Informação nunca depende só de cor (verificado em parte por design; confirmar nos gráficos de barras e na ponte).
2. Tema escuro: **não implementado de propósito** (os tokens de design são provisórios, enquanto o design system não é fornecido). Reabrir quando houver tokens oficiais: criar variante escura, revalidar contraste (axe) e screenshots.

## Registro (preencher)
| Data | Pessoa | Navegador | Leitor de tela (versão) | Dashboard | A (teclado) | B (leitor) | Problemas encontrados |
|---|---|---|---|---|---|---|---|
| | | | | P1 | | | |
| | | | | P2 | | | |
| | | | | P3 | | | |

Resultado só vira "verificado" nos READMEs depois de esta tabela estar preenchida e os problemas tratados.
