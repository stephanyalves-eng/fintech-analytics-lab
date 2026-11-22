# P3 · Fintech Experimentation & A/B Testing Lab

Pergunta: **3DS baseado em risco (B) aumenta a conversão sem piorar fraude, falhas, latência, custo ou abandono, comparado ao 3DS obrigatório (A)?** Todos os dados são sintéticos e a economia é hipotética.

```powershell
.\.venv\Scripts\Activate.ps1
python -m fintech_lab.p3_experiments.cli verify      # protocolo bate com o lock
python -m fintech_lab.p3_experiments.cli generate    # 5 cenários -> data/p3 (não versionado)
python -m fintech_lab.p3_experiments.cli analyze     # análise travada + memos + relatório
python -m fintech_lab.p3_experiments.cli montecarlo  # erro tipo I e poder
python -m fintech_lab.p3_experiments.cli dashboard   # http://localhost:8502
```

- Protocolo pré-registrado e bloqueado: [docs/protocol.md](docs/protocol.md). Métodos e ressalvas: [docs/methods.md](docs/methods.md).
- Resultados por cenário: [reports/experiment_report.md](reports/experiment_report.md) e `reports/scenarios/<cenário>/decision_memo.md`.
- Screenshots reais do app em `assets/screenshots/` (`app/capture_screenshots.py`).

## Interpretação responsável
- Os cenários provam que o **motor** distingue efeito, ausência de efeito, SRM e dados ausentes. Não dizem nada sobre um 3DS real.
- Intervalo que inclui zero não é "sem efeito". Guardrail `undetermined` não é segurança.
- A decisão vem só do protocolo travado; economia e segmentos não a alteram.
- Ressalvas medidas (ver methods.md): o G2 tem erro tipo I de 0,028 (leve excesso) e o G4 tem poder de só 0,35, o que limita a chance real de "Launch".
- Acessibilidade: auditoria automática com axe-core (0 violações nas 7 abas e no cenário SRM; 1 item `incomplete` por tela para revisão manual; teste de teclado automatizado e parcial em `reports/keyboard_smoke.md`: sem armadilha, setas movem entre abas; teclado humano e leitor de tela `[TO VERIFY]`) em `reports/a11y_axe.md`. Teclado e leitor de tela não foram testados manualmente [TO VERIFY].
