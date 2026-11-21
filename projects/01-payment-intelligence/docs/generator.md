# P1 · Gerador sintético (P1.2)

Todos os dados produzidos aqui são **`synthetic`**. Os parâmetros ficam em `configs/generator.yaml`, foram escolhidos para dar formas plausíveis e **não estão calibrados** contra benchmarks reais do setor.

## Uso (raiz do repo, `.venv` ativo)
```powershell
python -m fintech_lab.p1_payments.cli generate                    # 500k tentativas -> data/p1/default
python -m fintech_lab.p1_payments.cli generate --attempts 2000000 --out data/p1/large
python -m fintech_lab.p1_payments.cli generate --seed 7 --merchants 100 --out data/p1/s7
python -m fintech_lab.p1_payments.cli corrupt                     # fixture de DQ -> data/p1/corrupted
```
Saída: um Parquet por tabela (metadado de schema `data_origin=synthetic`) e um `manifest.json` com seed, versão do gerador, hash da config, schema, contagens, SHA-256 dos arquivos e SHA-256 do conteúdo.

## Como os dados são gerados
| Etapa | Mecânica |
|---|---|
| Merchants | país, setor e porte por pesos; volume = peso do porte × lognormal(0, 0,5) (heterogeneidade); 60% já ativos antes do período, o resto ativa durante (gera cohorts); cada merchant tem um adquirente primário |
| Pagamentos | dia por curva de demanda (dia da semana × mês × tendência × picos), limitada à data de ativação; hora por perfil de 24h (local); método pelo mix do país; valor lognormal por setor em BRL equivalente, convertido para a moeda local pelo FX do dia |
| Tentativas | 85% da 1ª tentativa vai ao adquirente primário. P(erro técnico) por adquirente (maior no pico em alguns); P(aprovação \| sem erro) = logística(base do adquirente + método + setor + efeito do merchant + faixa de valor + madrugada + nº da tentativa + risco latente) |
| Recusas | P(hard \| recusa) cresce com o risco latente; códigos sorteados dentro da categoria. Pix: só `pix_rejected` (hard) |
| Retries | só após soft (55%) ou técnico (80%), até 3 tentativas; troca de adquirente do mesmo país e tipo (30% soft / 60% técnico); intervalo exponencial (20 min soft / 30 s técnico) |
| Volume | gera pagamentos i.i.d. e mantém o maior prefixo cujo total de tentativas ≤ `target_attempts` (fica até 2 abaixo do alvo) |
| Settlement | 1 por pagamento `succeeded`: data local da aprovação + D+N do método; fee = MDR sintético por método × porte `[TO VERIFY]` |

O **risco latente** é por pagamento e **não é exportado**: funciona como confundidor oculto. Os padrões que a análise "descobre" (diferença entre adquirentes, erro no pico, efeito de faixa de valor) foram **plantados** por esses parâmetros.

## Fixture corrompida (P1.2.d)
`corrupt` gera um dataset pequeno e separado (seed + 7, 2.000 pagamentos) e injeta 14 defeitos controlados. O `manifest.json` lista cada defeito, a chave afetada e o check de `sql/checks/contract.sql` que deve pegá-lo.

## Execução observada (2026-11-21, seed 20261121)
| Comando | Resultado |
|---|---|
| `generate` (padrão) | 447.090 pagamentos, 500.000 tentativas, 360.162 settlements, 300 merchants; 3,5 s |
| `generate` repetido | `dataset_content_sha256` idêntico (`fa2f4dc4…`) |
| `generate --attempts 2000000` | 1.788.668 pagamentos, 2.000.000 tentativas; 17,0 s |
| `check` (limpo) | 13/13 contrato + 5/5 reconciliação PASS |
| `check --contract-only` (corrompido) | 12 checks falham conforme esperado; c13 passa (nenhum defeito o atinge) |
