"""End-to-end run + decision memo + cross-scenario report (P3.4 / P3.5.e). Numbers only from runs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from fintech_lab.p3_experiments.analysis import analyze
from fintech_lab.p3_experiments.decision import decide, exploratory_segments
from fintech_lab.p3_experiments.economics import evaluate, load_economics
from fintech_lab.p3_experiments.power import P3_ROOT, REPO_ROOT, load_protocol

DATA_ROOT = REPO_ROOT / "data" / "p3"
REPORTS = P3_ROOT / "reports" / "scenarios"


def run(data_dir: Path) -> dict[str, Any]:
    """Analysis + decision + hypothetical economics + exploratory segments for one dataset."""
    protocol = load_protocol()
    res = analyze(data_dir, protocol)
    u = res["_frames"]["users"]
    res["decision"] = decide(res)
    res["economics"] = evaluate(u, load_economics())
    res["segments"] = exploratory_segments(u, protocol)
    del res["_frames"]
    return res


def _pp(v: float) -> str:
    return "n/a" if v != v else f"{v * 100:+.2f} p.p."


def _g(v: float, relative: bool, gid: str) -> str:
    if v != v:
        return "n/a"
    if relative:
        return f"{v * 100:+.2f}%"
    return f"{v:+.0f} ms" if gid == "G3" else f"{v * 100:+.3f} p.p."


def _brl(v: float) -> str:
    return f"R$ {v:,.0f}"


def _fmt_est(gid: str, v: float) -> str:
    return f"{v:.0f} ms" if gid == "G3" else f"{v:.4g}"


def memo(res: dict[str, Any]) -> str:
    m, p, d, e = res["meta"], res["primary"], res["decision"], res["economics"]
    g = res["gates"]
    L = [
        f"# Memo de decisão · {m['experiment_id']} · cenário `{m['scenario']}`",
        "",
        f"> **Dados 100% sintéticos** (`{m['data_origin']}`), seed {m['seed']}, protocolo "
        f"v{m['protocol_version']} bloqueado (SHA-256, {m['amendments']} emendas). "
        "Os valores econômicos são **hipotéticos** e dependem de premissas [TO VERIFY].",
        "",
        f"## Decisão: **{d['decision']}** ({d['rule']})",
        *[f"- {r}" for r in d["reasons"]],
        "",
        "## Validade (antes de qualquer efeito)",
        f"- SRM: A={g['srm']['n_a']}, B={g['srm']['n_b']}, p={g['srm']['p_value']:.4g} "
        f"(limite {g['srm']['threshold']}) → {'ok' if g['srm']['pass'] else 'FALHOU'}",
        f"- Integridade da atribuição: {g['assignment_integrity']['duplicate_users']} duplicados, "
        f"{g['assignment_integrity']['arm_mismatch_vs_hash']} divergências do hash → "
        f"{'ok' if g['assignment_integrity']['pass'] else 'FALHOU'}",
        f"- Eventos antes da exposição: {g['events_before_exposure']['count']}",
        f"- Trilhas incompletas: A {g['missing_events']['share_a']:.2%}, "
        f"B {g['missing_events']['share_b']:.2%} → "
        f"{'ok' if g['missing_events']['pass'] else 'FALHOU'}",
        "",
        "## Métrica primária P01 (conversão do usuário em 7 d, grão usuário, ITT)",
        f"- A {p['p_a']:.2%} (n={p['n_a']}) · B {p['p_b']:.2%} (n={p['n_b']})",
        f"- Diferença {_pp(p['diff'])}, IC 95% [{_pp(p['ci_low'])}, {_pp(p['ci_high'])}], "
        f"p={p['p_value']:.4g}",
        f"- Relativa {p['rel'] * 100:+.2f}% [{p['rel_ci_low'] * 100:+.2f}%, "
        f"{p['rel_ci_high'] * 100:+.2f}%]",
        f"- MDE de desenho no n observado: {_pp(p['mde_abs_at_observed_n'])} "
        "(não é poder observado)",
        "",
        "## Guardrails (não inferioridade; d = B − A, maior é pior)",
        "| ID | Métrica | A | B | d | IC 95% | Margem | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for x in res["guardrails"]:
        rel = x["relative"]
        mg = f"{x['margin'] * 100:.0f}%" if rel else _g(x["margin"], False, x["id"])
        L.append(
            f"| {x['id']} | {x['name']} | {_fmt_est(x['id'], x['est_a'])} | "
            f"{_fmt_est(x['id'], x['est_b'])} | {_g(x['diff'], rel, x['id'])} | "
            f"[{_g(x['ci_low'], rel, x['id'])}, {_g(x['ci_high'], rel, x['id'])}] | {mg} | "
            f"**{x['status']}** |"
        )
    s = res["sensitivity"]
    ex, hc = s["exclude_incomplete_trails"], s["robust_hc1"]
    L += [
        "",
        "## Sensibilidade (não decisória)",
        f"- Excluindo {s['incomplete_users']} usuários com trilha incompleta: {_pp(ex['diff'])} "
        f"[{_pp(ex['ci_low'])}, {_pp(ex['ci_high'])}]",
        f"- Erro-padrão robusto HC1: {_pp(hc['diff'])} [{_pp(hc['ci_low'])}, {_pp(hc['ci_high'])}]",
        "",
        "## Economia HIPOTÉTICA",
        f"- Valor por usuário: A R$ {e['value_per_user_a']:.2f} · B R$ {e['value_per_user_b']:.2f} "
        f"· Δ R$ {e['diff_per_user']:+.3f} "
        f"[{e['ci_low_per_user']:+.3f}, {e['ci_high_per_user']:+.3f}]",
        f"- Anualizado ({e['annual_users']:,} usuários/ano, premissa): Δ {_brl(e['annual_delta'])} "
        f"[{_brl(e['annual_ci_low'])}, {_brl(e['annual_ci_high'])}]",
        f"- Após custo de implementação assumido ({_brl(e['implementation_cost'])}): "
        f"{_brl(e['year1_net'])} [{_brl(e['year1_net_ci_low'])}, {_brl(e['year1_net_ci_high'])}]",
        "- A regra de lançamento do protocolo **não** usa esta seção.",
        "",
        "## Segmentos (exploratórios, sem correção de multiplicidade, não decidem nada)",
    ]
    seg = res["segments"]
    if len(seg):
        L += ["| Segmento | Nível | n A | n B | Δ | IC 95% |", "|---|---|---|---|---|---|"]
        L += [
            f"| {r.segment} | {r.level} | {r.n_a} | {r.n_b} | {_pp(r.diff)} | "
            f"[{_pp(r.ci_low)}, {_pp(r.ci_high)}] |"
            for r in seg.itertuples()
        ]
    L += [
        "",
        "## Limitações",
        "- Efeito ITT de oferecer B, na população simulada (BR, cartão); sem validade externa.",
        "- Chargeback simulado com maturação de 30 d; na prática pode levar 90 d ou mais.",
        "- Interferência entre usuários assumida desprezível (não verificada).",
        "- Não significativo ≠ sem efeito; um guardrail `undetermined` não prova segurança.",
    ]
    return "\n".join(L) + "\n"


def _json_default(o: Any) -> Any:
    return str(o)


def _clean(o: Any) -> Any:
    if isinstance(o, float) and math.isnan(o):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def write_outputs(res: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    slim = _clean({k: v for k, v in res.items() if k != "segments"})
    (out_dir / "results.json").write_text(
        json.dumps(slim, indent=2, default=_json_default) + "\n", encoding="utf-8", newline="\n"
    )
    res["segments"].to_csv(out_dir / "exploratory_segments.csv", index=False, lineterminator="\n")
    (out_dir / "decision_memo.md").write_text(memo(res), encoding="utf-8", newline="\n")
    return out_dir


def experiment_report(results: dict[str, dict[str, Any]]) -> str:
    """Cross-scenario report. Outcomes come from the data; no expected result is hard-coded."""
    L = [
        "# Relatório do experimento P3-EXP-001 (todos os cenários)",
        "",
        "> Dados sintéticos. Cada linha é uma execução real do pipeline travado.",
        "",
        "| Cenário | Decisão | P01 Δ [IC 95%] | p | SRM p | Trilhas inc. B−A | Guardrails |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, r in results.items():
        p, g = r["primary"], r["gates"]
        gs = " ".join(f"{x['id']}:{x['status'][0]}" for x in r["guardrails"])
        L.append(
            f"| {name} | **{r['decision']['decision']}** | {_pp(p['diff'])} "
            f"[{_pp(p['ci_low'])}, {_pp(p['ci_high'])}] | {p['p_value']:.3g} | "
            f"{g['srm']['p_value']:.3g} | {g['missing_events']['diff']:+.2%} | {gs} |"
        )
    L += [
        "",
        "Legenda dos guardrails: p = pass, f = fail, u = undetermined.",
        "Memos por cenário em `reports/scenarios/<cenário>/decision_memo.md`.",
        "",
    ]
    return "\n".join(L)


def run_all(scenarios: tuple[str, ...], data_root: Path = DATA_ROOT) -> dict[str, dict[str, Any]]:
    out = {}
    for s in scenarios:
        res = run(Path(data_root) / s)
        write_outputs(res, REPORTS / s)
        out[s] = res
    (P3_ROOT / "reports" / "experiment_report.md").write_text(
        experiment_report(out), encoding="utf-8", newline="\n"
    )
    return out
