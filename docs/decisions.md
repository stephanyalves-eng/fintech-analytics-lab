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
| 2026-11-21 | P1.2: volume = maior prefixo de pagamentos i.i.d. com Σ tentativas ≤ alvo | Mantém o alvo de tentativas sem enviesar a amostra |
| 2026-11-21 | P1.2: risco por pagamento é latente (não exportado) | Confundidor oculto realista; evita "vazar" a resposta |
| 2026-11-21 | P1.2: dinheiro em Parquet como decimal(18,2), FX decimal(18,8) | Somas exatas nos checks de reconciliação |
| 2026-11-21 | P1.3: checks e análises como blocos `-- name:` em arquivos SQL | SQL legível/versionado; o runner Python só conta linhas violadoras |
| 2026-11-21 | P1.4: S1 como mistura θ (sucesso **e** custo); θ = 0 é o cenário nulo | Evita mudar custo sem mudar comportamento; sensibilidade coerente |
| 2026-11-21 | P1.4: S2 cap 4 rotulado como extrapolação (propensão observada 2→3 × M01 da 3ª × δ) | A 4ª tentativa nunca foi observada |
| 2026-11-21 | P1.5: filtro de adquirente = adquirente da tentativa (grão tentativa) / da 1ª tentativa (grão pagamento) | Um pagamento pode passar por 2 adquirentes; o denominador fica explícito |
| 2026-11-21 | P1.5: paleta categórica fixa por entidade (validada para CVD) + tabela por gráfico | Contraste < 3:1 em 3 cores; a cor não é o único canal |
| 2026-11-21 | P1.5: screenshots via Edge headless + CDP (lib `websockets`, já dependência do Streamlit) | Telas reais sem nova dependência; falha se houver exceção |
| 2026-11-21 | Auditoria P1: `build` bloqueado por checks de contrato/reconciliação (`--skip-checks` só para fixtures) | Dados fora do contrato não podem alimentar marts/dashboard em silêncio |
| 2026-11-21 | Auditoria P1: IC bootstrap (500 reps, estrato × braço, seed fixa) para Δ TPV/contribuição de S1; sinal só quando o IC exclui zero | O IC antigo cobria só Δ aprovados; a conclusão sobre margem não tinha suporte |
| 2026-11-21 | Auditoria P1: `requirements-lock.txt` + versões no manifest | O hash só é garantido no mesmo ambiente |
| 2026-11-21 | Auditoria P1: cohorts por mês de ativação, `pre_window` separado; churn não modelado (retenção ≈ 1 rotulada) | Evita censura à esquerda; modelar churn mudaria todos os outputs |
| 2026-11-21 | P3.1: experimento = 3DS baseado em risco (B) vs. 3DS obrigatório (A), unidade usuário, hash SHA-256 com salt, 50/50 | Trade-off real entre conversão e fraude; métrica primária no grão usuário evita clusters |
| 2026-11-21 | P3.1: n = máximo entre primária e guardrails de proporção (poder ≥ 0,80 em cada) | Com o n da primária (9.335), o G1 teria poder ≈ 0,40 e o Launch seria quase sempre inconclusivo |
| 2026-11-21 | P3.1: guardrails via interseção-união (todos precisam passar), sem Holm | A IUT controla α sem ajuste; Holm (proposto no plano) seria desnecessariamente conservador |
| 2026-11-21 | P3.1: lock por SHA-256 de texto normalizado em LF; mudança só via `--amend` registrado | Checkout CRLF no Windows não quebra o hash; emendas ficam auditáveis |
| 2026-11-21 | P3.2: efeito verdadeiro em `simulation.yaml`; análise proibida de importá-lo (teste AST) | Separação gerador × análise exigida no aceite |
| 2026-11-21 | P3.2: trilha incompleta = aprovação sem tentativa ou lacuna de numeração | Detectável só por eventos; fração é piso |
| 2026-11-21 | P3.3: G1/G2/G4 por razão com variância por usuário (delta); G3 bootstrap por usuário | Tentativas/pagamentos repetidos não são independentes |
| 2026-11-21 | P3.4: economia hipotética em `economics.yaml`, fora do lock, sem efeito na decisão | O protocolo define a regra; economia só informa |
| 2026-11-21 | P3: Ruff ignora E501 em `p3_experiments` e no app P3 | Literais densos com `# fmt: skip` |
| 2026-11-21 | P3: G4 (poder 0,35 sem degradação) e G2 (tipo I 0,028) ficam documentados, sem emenda ao protocolo | Decisão do usuário: só documentar; n, margem e método do intervalo permanecem como travados |
| 2026-11-21 | Auditoria P3: usuário com trilha incompleta não conta como conversão; análise exige `observation_end` ≥ dia 65 | Alinhar o código ao protocolo §7.3 e à regra de data de análise, sem emenda ao protocolo |
| 2026-11-21 | P2.1: só dados do P1 (Olist fora do MVP); TPV = M07 do P1; receita por data de criação local (accrual) | Um único TPV; evita reinterpretar dado público como PSP |
| 2026-11-21 | P2.1: cut-off/as-of 2025-09-30, horizonte T4/2025 (92 d), backtest 7/30/90 d; jan/2026 excluído (fuso) | Decisão do usuário; T4 tem realizado para avaliar |
| 2026-11-21 | P2.1: refund, chargeback, incentivo e custo variável sintéticos e determinísticos, reconhecidos na data do evento | P1 não tem refund/chargeback; rótulo `synthetic` |
| 2026-11-21 | P2.1: orçamento v1 (as-of 2024-12-31) fixo, com erro proposital (crescimento +4% a.m., take rate sem mix) | Decisão do usuário; dá desvios a explicar no P2.4, rotulados sintéticos por construção |
| 2026-11-21 | P2.1: sem MAPE; WAPE/Bias por razão de somas; Bias > 0 = superprevisão; Variance = actual − plan | Séries por merchant têm zeros |
| 2026-11-21 | P2.2: mart sobre as tabelas core do P1 (mesma conexão DuckDB), arredondamento só no grão mais baixo | Reconciliação exata dia/mês/merchant/total e contra M07/M08 do P1 |
| 2026-11-21 | P2.2: custo de processamento na data de criação do pagamento (regra do P1), não na da tentativa | R06 = M08 do P1; contrato F09 ajustado |
| 2026-11-21 | P2.2: refund/chargeback sorteados por pagamento (XOR) com seed própria; refund = valor total; eventos após 2025-12-31 ficam fora do mart | Determinístico, sem dupla perda; censura à direita declarada |
| 2026-11-21 | P2.2: orçamento v1 calibrado só com jan/2025 e congelado em `configs/budget_v1.yaml` com hash; `freeze` recusa sobrescrever | Plano fixo antes de T4 (R10); mudança só como v2 |
| 2026-11-21 | P2.2: splits treino 01/01–31/07, validação 01/08–30/09 (= as-of), teste T4; lags ≥ horizonte, janelas deslocadas pelo horizonte | Previsão direta sem vazamento; teste de perturbação do futuro |
| 2026-11-21 | P2.2: feriados por regra curada (fixos, Páscoa, n-ésima segunda), não calendário oficial completo | Sem dependência nova; marcado `[TO VERIFY]` |
| 2026-11-21 | P2.3: seleção por WAPE composto (média 7/30/90, pesos iguais), por alvo; modelo complexo só vence com margem > 1 EP pareado, senão o melhor baseline | Decisão do usuário (composto) + parcimônia; EP é aproximado |
| 2026-11-21 | P2.3: alvos = TPV/net revenue/margem consolidados + TPV por país (BR, MX, CL) | Decisão do usuário; merchant individual fica fora (intermitência) |
| 2026-11-21 | P2.3: backtest lê reais truncados em 2025-09-30; campeões congelados em `champions_b1.yaml` (hash de config e dados); holdout T4 roda depois, uma vez, e falha se a config mudou | T4 nunca influencia a escolha |
| 2026-11-21 | P2.3: baselines com intervalos por resíduos empíricos k-passos (≥ 20 resíduos, senão n/a); ETS/SARIMA com IC do modelo | Cobertura medida, não assumida |
| 2026-11-21 | P2.4: cenários como premissas relativas sobre 7 drivers (TPV = produto de 3 fatores), separados da banda estatística (erros de soma de 90 d do backtest) | Incerteza estatística ≠ hipóteses de negócio |
| 2026-11-21 | P2.4: ponte fee = volume + mix (país) + taxa + interação explícita; custos em volume e taxa/mix; falha se houver resíduo | Fecha exatamente com a variação total |
| 2026-11-21 | P2.4: alertas com limites genéricos em `alerts.yaml`, avaliados ex-ante (≤ as-of) e ex-post | Limites transparentes e editáveis, não calibrados ao T4 |
| 2026-11-21 | P2.4: achado: premissas de processamento (0,35%) e refund+chargeback (2% da fee) do orçamento v1 estão muito abaixo do observado; v1 segue congelado | Erro não proposital do P2.1; correção só em v2 |
| 2026-11-21 | P2.5: orçamento v2 = reforecast de ritmo no as-of (nível de setembro, crescimento abr→set, razões de 90 d), calibrado só com dados ≤ 30/09 e congelado com hash | Corrige as premissas descalibradas do v1 sem olhar o T4; v1 permanece como está |
| 2026-11-21 | P2.5: `cli pipeline` único; artefatos congelados são verificados e reutilizados; holdout recusa dados diferentes dos usados no congelamento (data_hash) | Reprodutibilidade em uma instrução, sem reescrever o que foi fixado |
| 2026-11-21 | P2.5: auditoria independente recalcula do Parquet bruto com pandas (17 checks); tolerância de meio centavo por pagamento | O mart arredonda por pagamento (contrato do P1) |
| 2026-11-21 | P2.5: dashboard em inglês como P1/P3, tokens neutros; scripts de screenshot/axe reutilizam o helper CDP do P3 | Consistência e sem nova dependência |
