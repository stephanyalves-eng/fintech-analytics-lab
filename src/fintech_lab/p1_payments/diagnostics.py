"""P1.4 diagnostics: descriptive tables, scenario runs and the executive memo.

All numbers in the memo are computed here from the warehouse; nothing is hand-written.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from fintech_lab.p1_payments import scenarios as sc
from fintech_lab.p1_payments.warehouse import SQL_DIR, load_named, run_analysis

MIN_SEGMENT_PAYMENTS = 500


def queries() -> dict[str, str]:
    return load_named(SQL_DIR / "diagnostics" / "diagnostics.sql")


def run(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    return con.execute(queries()[name]).df()


def worst_segments(con: duckdb.DuckDBPyConnection, top: int = 10) -> pd.DataFrame:
    d = run(con, "d02_segment_success")
    d = d[d["payments"] >= MIN_SEGMENT_PAYMENTS].copy()
    ci = [sc.wilson(s, n) for s, n in zip(d["succeeded"], d["payments"], strict=True)]
    d["m02_lo95"] = [c[0] for c in ci]
    d["m02_hi95"] = [c[1] for c in ci]
    d["below_baseline_95"] = d["m02_hi95"] < d["baseline_m02"]
    return d.sort_values("lost_vs_baseline", ascending=False).head(top).reset_index(drop=True)


def compute_all(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """Every table the memo and the dashboard scenario tab rely on."""
    s1_base = run(con, "s1_reroute_base")
    s2_base = run(con, "s2_retry_base")
    cp = s2_base.set_index("country")["payments"]
    s1 = sc.simulate_s1(s1_base, cp)
    boot = sc.s1_bootstrap(run(con, "s1_payments"), cp)
    s1 = s1.merge(boot, on=["country", "first_acquirer_id"], how="left", validate="1:1")
    return {
        "d01_failure_taxonomy": run(con, "d01_failure_taxonomy"),
        "d02_worst_segments": worst_segments(con),
        "d03_error_rate_by_period": run(con, "d03_error_rate_by_period"),
        "d04_acquirer_mix_adjusted": run_analysis(con, "q04_acquirer_mix_adjusted"),
        "s1_reroute_base": s1_base,
        "s1_result": s1,
        "s1_sensitivity": sc.s1_sensitivity(s1_base, cp),
        "s2_retry_base": s2_base,
        "s2_grid": sc.s2_grid(s2_base),
    }


# ---------------------------------------------------------------- memo rendering
def _fmt(v: object, kind: str = "") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if kind == "pct":
        return f"{float(v) * 100:.1f}%".replace(".", ",")
    if kind == "pp":
        return f"{float(v):+.2f} pp".replace(".", ",")
    if kind == "x":
        return f"{float(v):.2f}×".replace(".", ",")
    if kind == "brl":
        return f"R$ {float(v):,.0f}".replace(",", ".")
    if kind == "int":
        return f"{float(v):,.0f}".replace(",", ".")
    if kind == "sint":
        return f"{float(v):+,.0f}".replace(",", ".")
    return str(v)


def md_table(df: pd.DataFrame, cols: dict[str, tuple[str, str]]) -> str:
    """cols: {column: (header, kind)}."""
    head = "| " + " | ".join(h for h, _ in cols.values()) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    rows = [
        "| " + " | ".join(_fmt(r[c], k) for c, (_, k) in cols.items()) + " |"
        for _, r in df.iterrows()
    ]
    return "\n".join([head, sep, *rows])


def render_memo(t: dict[str, pd.DataFrame], manifest: dict, dataset_id: str) -> str:
    tax = t["d01_failure_taxonomy"]
    fail = tax[tax["result"] != "approved"]
    cat = fail.groupby(["country", "category"], as_index=False)[["attempts", "share_of_attempts"]]
    cat = cat.sum()
    tot_att = tax.groupby("country")["attempts"].sum()
    cat_share = cat.pivot(index="country", columns="category", values="share_of_attempts")
    cat_share = cat_share.reindex(columns=["soft", "hard", "technical"]).reset_index()

    seg = t["d02_worst_segments"]
    err = t["d03_error_rate_by_period"].pivot(
        index=["country", "acquirer_id"], columns="period", values="m10_technical_error_rate"
    )
    err = err.reset_index()
    err["ratio"] = err["peak 19-22h"] / err["off-peak"]
    acq = t["d04_acquirer_mix_adjusted"]

    s1 = t["s1_result"]
    sens = t["s1_sensitivity"]
    s1_pivot = (
        sens[sens["take_mult"] == 1.0]
        .pivot(
            index=["country", "first_acquirer_id"], columns="theta", values="d_net_contribution_brl"
        )
        .reset_index()
    )
    s1_pivot.columns = [str(c) for c in s1_pivot.columns]
    s1 = s1.assign(
        contrib_ci=[
            f"{_fmt(lo, 'brl')} a {_fmt(hi, 'brl')}"
            for lo, hi in zip(
                s1["d_net_contribution_brl_boot_lo95"],
                s1["d_net_contribution_brl_boot_hi95"],
                strict=True,
            )
        ]
    )
    pos = s1[s1["d_succeeded_lo95"] > 0]
    neg = s1[s1["d_succeeded_hi95"] < 0]
    unclear = s1[(s1["d_succeeded_lo95"] <= 0) & (s1["d_succeeded_hi95"] >= 0)]

    g = t["s2_grid"]
    s2_tot = g[(g["country"] == "TOTAL") & (g["take_mult"] == 1.0)].copy()
    s2_tot["cenário"] = s2_tot.apply(
        lambda r: f"cap {r['cap']}" + (f" (δ={r['delta']:.2f})" if r["cap"] == 4 else ""), axis=1
    )
    s2_take = g[(g["country"] == "TOTAL") & (g["cap"].isin([2, 4]))]
    s2_take = s2_take[(s2_take["cap"] == 2) | (s2_take["delta"] == 0.75)].copy()
    s2_take["cenário"] = s2_take["cap"].map({2: "cap 2", 4: "cap 4 (δ=0.75)"})
    s2_take = s2_take.pivot(index="cenário", columns="take_mult", values="d_net_contribution_brl")
    s2_take = s2_take.reset_index()
    s2_take.columns = [str(c) for c in s2_take.columns]

    rows = manifest.get("tables", {})
    n_pay = rows.get("fact_payment", {}).get("rows")
    n_att = rows.get("fact_attempt", {}).get("rows")
    sha = manifest.get("dataset_content_sha256", "[TO VERIFY]")

    def names(df: pd.DataFrame) -> str:
        return ", ".join(df["first_acquirer_id"]) or "nenhum"

    L: list[str] = []
    a = L.append
    a("# P1 · Memo executivo: diagnóstico e simulação de intervenções")
    a("")
    a(
        "> **Dados sintéticos.** Todos os números abaixo são `derived` de um dataset `synthetic` "
        "gerado com seed fixa. Os padrões encontrados foram **plantados pelo gerador** "
        "(circularidade). Os cenários são *estimativas simuladas sob pressupostos explícitos*, "
        "não uplift realizado nem prova causal. Receita/take rate dependem de MDR sintético: "
        "**[TO VERIFY]**."
    )
    a("")
    a(
        f"- Gerado por `python -m fintech_lab.p1_payments.cli diagnose` a partir do dataset "
        f"{dataset_id} (sem data de execução: a mesma entrada gera o mesmo memo)"
    )
    a(
        f"- Dataset: seed `{manifest.get('seed', '[TO VERIFY]')}`, "
        f"{_fmt(n_pay, 'int')} pagamentos, {_fmt(n_att, 'int')} tentativas; "
        f"SHA-256 do conteúdo `{sha[:16]}…`"
    )
    a("- Tabelas completas (CSV) em `reports/diagnostics/`.")
    a("")
    a("## 1. Achados descritivos (P1.4.a, P1.4.b)")
    a("")
    a("### 1.1 Taxonomia de falhas por país")
    a("Denominador: **todas as tentativas** do país (M03 para soft/hard, M10 para technical).")
    a("")
    cat_share["attempts"] = cat_share["country"].map(tot_att)
    a(
        md_table(
            cat_share,
            {
                "country": ("País", ""),
                "attempts": ("Tentativas", "int"),
                "soft": ("Soft decline (emissor, retentável)", "pct"),
                "hard": ("Hard decline (emissor, final)", "pct"),
                "technical": ("Erro técnico (adquirente/PSP)", "pct"),
            },
        )
    )
    a("")
    a(
        "Recusas *soft/hard* vêm do emissor; *technical* (timeout, erro do adquirente) é "
        "responsabilidade da cadeia de processamento. Só soft e technical são retentáveis."
    )
    a("")
    a("### 1.2 Erro técnico em horário de pico (M10)")
    a("Denominador: tentativas do adquirente no período (hora local do merchant).")
    a("")
    a(
        md_table(
            err,
            {
                "country": ("País", ""),
                "acquirer_id": ("Adquirente", ""),
                "off-peak": ("M10 fora do pico", "pct"),
                "peak 19-22h": ("M10 pico 19–22h", "pct"),
                "ratio": ("Razão pico/fora", "x"),
            },
        )
    )
    a("")
    a("### 1.3 Adquirentes: M01 bruto vs ajustado por mix (cartões)")
    a(
        "Padronização direta sobre método × faixa de valor com o mix de tentativas do país "
        "(evita efeito Simpson). Descritivo: o roteamento original não é aleatório."
    )
    a("")
    a(
        md_table(
            acq,
            {
                "country": ("País", ""),
                "acquirer_id": ("Adquirente", ""),
                "attempts": ("Tentativas", "int"),
                "m01_raw": ("M01 bruto", "pct"),
                "m01_mix_adjusted": ("M01 ajustado", "pct"),
                "rank_adjusted": ("Rank", ""),
            },
        )
    )
    a("")
    a(
        f"### 1.4 Segmentos com mais pagamentos perdidos vs. a base país × método (n ≥ "
        f"{MIN_SEGMENT_PAYMENTS})"
    )
    a(
        "Grão: país × método × faixa de valor (BRL) × setor. *Perdidos* = pagamentos × "
        "(M02 da base − M02 do segmento). IC 95% de Wilson para o M02 do segmento."
    )
    a("")
    seg = seg.assign(
        ci=[
            f"{lo * 100:.1f}–{hi * 100:.1f}%".replace(".", ",")
            for lo, hi in zip(seg["m02_lo95"], seg["m02_hi95"], strict=True)
        ]
    )
    a(
        md_table(
            seg,
            {
                "country": ("País", ""),
                "method_code": ("Método", ""),
                "amount_band_brl": ("Faixa BRL", ""),
                "sector": ("Setor", ""),
                "payments": ("Pagamentos", "int"),
                "m02": ("M02", "pct"),
                "ci": ("IC 95%", ""),
                "baseline_m02": ("M02 base", "pct"),
                "lost_vs_baseline": ("Perdidos", "int"),
            },
        )
    )
    a("")
    a(
        "A diferença de um segmento mistura risco do portador, ticket, setor e emissor; "
        "ela indica onde investigar, não o que causa a perda."
    )
    a("")
    a("## 2. Cenários hipotéticos (P1.4.c, P1.4.d)")
    a("")
    a("### S1 · Rerotear retries de soft decline para o adquirente alternativo")
    a(
        "**População:** pagamentos com cartão cuja 1ª tentativa foi soft decline e que foram "
        "retentados no **mesmo** adquirente. **Mecânica:** dentro de cada estrato país × "
        "adquirente inicial × método × faixa de valor, aplica-se θ × (M02 dos que trocaram − "
        "M02 dos que ficaram) aos que ficaram. O custo por pagamento segue a mesma mistura "
        "(θ × diferença observada entre os braços), então θ = 0 é o cenário nulo. "
        "Receita: ticket médio aprovado × take rate sintética "
        "**[TO VERIFY]**. Estratos com < 30 pagamentos por braço ficam fora (coluna Cobertura)."
    )
    a("")
    a("Resultado com θ = 1 (a diferença observada se transfere integralmente):")
    a("")
    a(
        md_table(
            s1,
            {
                "country": ("País", ""),
                "first_acquirer_id": ("De", ""),
                "rerouted_payments": ("Rerroteados", "int"),
                "coverage": ("Cobertura", "pct"),
                "d_succeeded": ("Δ pagamentos aprovados", "sint"),
                "d_succeeded_lo95": ("IC95 inf.", "sint"),
                "d_succeeded_hi95": ("IC95 sup.", "sint"),
                "d_m02_pp": ("Δ M02 do país", "pp"),
                "d_tpv_brl": ("Δ TPV (BRL)", "brl"),
                "d_net_contribution_brl": ("Δ contribuição (BRL)", "brl"),
                "contrib_ci": ("IC95 Δ contribuição (bootstrap)", ""),
            },
        )
    )
    a("")
    n_boot = int(s1["n_boot"].iloc[0]) if len(s1) else 0
    a(
        f"IC 95% de Δ pagamentos: aproximação normal da diferença de proporções. IC de Δ TPV e "
        f"Δ contribuição: bootstrap percentil ({n_boot} reamostragens de pagamentos dentro de "
        f"cada estrato × braço, seed `{int(s1['boot_seed'].iloc[0]) if len(s1) else '—'}`). "
        "Cobre só o ruído amostral; θ e take rate são tratados nas grades de sensibilidade."
    )
    a("")
    a(
        f"- IC 95% de Δ acima de zero: **{names(pos)}**. Abaixo de zero: **{names(neg)}**. "
        f"Indefinido (IC cruza zero): **{names(unclear)}**."
    )
    a(
        "- Escolher só as direções com estimativa positiva introduz *winner's curse*: o ganho "
        "esperado dessas direções tende a ser superestimado."
    )
    a("")
    lo_c, hi_c = s1["d_net_contribution_brl_boot_lo95"], s1["d_net_contribution_brl_boot_hi95"]
    more = s1["d_succeeded_lo95"] > 0
    trade = s1[more & (hi_c < 0)]
    unclear_c = s1[more & (lo_c <= 0) & (hi_c >= 0)]
    if len(trade):
        a(
            f"- Trade-off autorização × custo: em **{names(trade)}** o cenário aprova mais "
            "pagamentos, mas a contribuição cai (IC 95% bootstrap abaixo de zero), porque o "
            "adquirente de destino tem tarifa sintética maior. Decidir exige pesar conversão "
            "do merchant contra margem."
        )
    if len(unclear_c):
        a(
            f"- Em **{names(unclear_c)}** o cenário aprova mais pagamentos, mas o sinal da "
            "Δ contribuição é **indefinido** (IC 95% bootstrap cruza zero): a amostra não "
            "sustenta afirmar ganho nem perda de margem."
        )
    a("")
    a("Sensibilidade da Δ contribuição líquida (BRL) a θ, take rate × 1,0 (linear em θ):")
    a("")
    th = {str(x): (f"θ={x:g}", "brl") for x in sc.THETAS}
    a(md_table(s1_pivot, {"country": ("País", ""), "first_acquirer_id": ("De", ""), **th}))
    a("")
    a("Sensibilidade da Δ contribuição líquida (BRL) à take rate sintética, θ = 1:")
    a("")
    tk1 = (
        sens[sens["theta"] == 1.0]
        .pivot(
            index=["country", "first_acquirer_id"],
            columns="take_mult",
            values="d_net_contribution_brl",
        )
        .reset_index()
    )
    tk1.columns = [str(c) for c in tk1.columns]
    tkc = {str(x): (f"take × {x:g}", "brl") for x in sc.MULTS}
    a(md_table(tk1, {"country": ("País", ""), "first_acquirer_id": ("De", ""), **tkc}))
    a("")
    a("### S2 · Limite de tentativas por pagamento (observado = 3)")
    a(
        "**cap 2** remove a 3ª tentativa (dentro do suporte; supõe tentativas 1–2 inalteradas). "
        "**cap 4** é **extrapolação**: a 4ª tentativa ocorre com a propensão observada de retry "
        "2→3 e aprova com o M01 observado na 3ª tentativa × δ (δ < 1 = decaimento)."
    )
    a("")
    a(
        md_table(
            s2_tot,
            {
                "cenário": ("Cenário", ""),
                "support": ("Suporte", ""),
                "m02_scenario": ("M02", "pct"),
                "d_m02_pp": ("Δ M02", "pp"),
                "d_succeeded": ("Δ pagamentos", "sint"),
                "d_tpv_brl": ("Δ TPV (BRL)", "brl"),
                "d_cost_brl": ("Δ custo (BRL)", "brl"),
                "d_net_contribution_brl": ("Δ contribuição (BRL)", "brl"),
            },
        )
    )
    a("")
    a("Sensibilidade da Δ contribuição líquida (BRL) ao multiplicador da take rate sintética:")
    a("")
    tk = {str(x): (f"take × {x:g}", "brl") for x in sc.MULTS}
    a(md_table(s2_take, {"cenário": ("Cenário", ""), **tk}))
    a("")
    a("## 3. Vieses e por que isto não é causalidade (P1.4.e)")
    a("")
    for line in [
        "**Viés de seleção / sobrevivência:** quem chega à 2ª ou 3ª tentativa já foi recusado; "
        "essa população tem risco latente maior (o gerador usa um risco oculto por pagamento). "
        "Taxas por `attempt_no` não são comparáveis entre si sem ajuste.",
        "**Troca de adquirente:** no gerador, a troca no retry é sorteada independentemente do "
        "risco, por isso a comparação de S1 dentro do estrato é quase não viesada **neste** "
        "dataset. Em produção, roteamento e retries são decididos por regras ligadas ao risco, e "
        "a mesma comparação seria confundida.",
        "**Contrafactual não observado:** não vemos o que teria acontecido com o mesmo pagamento "
        "em outro adquirente. θ representa quanto da diferença observada transferiria; o valor "
        "real é desconhecido (por isso a grade 0–1).",
        "**Fora do suporte:** cap 4 nunca foi observado. δ e a propensão de retry são "
        "pressupostos; regras de bandeira, atrito do usuário e limites de retry do emissor ficam "
        "fora do modelo.",
        "**Capacidade, contratos e preço:** S1 ignora limite de volume, SLA e renegociação de "
        "tarifa com o adquirente alternativo.",
        "**Circularidade:** os efeitos que aparecem (adquirente B do BR pior, picos de erro) "
        "foram parametrizados no `configs/generator.yaml`. O exercício demonstra o método, não "
        "descobre um fato de mercado.",
        "**Receita:** take rate e contribuição dependem de MDR sintético **[TO VERIFY]**.",
        "**Próximo passo para causalidade:** teste A/B ou roteamento aleatorizado em uma fração "
        "do tráfego (ver P3), com métrica primária M02 e guardrails de custo (M09) e M10.",
    ]:
        a(f"- {line}")
    a("")
    a("## 4. Reprodução")
    a("")
    a("```powershell")
    a(".\\.venv\\Scripts\\Activate.ps1")
    a("python -m fintech_lab.p1_payments.cli generate")
    a("python -m fintech_lab.p1_payments.cli build")
    a("python -m fintech_lab.p1_payments.cli diagnose")
    a("```")
    return "\n".join(L) + "\n"


def write_reports(
    con: duckdb.DuckDBPyConnection, data_dir: str | Path, out_dir: str | Path
) -> dict[str, pd.DataFrame]:
    out = Path(out_dir)
    tdir = out / "diagnostics"
    tdir.mkdir(parents=True, exist_ok=True)
    tables = compute_all(con)
    for name, df in tables.items():
        df.to_csv(tdir / f"{name}.csv", index=False, float_format="%.6g")
    mf = Path(data_dir) / "manifest.json"
    manifest = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
    sha = str(manifest.get("dataset_content_sha256", "[TO VERIFY]"))
    memo = render_memo(tables, manifest, f"`{sha[:12]}`")
    (out / "diagnostic_memo.md").write_text(memo, encoding="utf-8")
    return tables
