"""P2.4 orchestration: bridges, scenarios, alerts and the executive closing report.

Every number in the report is computed here from the P2 exports; the prose only describes them.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fintech_lab.p1_payments.generator import DEFAULT_CONFIG as P1_GENERATOR_CONFIG
from fintech_lab.p2_forecasting import alerts as AL
from fintech_lab.p2_forecasting import pnl, scenarios
from fintech_lab.p2_forecasting.bridge import contribution_bridge, fee_bridge, lmdi
from fintech_lab.p2_forecasting.config import d
from fintech_lab.p2_forecasting.reporting import md_table

TARGETS = {"tpv_total": "tpv", "net_revenue_total": "net", "contribution_total": "contribution"}
NAMES = {"tpv": "TPV", "net": "Net revenue", "contribution": "Contribution margin"}


def _load(data: Path) -> dict[str, pd.DataFrame]:
    rd = pd.read_parquet
    return {
        "monthly": rd(data / "fct_monthly.parquet"),
        "segment": rd(data / "fct_daily_segment.parquet"),
        "merchant": rd(data / "fct_daily_merchant.parquet"),
        "budget": rd(data / "budget_v1.parquet"),
        "holdout": rd(data / "backtest" / "fct_holdout_forecast.parquet"),
        "bt_fc": rd(data / "backtest" / "fct_backtest_forecast.parquet"),
        "bt_metrics": rd(data / "backtest" / "fct_backtest_metrics.parquet"),
    }


def _drivers(merchant: pd.DataFrame, start: date, end: date) -> dict[str, float]:
    dl = pd.to_datetime(merchant["date_local"])
    m = merchant[(dl >= pd.Timestamp(start)) & (dl <= pd.Timestamp(end))]
    active = m.loc[m["n_succeeded"] > 0, "merchant_id"].nunique()
    n, tpv = float(m["n_succeeded"].sum()), float(m["tpv_brl"].astype(float).sum())
    return {"active_merchants": float(active), "payments_per_merchant": n / active,
            "avg_ticket_brl": tpv / n}


def run_closing(
    data_dir: str | Path, assumptions: dict[str, Any], bt_cfg: dict[str, Any],
    scen_cfg: dict[str, Any], alert_cfg: dict[str, Any], champions_path: str | Path,
    reports_dir: str | Path,
) -> dict[str, Any]:
    data, rep = Path(data_dir), Path(reports_dir)
    rep.mkdir(parents=True, exist_ok=True)
    D = _load(data)
    champs = yaml.safe_load(Path(champions_path).read_text(encoding="utf-8"))["champions"]
    as_of = d(bt_cfg["as_of"])
    t4s, t4e = d(scen_cfg["horizon"]["start"]), d(scen_cfg["horizon"]["end"])

    # ---- the three states of the closing quarter, by country -----------------------------
    actual = pnl.actual_pl(D["monthly"], t4s, t4e)
    budget = pnl.budget_pl(D["budget"], assumptions, t4s, t4e)
    ho = D["holdout"]
    tpv_fc = pd.Series({
        c: float(ho[(ho["target"] == f"tpv_{c}") & (ho["model"] == champs[f"tpv_{c}"]["model"])
                    ]["yhat"].sum()) for c in pnl.COUNTRIES})
    ws, we = pnl.trailing_window(as_of, int(scen_cfg["ratios_window_days"]))
    train_pl = pnl.window_pl(D["segment"], ws, we)
    base_ratios = pnl.ratios(train_pl)
    forecast = pnl.pl_from_ratios(tpv_fc, base_ratios)

    direct = {t: float(ho[(ho["target"] == t) & (ho["model"] == champs[t]["model"])]["yhat"].sum())
              for t in TARGETS}
    head = []
    for t, col in TARGETS.items():
        a, b, f = (float(x[col].sum()) for x in (actual, budget, forecast))
        head.append({"metric": NAMES[col], "budget": b, "forecast_composed": f,
                     "forecast_direct_champion": direct[t], "actual": a,
                     "actual_vs_budget": a - b, "actual_vs_budget_pct": (a - b) / b,
                     "forecast_err_pct": (f - a) / a, "budget_err_pct": (b - a) / a,
                     "actual_vs_forecast_pct": (a - f) / f})
    headline = pd.DataFrame(head)

    mm = D["monthly"][["month", "country", "tpv_brl", "net_revenue_brl", "contribution_brl"]].copy()
    for c in ("tpv_brl", "net_revenue_brl", "contribution_brl"):
        mm[c] = mm[c].astype(float)
    mm = mm.rename(columns={c: f"actual_{c[:-4]}" for c in ("tpv_brl", "net_revenue_brl",
                                                             "contribution_brl")})
    b1 = D["budget"][["month", "country", "tpv_brl", "net_revenue_brl", "contribution_brl"]]
    b1 = b1.rename(columns={c: f"budget_v1_{c[:-4]}" for c in ("tpv_brl", "net_revenue_brl",
                                                                "contribution_brl")})
    monthly_summary = mm.merge(b1, on=["month", "country"], how="left")
    b2_path = data / "budget_v2.parquet"
    if b2_path.exists():
        b2 = pd.read_parquet(b2_path)[["month", "country", "tpv_brl", "net_revenue_brl",
                                       "contribution_brl"]]
        b2 = b2.rename(columns={c: f"budget_v2_{c[:-4]}" for c in ("tpv_brl", "net_revenue_brl",
                                                                    "contribution_brl")})
        monthly_summary = monthly_summary.merge(b2, on=["month", "country"], how="left")
    monthly_summary = monthly_summary.sort_values(["month", "country"]).reset_index(drop=True)
    budget2 = (pnl.pl_from_table(pd.read_parquet(b2_path), t4s, t4e) if b2_path.exists() else None)
    if budget2 is not None:
        rows2 = []
        for col in ("tpv", "net", "contribution"):
            a2, b1, b2 = (float(x[col].sum()) for x in (actual, budget, budget2))
            rows2.append({"metric": NAMES[col], "actual": a2, "budget_v1": b1, "budget_v2": b2,
                          "v1_err_pct": (b1 - a2) / a2, "v2_err_pct": (b2 - a2) / a2,
                          "forecast_composed": float(forecast[col].sum()),
                          "forecast_err_pct": (float(forecast[col].sum()) - a2) / a2})
        budget_cmp = pd.DataFrame(rows2)
    else:
        budget_cmp = None

    # ---- bridges ------------------------------------------------------------------------------
    bridges = {"budget_to_forecast": contribution_bridge(budget, forecast),
               "forecast_to_actual": contribution_bridge(forecast, actual),
               "budget_to_actual": contribution_bridge(budget, actual)}
    fee_parts = pd.DataFrame(
        {k: fee_bridge(x, y) for k, (x, y) in {
            "budget_to_forecast": (budget, forecast), "forecast_to_actual": (forecast, actual),
            "budget_to_actual": (budget, actual)}.items()}).T

    def _tot(pl: pd.DataFrame) -> dict[str, float]:
        t = pl[["tpv", "fee", "rc", "inc", "proc", "var"]].sum()
        return {"take_rate (fee/TPV)": t.fee / t.tpv, "refund+chargeback / fee": t.rc / t.fee,
                "incentives / TPV": t.inc / t.tpv, "processing cost / TPV": t.proc / t.tpv,
                "other variable cost / TPV": t["var"] / t.tpv}

    ratio_check = pd.DataFrame({"budget_v1": _tot(budget), "trailing_90d_at_as_of": _tot(train_pl),
                                "actual_t4": _tot(actual)}).rename_axis("ratio").reset_index()
    ratio_check["actual_vs_budget_rel"] = ratio_check["actual_t4"] / ratio_check["budget_v1"] - 1

    # ---- descriptive driver decomposition: Q3 -> T4 actual (LMDI) ---------------------------
    q3 = _drivers(D["merchant"], date(2025, 7, 1), date(2025, 9, 30))
    q4 = _drivers(D["merchant"], t4s, t4e)
    lm = lmdi(q3, q4)

    # ---- scenarios (assumptions) and the separate statistical band --------------------------
    scen = scenarios.scenarios_from_config(scen_cfg)
    stab = scenarios.scenario_table(tpv_fc, base_ratios, scen)
    if abs(float(stab.loc[stab["scenario"] == "base", "contribution"].iloc[0])
           - float(forecast["contribution"].sum())) > 1e-6:
        raise AssertionError("base scenario must equal the composed forecast")
    sens = scenarios.sensitivity(tpv_fc, base_ratios, float(scen_cfg["sensitivity"]["step"]),
                                 joint=scen["conservative"])
    bands = []
    for t, col in TARGETS.items():
        band = scenarios.statistical_band(D["bt_fc"], t, champs[t]["model"], as_of, 90,
                                          direct[t])
        bands.append({"metric": NAMES[col], "champion": champs[t]["model"], **band,
                      "actual": float(actual[col].sum()),
                      "actual_inside_band": band["implied_lo"] <= float(actual[col].sum())
                      <= band["implied_hi"]})
    band_df = pd.DataFrame(bands)
    pos = []
    for col in ("tpv", "net", "contribution"):
        a = float(actual[col].sum())
        row = stab.set_index("scenario")[col]
        pos.append({"metric": NAMES[col], "actual": a, "conservative": row["conservative"],
                    "base": row["base"], "optimistic": row["optimistic"],
                    "actual_inside_scenarios": row["conservative"] <= a <= row["optimistic"]})
    scen_pos = pd.DataFrame(pos)

    # ---- alerts ------------------------------------------------------------------------------
    rules = alert_cfg["rules"]
    mt = D["bt_metrics"]
    ytd_s = date(2025, 1, 1)
    ytd_a = float(pnl.actual_pl(D["monthly"], ytd_s, date(2025, 9, 1))["tpv"].sum())
    ytd_b = float(pnl.budget_pl(D["budget"], assumptions, ytd_s, date(2025, 9, 1))["tpv"].sum())
    bud_ratio = pnl.ratios(budget)
    merch = D["merchant"]
    dl = pd.to_datetime(merch["date_local"])
    tw = merch[(dl >= pd.Timestamp(ws)) & (dl <= pd.Timestamp(we))]
    top10 = (tw.groupby("merchant_id")["tpv_brl"].sum().astype(float).nlargest(10).sum()
             / float(tw["tpv_brl"].astype(float).sum()))
    ex_ante: list[dict[str, Any]] = []
    for col in ("tpv", "net", "contribution"):
        v = AL.rel(float(forecast[col].sum()), float(budget[col].sum()))
        ex_ante.append({"alert": "forecast_vs_budget", "scope": NAMES[col], "value": v,
                        "evidence": f"forecast {forecast[col].sum():,.0f} vs budget "
                                    f"{budget[col].sum():,.0f}"})
    for c in pnl.COUNTRIES:
        v = AL.rel(float(forecast.loc[c, "tpv"]), float(budget.loc[c, "tpv"]))
        ex_ante.append({"alert": "forecast_vs_budget", "scope": f"TPV {c}", "value": v,
                        "evidence": f"forecast {forecast.loc[c, 'tpv']:,.0f} vs budget "
                                    f"{budget.loc[c, 'tpv']:,.0f}"})
    ex_ante.append({"alert": "ytd_run_rate_gap", "scope": "TPV Jan-Sep",
                    "value": AL.rel(ytd_a, ytd_b),
                    "evidence": f"actual {ytd_a:,.0f} vs budget {ytd_b:,.0f}"})
    for t, col in TARGETS.items():
        m90 = mt[(mt["target"] == t) & (mt["model"] == champs[t]["model"]) & (mt["horizon"] == 90)]
        ex_ante.append({"alert": "model_reliability", "scope": NAMES[col],
                        "value": float(champs[t]["composite_wape"]),
                        "evidence": f"champion {champs[t]['model']}, validation composite WAPE"})
        ex_ante.append({"alert": "interval_coverage_80", "scope": NAMES[col],
                        "value": float(m90["cov80"].iloc[0]), "lower_is_worse": True,
                        "evidence": f"champion {champs[t]['model']}, 90-day backtest coverage"})
    for c in pnl.COUNTRIES:
        ex_ante.append({"alert": "take_rate_drift", "scope": c,
                        "value": AL.rel(float(base_ratios.loc[c, "take"]),
                                        float(bud_ratio.loc[c, "take"])),
                        "evidence": f"last-90d take {base_ratios.loc[c, 'take']:.4f} vs budget "
                                    f"{bud_ratio.loc[c, 'take']:.4f}"})
        ex_ante.append({"alert": "refund_cb_share_drift", "scope": c,
                        "value": AL.rel(float(base_ratios.loc[c, "rc_share"]),
                                        float(bud_ratio.loc[c, "rc_share"])),
                        "evidence": f"last-90d refund+cb/fee {base_ratios.loc[c, 'rc_share']:.4f} "
                                    f"vs budget {bud_ratio.loc[c, 'rc_share']:.4f}"})
    ex_ante.append({"alert": "merchant_concentration", "scope": "top-10 merchants", "value": top10,
                    "evidence": "share of TPV, last 90 days"})
    ex_post = []
    for col in ("tpv", "net", "contribution"):
        ex_post.append({"alert": "actual_vs_budget", "scope": NAMES[col],
                        "value": AL.rel(float(actual[col].sum()), float(budget[col].sum())),
                        "evidence": f"actual {actual[col].sum():,.0f} vs budget "
                                    f"{budget[col].sum():,.0f}"})
    act_ratio = pnl.ratios(actual)
    for c in pnl.COUNTRIES:
        ex_post.append({"alert": "take_rate_drift", "scope": c,
                        "value": AL.rel(float(act_ratio.loc[c, "take"]),
                                        float(bud_ratio.loc[c, "take"])),
                        "evidence": f"T4 take {act_ratio.loc[c, 'take']:.4f} vs budget "
                                    f"{bud_ratio.loc[c, 'take']:.4f}"})
    al_ante, al_post = AL.evaluate(ex_ante, rules), AL.evaluate(ex_post, rules)

    if budget2 is not None:
        bridges["budget_v2_to_actual"] = contribution_bridge(budget2, actual)
    out = {"monthly_summary": monthly_summary, "budget_cmp": budget_cmp, "budget2": budget2, "ratio_check": ratio_check, "headline": headline, "fee_parts": fee_parts, "lmdi": lm, "scenarios": stab,
           "scenario_position": scen_pos, "sensitivity": sens, "band": band_df,
           "alerts_ex_ante": al_ante, "alerts_ex_post": al_post, **bridges,
           "actual": actual, "budget": budget, "forecast": forecast,
           "q3_drivers": q3, "q4_drivers": q4, "base_tpv": tpv_fc, "base_ratios": base_ratios,
           "champions": champs, "as_of": as_of, "t4": (t4s, t4e)}
    _write(out, rep, scen_cfg, bt_cfg)
    return out


def _generator_seasonal_ref() -> str:
    try:
        g = yaml.safe_load(Path(P1_GENERATOR_CONFIG).read_text(encoding="utf-8"))
        mth = g["seasonality"]["month"]
        t4, q3 = sum(mth[9:12]) / 3, sum(mth[6:9]) / 3
        return (f"Fator sazonal mensal configurado no gerador sintético do P1 "
                f"(`seasonality.month`): "
                f"média Out-Dez {t4:.3f} vs Jul-Set {q3:.3f}, razão {t4 / q3:.3f}. "
                "É um parâmetro do gerador (verdade conhecida só porque os dados são sintéticos), "
                "não uma estimativa a partir dos dados.")
    except Exception:
        return "Fator sazonal do gerador indisponível [TO VERIFY]."


def _v2_section(o: dict[str, Any]) -> str:
    if o["budget_cmp"] is None:
        return ""
    c = o["budget_cmp"]
    t, m = c.iloc[0], c.iloc[2]
    return f"""**Orçamento v2 (reforecast congelado em 30/09, só com dados ≤ 30/09).** Regras em `configs/budget_v2_rules.yaml`: nível = TPV de setembro por dia e país, crescimento composto de abril a setembro, razões dos últimos 90 dias. Erro do TPV no trimestre: v1 {t.v1_err_pct:+.1%}, v2 {t.v2_err_pct:+.1%}, previsão composta {t.forecast_err_pct:+.1%}. Erro da margem: v1 {m.v1_err_pct:+.1%}, v2 {m.v2_err_pct:+.1%}, previsão composta {m.forecast_err_pct:+.1%} (erro = (plano − realizado) / realizado).

{md_table(c, pct=("v1_err_pct", "v2_err_pct", "forecast_err_pct"), money=("actual", "budget_v1", "budget_v2", "forecast_composed"))}

Ponte Orçamento v2 → Realizado:

{md_table(o["budget_v2_to_actual"], money=("effect",))}

"""


def _top(bridge: pd.DataFrame, n: int = 3) -> str:
    b = bridge[bridge["kind"].isin(["fee", "cost"])].copy()
    b["abs"] = b["effect"].abs()
    return "; ".join(f"{r.step} ({r.effect:+,.0f})" for r in b.nlargest(n, "abs").itertuples())


def _write(o: dict[str, Any], rep: Path, scen_cfg: dict, bt_cfg: dict) -> None:
    for k in ("ratio_check", "headline", "fee_parts", "lmdi", "scenarios", "scenario_position", "sensitivity",
              "band", "alerts_ex_ante", "alerts_ex_post", "budget_to_forecast",
              "forecast_to_actual", "budget_to_actual"):
        df = o[k]
        df.to_csv(rep / f"p24_{k}.csv", index=k == "fee_parts")
    o["monthly_summary"].to_csv(rep / "monthly_actual_vs_budget.csv", index=False)
    if o["budget_cmp"] is not None:
        o["budget_cmp"].to_csv(rep / "p24_budget_v1_v2_actual.csv", index=False)
        o["budget_v2_to_actual"].to_csv(rep / "p24_budget_v2_to_actual.csv", index=False)
    h = o["headline"].set_index("metric")
    tpv, con = h.loc["TPV"], h.loc["Contribution margin"]
    n_red = (o["alerts_ex_ante"]["severity"] == "red").sum()
    n_amb = (o["alerts_ex_ante"]["severity"] == "amber").sum()
    lm = o["lmdi"].set_index("driver")
    inter = o["sensitivity"].attrs.get("interaction", {})
    money = ("budget", "forecast_composed", "forecast_direct_champion", "actual",
             "actual_vs_budget")
    pct = ("actual_vs_budget_pct", "forecast_err_pct", "budget_err_pct", "actual_vs_forecast_pct")
    text = f"""# P2 — Relatório executivo de fechamento T4/2025

> Dados 100% sintéticos (P1 + refund/chargeback/orçamento sintéticos). Receita e margem são estimativas `[TO VERIFY]`. Todos os números abaixo foram calculados por `python -m fintech_lab.p2_forecasting.cli close`; o texto só descreve esses valores. Nenhuma afirmação causal.

## 1. Resultado do trimestre (01/10–31/12/2025, BRL)
O TPV realizado foi {tpv.actual:,.0f}: {tpv.actual_vs_budget_pct:+.1%} em relação ao orçamento v1 ({tpv.budget:,.0f}) e {tpv.actual_vs_forecast_pct:+.1%} em relação à previsão composta feita em 2025-09-30 ({tpv.forecast_composed:,.0f}). A margem de contribuição realizada foi {con.actual:,.0f}, contra {con.budget:,.0f} orçados ({con.actual_vs_budget_pct:+.1%}) e {con.forecast_composed:,.0f} previstos.

{md_table(o["headline"], pct=pct, money=money)}

*Previsão composta* = previsão do campeão de TPV por país × razões dos últimos {scen_cfg["ratios_window_days"]} dias até o as-of (take rate, refund+chargeback/fee, custos/TPV). *Previsão direta* = campeão de cada alvo (P2.3). As duas diferem por construção; a ponte e os cenários usam a composta.

## 2. O que o as-of de 30/09 já sinalizava (alertas ex-ante)
{n_red} alertas vermelhos e {n_amb} amarelos, com limites em `configs/alerts.yaml` (números redondos fixados antes de olhar o T4; não calibrados ao resultado).

{md_table(o["alerts_ex_ante"][o["alerts_ex_ante"]["severity"].isin(["red", "amber"])], pct=("value", "amber", "red"))}

Alertas ex-post (realizado vs orçamento):

{md_table(o["alerts_ex_post"], pct=("value", "amber", "red"))}

## 3. Ponte da margem de contribuição
Convenção: efeitos puros sobre o estado de referência (volume ao take rate médio de referência; mix = mudança de participação entre países às taxas de referência; taxa = mudança de take rate às participações de referência) e uma linha explícita de **interação** (termos de 2ª e 3ª ordem). A ponte fecha com a variação total; resíduo = 0 dentro da tolerância numérica. Custos: parte de volume (ΔTPV × custo/TPV de referência) e parte de taxa/mix.

**Orçamento → Realizado.** Maiores efeitos: {_top(o["budget_to_actual"])}.

{md_table(o["budget_to_actual"], money=("effect",))}

**Orçamento → Previsão** (diferença entre os dois planos): {_top(o["budget_to_forecast"])}.

**Previsão → Realizado** (decomposição do erro de previsão): {_top(o["forecast_to_actual"])}.

{md_table(o["forecast_to_actual"], money=("effect",))}

**Premissas de razão do orçamento v1 vs. observado.** O orçamento fixou, no P2.1, custo de processamento e refund+chargeback sem calibrá-los contra o P1; os dados mostram:

{md_table(o["ratio_check"], pct=("actual_vs_budget_rel",), digits=4)}

Isto é uma diferença aritmética entre premissas e razões observadas. Os efeitos "rate/mix" de processamento e de refund+chargeback na ponte acima vêm dessa diferença. Esse erro **não** estava entre os erros propositais declarados (crescimento e mix de take rate); a ponte de TPV (volume) reflete o erro declarado de crescimento.

Receita de fee, Orçamento → Realizado (puros + interação): {", ".join(f"{k} {v:+,.0f}" for k, v in o["fee_parts"].loc["budget_to_actual"].items())}.

{_v2_section(o)}
## 4. O que mudou no volume: Jul–Set → Out–Dez (LMDI, descritivo)
TPV = merchants com venda × pagamentos/merchant × ticket médio. Os efeitos somam exatamente a variação de TPV entre os dois trimestres (interações repartidas simetricamente).

{md_table(o["lmdi"], money=("effect",), digits=2)}

Merchants com venda: {o["q3_drivers"]["active_merchants"]:.0f} → {o["q4_drivers"]["active_merchants"]:.0f}; pagamentos por merchant: {lm.loc["payments_per_merchant", "from"]:.1f} → {lm.loc["payments_per_merchant", "to"]:.1f}; ticket médio: {lm.loc["avg_ticket_brl", "from"]:.2f} → {lm.loc["avg_ticket_brl", "to"]:.2f}.

{_generator_seasonal_ref()}

## 5. Cenários (hipóteses de negócio) e banda estatística (separadas)
**Cenários** (`configs/scenarios.yaml`) são premissas sobre merchants, volume/merchant, ticket, take rate, refund+chargeback, custos. Não são intervalos de probabilidade nem foram calibrados para cobrir o realizado.

{md_table(o["scenarios"], money=("tpv", "fee", "rc", "inc", "proc", "var", "net", "contribution"))}

Posição do realizado frente aos cenários:

{md_table(o["scenario_position"], money=("actual", "conservative", "base", "optimistic"))}

**Banda estatística** (previsão direta do campeão ± erros empíricos da soma de 90 dias no backtest; quantis 10–90%; as janelas se sobrepõem, n pequeno):

{md_table(o["band"][["metric", "champion", "n_origins", "err_q_lo", "err_q_hi", "implied_lo", "point", "implied_hi", "actual", "actual_inside_band"]], money=("implied_lo", "point", "implied_hi", "actual"), digits=3)}

Cenário e banda medem coisas diferentes: o cenário muda hipóteses de negócio; a banda mede só o erro histórico de previsão do modelo dentro do padrão visto até setembro.

## 6. Sensibilidade (um driver por vez, ±{scen_cfg["sensitivity"]["step"]:.0%})
{md_table(o["sensitivity"], money=("d_tpv", "d_net", "d_contribution"), digits=2)}

Interação do cenário conservador (efeito conjunto − soma dos efeitos individuais): TPV {inter.get("tpv", float("nan")):+,.0f}; net revenue {inter.get("net", float("nan")):+,.0f}; margem {inter.get("contribution", float("nan")):+,.0f}.

## 7. Limites
- Um ano de histórico sintético; um único trimestre de teste. Nada aqui é desempenho real nem estatística de longo prazo.
- Refund, chargeback, incentivos, custo variável e orçamento são premissas sintéticas (`assumptions.yaml`), e o orçamento v1 tem erro proposital declarado: toda variação contra ele é sintética por construção.
- Custo de processamento é tratado como proporção do TPV (as retentativas não são modeladas como driver separado).
- A previsão composta usa razões dos últimos {scen_cfg["ratios_window_days"]} dias; chargebacks têm atraso de 15–60 dias, então a razão no as-of é uma leitura em base de data de evento.
- Pontes explicam a diferença aritmética; não provam causa.
"""
    (rep / "executive_closing_report.md").write_text(text, encoding="utf-8")
