# P1 · Memo executivo: diagnóstico e simulação de intervenções

> **Dados sintéticos.** Todos os números abaixo são `derived` de um dataset `synthetic` gerado com seed fixa. Os padrões encontrados foram **plantados pelo gerador** (circularidade). Os cenários são *estimativas simuladas sob pressupostos explícitos*, não uplift realizado nem prova causal. Receita/take rate dependem de MDR sintético: **[TO VERIFY]**.

- Gerado por `python -m fintech_lab.p1_payments.cli diagnose` a partir do dataset `fa2f4dc4ed38` (sem data de execução: a mesma entrada gera o mesmo memo)
- Dataset: seed `20261121`, 447.090 pagamentos, 500.000 tentativas; SHA-256 do conteúdo `fa2f4dc4ed3873b0…`
- Tabelas completas (CSV) em `reports/diagnostics/`.

## 1. Achados descritivos (P1.4.a, P1.4.b)

### 1.1 Taxonomia de falhas por país
Denominador: **todas as tentativas** do país (M03 para soft/hard, M10 para technical).

| País | Tentativas | Soft decline (emissor, retentável) | Hard decline (emissor, final) | Erro técnico (adquirente/PSP) |
|---|---|---|---|---|
| BR | 267.285 | 12,7% | 8,4% | 1,9% |
| CL | 89.457 | 22,7% | 11,3% | 3,0% |
| MX | 143.258 | 19,3% | 9,9% | 2,5% |

Recusas *soft/hard* vêm do emissor; *technical* (timeout, erro do adquirente) é responsabilidade da cadeia de processamento. Só soft e technical são retentáveis.

### 1.2 Erro técnico em horário de pico (M10)
Denominador: tentativas do adquirente no período (hora local do merchant).

| País | Adquirente | M10 fora do pico | M10 pico 19–22h | Razão pico/fora |
|---|---|---|---|---|
| BR | ACQ_BR_A | 1,5% | 1,5% | 0,98× |
| BR | ACQ_BR_B | 2,5% | 6,1% | 2,44× |
| BR | PIX_BR | 1,0% | 1,0% | 1,01× |
| CL | ACQ_CL_A | 2,0% | 2,1% | 1,05× |
| CL | ACQ_CL_B | 3,4% | 4,4% | 1,28× |
| MX | ACQ_MX_A | 3,0% | 3,5% | 1,20× |
| MX | ACQ_MX_B | 2,0% | 2,1% | 1,06× |

### 1.3 Adquirentes: M01 bruto vs ajustado por mix (cartões)
Padronização direta sobre método × faixa de valor com o mix de tentativas do país (evita efeito Simpson). Descritivo: o roteamento original não é aleatório.

| País | Adquirente | Tentativas | M01 bruto | M01 ajustado | Rank |
|---|---|---|---|---|---|
| BR | ACQ_BR_A | 105.857 | 73,0% | 72,7% | 1 |
| BR | ACQ_BR_B | 75.572 | 64,8% | 65,3% | 2 |
| CL | ACQ_CL_A | 40.636 | 66,1% | 67,5% | 1 |
| CL | ACQ_CL_B | 48.821 | 60,5% | 58,9% | 2 |
| MX | ACQ_MX_B | 74.420 | 71,8% | 71,5% | 1 |
| MX | ACQ_MX_A | 68.838 | 64,5% | 64,8% | 2 |

### 1.4 Segmentos com mais pagamentos perdidos vs. a base país × método (n ≥ 500)
Grão: país × método × faixa de valor (BRL) × setor. *Perdidos* = pagamentos × (M02 da base − M02 do segmento). IC 95% de Wilson para o M02 do segmento.

| País | Método | Faixa BRL | Setor | Pagamentos | M02 | IC 95% | M02 base | Perdidos |
|---|---|---|---|---|---|---|---|---|
| BR | credit_card | 4: >=1000 | travel | 7.890 | 66,8% | 65,8–67,9% | 79,7% | 1.018 |
| BR | credit_card | 3: 200-1000 | travel | 9.817 | 73,9% | 73,0–74,8% | 79,7% | 573 |
| BR | credit_card | 2: 50-200 | digital_goods | 7.322 | 74,7% | 73,7–75,7% | 79,7% | 368 |
| BR | debit_card | 4: >=1000 | travel | 2.371 | 62,8% | 60,9–64,8% | 76,5% | 323 |
| BR | pix | 4: >=1000 | travel | 5.592 | 87,9% | 87,1–88,8% | 93,5% | 312 |
| MX | credit_card | 2: 50-200 | digital_goods | 5.941 | 74,9% | 73,8–76,0% | 79,6% | 278 |
| MX | debit_card | 3: 200-1000 | ecommerce_retail | 4.550 | 69,9% | 68,6–71,2% | 75,9% | 273 |
| CL | credit_card | 4: >=1000 | travel | 2.084 | 63,3% | 61,2–65,3% | 75,8% | 261 |
| CL | debit_card | 4: >=1000 | travel | 1.994 | 59,4% | 57,3–61,6% | 71,6% | 243 |
| MX | credit_card | 3: 200-1000 | ecommerce_retail | 5.705 | 75,6% | 74,4–76,7% | 79,6% | 228 |

A diferença de um segmento mistura risco do portador, ticket, setor e emissor; ela indica onde investigar, não o que causa a perda.

## 2. Cenários hipotéticos (P1.4.c, P1.4.d)

### S1 · Rerotear retries de soft decline para o adquirente alternativo
**População:** pagamentos com cartão cuja 1ª tentativa foi soft decline e que foram retentados no **mesmo** adquirente. **Mecânica:** dentro de cada estrato país × adquirente inicial × método × faixa de valor, aplica-se θ × (M02 dos que trocaram − M02 dos que ficaram) aos que ficaram. O custo por pagamento segue a mesma mistura (θ × diferença observada entre os braços), então θ = 0 é o cenário nulo. Receita: ticket médio aprovado × take rate sintética **[TO VERIFY]**. Estratos com < 30 pagamentos por braço ficam fora (coluna Cobertura).

Resultado com θ = 1 (a diferença observada se transfere integralmente):

| País | De | Rerroteados | Cobertura | Δ pagamentos aprovados | IC95 inf. | IC95 sup. | Δ M02 do país | Δ TPV (BRL) | Δ contribuição (BRL) | IC95 Δ contribuição (bootstrap) |
|---|---|---|---|---|---|---|---|---|---|---|
| BR | ACQ_BR_A | 5.980 | 100,0% | -435 | -562 | -307 | -0,18 pp | R$ -175.759 | R$ 934 | R$ -627 a R$ 2.430 |
| BR | ACQ_BR_B | 5.061 | 100,0% | +321 | +207 | +435 | +0,13 pp | R$ 89.690 | R$ -1.606 | R$ -2.901 a R$ -345 |
| CL | ACQ_CL_A | 2.739 | 100,0% | -188 | -278 | -97 | -0,25 pp | R$ -87.597 | R$ 330 | R$ -809 a R$ 1.780 |
| CL | ACQ_CL_B | 3.613 | 96,8% | +188 | +89 | +286 | +0,25 pp | R$ 32.059 | R$ -350 | R$ -626 a R$ -79 |
| MX | ACQ_MX_A | 4.798 | 100,0% | +255 | +142 | +369 | +0,20 pp | R$ 42.730 | R$ -451 | R$ -1.725 a R$ 895 |
| MX | ACQ_MX_B | 4.164 | 97,4% | -149 | -255 | -43 | -0,12 pp | R$ -18.343 | R$ 547 | R$ 242 a R$ 853 |

IC 95% de Δ pagamentos: aproximação normal da diferença de proporções. IC de Δ TPV e Δ contribuição: bootstrap percentil (500 reamostragens de pagamentos dentro de cada estrato × braço, seed `20261121`). Cobre só o ruído amostral; θ e take rate são tratados nas grades de sensibilidade.

- IC 95% de Δ acima de zero: **ACQ_BR_B, ACQ_CL_B, ACQ_MX_A**. Abaixo de zero: **ACQ_BR_A, ACQ_CL_A, ACQ_MX_B**. Indefinido (IC cruza zero): **nenhum**.
- Escolher só as direções com estimativa positiva introduz *winner's curse*: o ganho esperado dessas direções tende a ser superestimado.

- Trade-off autorização × custo: em **ACQ_BR_B, ACQ_CL_B** o cenário aprova mais pagamentos, mas a contribuição cai (IC 95% bootstrap abaixo de zero), porque o adquirente de destino tem tarifa sintética maior. Decidir exige pesar conversão do merchant contra margem.
- Em **ACQ_MX_A** o cenário aprova mais pagamentos, mas o sinal da Δ contribuição é **indefinido** (IC 95% bootstrap cruza zero): a amostra não sustenta afirmar ganho nem perda de margem.

Sensibilidade da Δ contribuição líquida (BRL) a θ, take rate × 1,0 (linear em θ):

| País | De | θ=0 | θ=0.25 | θ=0.5 | θ=0.75 | θ=1 |
|---|---|---|---|---|---|---|
| BR | ACQ_BR_A | R$ 0 | R$ 233 | R$ 467 | R$ 700 | R$ 934 |
| BR | ACQ_BR_B | R$ 0 | R$ -401 | R$ -803 | R$ -1.204 | R$ -1.606 |
| CL | ACQ_CL_A | R$ 0 | R$ 83 | R$ 165 | R$ 248 | R$ 330 |
| CL | ACQ_CL_B | R$ 0 | R$ -88 | R$ -175 | R$ -263 | R$ -350 |
| MX | ACQ_MX_A | R$ 0 | R$ -113 | R$ -226 | R$ -339 | R$ -451 |
| MX | ACQ_MX_B | R$ 0 | R$ 137 | R$ 274 | R$ 411 | R$ 547 |

Sensibilidade da Δ contribuição líquida (BRL) à take rate sintética, θ = 1:

| País | De | take × 0.8 | take × 1 | take × 1.2 |
|---|---|---|---|---|
| BR | ACQ_BR_A | R$ 1.865 | R$ 934 | R$ 3 |
| BR | ACQ_BR_B | R$ -2.073 | R$ -1.606 | R$ -1.138 |
| CL | ACQ_CL_A | R$ 784 | R$ 330 | R$ -123 |
| CL | ACQ_CL_B | R$ -507 | R$ -350 | R$ -193 |
| MX | ACQ_MX_A | R$ -704 | R$ -451 | R$ -199 |
| MX | ACQ_MX_B | R$ 624 | R$ 547 | R$ 471 |

### S2 · Limite de tentativas por pagamento (observado = 3)
**cap 2** remove a 3ª tentativa (dentro do suporte; supõe tentativas 1–2 inalteradas). **cap 4** é **extrapolação**: a 4ª tentativa ocorre com a propensão observada de retry 2→3 e aprova com o M01 observado na 3ª tentativa × δ (δ < 1 = decaimento).

| Cenário | Suporte | M02 | Δ M02 | Δ pagamentos | Δ TPV (BRL) | Δ custo (BRL) | Δ contribuição (BRL) |
|---|---|---|---|---|---|---|---|
| cap 2 | in-support | 79,7% | -0,86 pp | -3.837 | R$ -1.008.832 | R$ -19.365 | R$ -6.382 |
| cap 3 | in-support | 80,6% | +0,00 pp | +0 | R$ 0 | R$ 0 | R$ 0 |
| cap 4 (δ=0.50) | extrapolated | 80,6% | +0,08 pp | +341 | R$ 115.976 | R$ 1.987 | R$ 576 |
| cap 4 (δ=0.75) | extrapolated | 80,7% | +0,11 pp | +512 | R$ 173.963 | R$ 2.889 | R$ 955 |
| cap 4 (δ=1.00) | extrapolated | 80,7% | +0,15 pp | +683 | R$ 231.951 | R$ 3.792 | R$ 1.334 |

Sensibilidade da Δ contribuição líquida (BRL) ao multiplicador da take rate sintética:

| Cenário | take × 0.8 | take × 1 | take × 1.2 |
|---|---|---|---|
| cap 2 | R$ -1.232 | R$ -6.382 | R$ -11.531 |
| cap 4 (δ=0.75) | R$ 186 | R$ 955 | R$ 1.724 |

## 3. Vieses e por que isto não é causalidade (P1.4.e)

- **Viés de seleção / sobrevivência:** quem chega à 2ª ou 3ª tentativa já foi recusado; essa população tem risco latente maior (o gerador usa um risco oculto por pagamento). Taxas por `attempt_no` não são comparáveis entre si sem ajuste.
- **Troca de adquirente:** no gerador, a troca no retry é sorteada independentemente do risco, por isso a comparação de S1 dentro do estrato é quase não viesada **neste** dataset. Em produção, roteamento e retries são decididos por regras ligadas ao risco, e a mesma comparação seria confundida.
- **Contrafactual não observado:** não vemos o que teria acontecido com o mesmo pagamento em outro adquirente. θ representa quanto da diferença observada transferiria; o valor real é desconhecido (por isso a grade 0–1).
- **Fora do suporte:** cap 4 nunca foi observado. δ e a propensão de retry são pressupostos; regras de bandeira, atrito do usuário e limites de retry do emissor ficam fora do modelo.
- **Capacidade, contratos e preço:** S1 ignora limite de volume, SLA e renegociação de tarifa com o adquirente alternativo.
- **Circularidade:** os efeitos que aparecem (adquirente B do BR pior, picos de erro) foram parametrizados no `configs/generator.yaml`. O exercício demonstra o método, não descobre um fato de mercado.
- **Receita:** take rate e contribuição dependem de MDR sintético **[TO VERIFY]**.
- **Próximo passo para causalidade:** teste A/B ou roteamento aleatorizado em uma fração do tráfego (ver P3), com métrica primária M02 e guardrails de custo (M09) e M10.

## 4. Reprodução

```powershell
.\.venv\Scripts\Activate.ps1
python -m fintech_lab.p1_payments.cli generate
python -m fintech_lab.p1_payments.cli build
python -m fintech_lab.p1_payments.cli diagnose
```
