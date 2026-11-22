"""P2 TPV / Revenue / Margin forecasting cockpit (Streamlit). All data is SYNTHETIC.

Run: python -m fintech_lab.p2_forecasting.cli dashboard

Everything shown is read from the exports of the P2 pipeline (frozen budgets, frozen champions,
holdout forecasts). Sidebar filters change only what is displayed; they never refit a model or
change a threshold. Scenario sliders re-run the deterministic scenario engine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fintech_lab.p2_forecasting import dashboard_data as dd
from fintech_lab.p2_forecasting import metrics as M
from fintech_lab.p2_forecasting import scenarios as sc
from fintech_lab.p2_forecasting.config import DEFAULT_OUT, P2_ROOT
from fintech_lab.p2_forecasting.onepager import REPO_ROOT, build_onepager
from fintech_lab.p2_forecasting.pipeline import artifacts_ready

DATA_ROOT = Path(os.environ.get("P2_DATA_ROOT", DEFAULT_OUT))
CONFIG_DIR = Path(os.environ.get("P2_CONFIG_DIR", P2_ROOT / "configs"))
TOKENS = json.loads((REPO_ROOT / "shared" / "design_tokens" / "tokens.json").read_text())
C = TOKENS["color"]
SERIES_COLOR = {"Actual": "#1B1F24", "Forecast": "#eb6834", "Budget v1": "#8a8f98",
                "Budget v2": "#2a78d6", "Train": "#5B6470"}  # fixed per series, never by rank
SEV_COLOR = {"red": C["negative"], "amber": C["warning"], "ok": C["positive"], "n/a": C["muted"]}
TARGETS = {"TPV": "tpv_total", "Net revenue": "net_revenue_total",
           "Contribution margin": "contribution_total", "TPV BR": "tpv_BR", "TPV MX": "tpv_MX",
           "TPV CL": "tpv_CL"}
MODELS = ["naive", "snaive", "ma7", "ma28", "ets", "sarima"]

st.set_page_config(page_title="P2 · Forecasting cockpit", page_icon="📈", layout="wide")
st.markdown(
    f"""<style>
    html, body, [class*="css"] {{ font-family: {TOKENS["font"]["family"]}; }}
    .synthetic-badge {{ display:inline-block; padding:2px 10px; border-radius:999px;
        background:{C["surface"]}; color:{C["text"]}; border:1px solid {C["muted"]};
        font-size:0.8rem; font-weight:600; }}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
        color:{C["muted"]} !important; opacity:1 !important; }}
    div[data-testid="stMetric"] {{ background:{C["surface"]}; border-radius:8px;
        padding:10px 14px; }}
    .infobar {{ display:flex; flex-wrap:wrap; gap:10px; margin:6px 0 14px; }}
    .info {{ flex:1 1 150px; background:{C["surface"]}; border-radius:8px; padding:8px 12px; }}
    .info span {{ display:block; font-size:0.8rem; color:{C["muted"]}; }}
    .info b {{ font-size:1.05rem; color:{C["text"]}; }}
    </style>""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Loading P2 artifacts and recomputing the closing tables…")
def bundle(data: str, cfg: str) -> dict:
    return dd.load_bundle(data, cfg)


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=48, b=10),
                      font=dict(family=TOKENS["font"]["family"], color=C["text"], size=13),
                      legend=dict(orientation="h", y=-0.2))
    return fig


def money(v: float) -> str:
    return "n/a" if v != v else f"{v:,.0f}"


def pct(v: float) -> str:
    return "n/a" if v != v else f"{v:+.1%}"


def download(df: pd.DataFrame, name: str, key: str) -> None:
    st.download_button(f"Download {name}.csv", df.to_csv(index=False).encode("utf-8"),
                       f"{name}.csv", "text/csv", key=key)


st.markdown("# P2 · TPV, Revenue & Margin Forecasting")
st.markdown('<span class="synthetic-badge">SYNTHETIC DATA</span>', unsafe_allow_html=True)
st.caption("Built on synthetic P1 payments plus synthetic refunds/chargebacks and budgets. Revenue "
           "and margin are estimates [TO VERIFY]; nothing here is a real result.")

if not artifacts_ready(DATA_ROOT) or not (CONFIG_DIR / "champions_b1.yaml").exists():
    st.error(f"P2 artifacts not found in {DATA_ROOT}. Run "
             "`python -m fintech_lab.p2_forecasting.cli pipeline` (or `cli dashboard`).")
    st.stop()

B = bundle(str(DATA_ROOT), str(CONFIG_DIR))
CLS, BT = B["o"], B["bt_cfg"]
as_of = pd.Timestamp(BT["as_of"])
t4s, t4e = (pd.Timestamp(x) for x in CLS["t4"])
champs = {k: v["model"] for k, v in CLS["champions"].items()}
hmax = BT["max_horizon"]
last_day = B["total"]["date_local"].max()

with st.sidebar:
    st.markdown("### Filters")
    period = st.date_input("Period (local dates)", (B["total"]["date_local"].min().date(),
                                                    last_day.date()),
                           min_value=B["total"]["date_local"].min().date(),
                           max_value=last_day.date())
    countries = st.multiselect("Country", ["BR", "CL", "MX"])
    methods = st.multiselect("Payment method", sorted(B["segment"]["method_code"].unique()))
    tiers = st.multiselect("Merchant size tier", sorted(B["segment"]["size_tier"].unique()))
    md = B["merchant_dim"].sort_values("merchant_id")
    merchants = st.multiselect("Merchant (overrides the method filter)", md["merchant_id"].tolist())
    grain = st.radio("Time grain", ["Day", "Week", "Month"], index=1, horizontal=True)
    metric_label = st.selectbox("Metric", list(dd.METRICS), index=0)
    target_label = st.selectbox("Forecast target", list(TARGETS), index=0)
    target = TARGETS[target_label]
    model = st.selectbox("Model (forecast & comparison tabs)", MODELS,
                         index=MODELS.index(champs[target]),
                         help="Default = frozen champion for the target")
    st.caption("Filters change what is displayed. Models, budgets and thresholds are frozen.")

infos = [("Data cut-off", str(as_of.date())), ("Last training day", str(as_of.date())),
         ("Forecast horizon", f"{hmax} days"), ("Backtest / budgets", f"{BT['version']} · v1 + v2"),
         (f"Champion · {target_label}", champs[target])]
st.markdown('<div class="infobar">' + "".join(
    f'<div class="info"><span>{k}</span><b>{v}</b></div>' for k, v in infos) + "</div>",
    unsafe_allow_html=True)

tabs = st.tabs(["Closing", "History", "Forecast & intervals", "Models", "Scenarios",
                "Variance bridge", "Risk alerts", "About & export"])

# ---------------------------------------------------------------- Closing
with tabs[0]:
    h = CLS["headline"].set_index("metric")
    st.markdown(f"### Closing quarter {t4s.date()} → {t4e.date()} (BRL)")
    cols = st.columns(3)
    for col, name in zip(cols, ["TPV", "Net revenue", "Contribution margin"], strict=True):
        r = h.loc[name]
        col.metric(name, money(r.actual), f"{r.actual_vs_budget_pct:+.1%} vs budget v1",
                   delta_color="off")
        col.caption(f"Forecast (composed): {money(r.forecast_composed)} · "
                    f"actual vs forecast {pct(r.actual_vs_forecast_pct)}")
    cmp_ = CLS["budget_cmp"]
    plans = pd.DataFrame({
        "Plan": ["Actual", "Budget v1", "Budget v2", "Forecast"],
        "TPV": [h.loc["TPV", "actual"], h.loc["TPV", "budget"],
                cmp_.iloc[0].budget_v2 if cmp_ is not None else float("nan"),
                h.loc["TPV", "forecast_composed"]]})
    fig = go.Figure(go.Bar(x=plans["Plan"], y=plans["TPV"],
                           marker_color=[SERIES_COLOR[p] for p in plans["Plan"]],
                           text=[f"{v / 1e6:.2f}M" for v in plans["TPV"]], textposition="outside"))
    st.plotly_chart(style(fig.update_layout(title="TPV: actual vs plans", yaxis_title="BRL")),
                    width="stretch")
    st.dataframe(CLS["headline"].style.format({c: "{:,.0f}" for c in (
        "budget", "forecast_composed", "forecast_direct_champion", "actual", "actual_vs_budget")}
        | {c: "{:+.1%}" for c in ("actual_vs_budget_pct", "forecast_err_pct", "budget_err_pct",
                                  "actual_vs_forecast_pct")}), hide_index=True)
    if cmp_ is not None:
        st.markdown("**Budget v1 vs v2 vs forecast** (error = (plan − actual) / actual)")
        st.dataframe(cmp_.style.format({c: "{:,.0f}" for c in (
            "actual", "budget_v1", "budget_v2", "forecast_composed")} | {
            c: "{:+.1%}" for c in ("v1_err_pct", "v2_err_pct", "forecast_err_pct")}),
            hide_index=True)
    by_c = pd.DataFrame({"Actual": CLS["actual"]["tpv"], "Budget v1": CLS["budget"]["tpv"],
                         "Forecast": CLS["forecast"]["tpv"]})
    if CLS["budget2"] is not None:
        by_c["Budget v2"] = CLS["budget2"]["tpv"]
    fig2 = go.Figure([go.Bar(name=c, x=by_c.index, y=by_c[c], marker_color=SERIES_COLOR[c])
                      for c in by_c.columns])
    st.plotly_chart(style(fig2.update_layout(barmode="group", title="TPV by country")),
                    width="stretch")

# ---------------------------------------------------------------- History
with tabs[1]:
    p0, p1 = (period[0], period[-1]) if len(period) else (None, None)
    hist = dd.history(B, p0, p1 if len(period) == 2 else p0, countries, methods, tiers, merchants)
    if merchants and methods:
        st.warning("Merchant data has no payment method: the method filter is ignored while "
                   "merchants are selected.")
    if hist.empty or hist["tpv_brl"].sum() == 0:
        st.info("No data for this combination of filters.")
    else:
        g = dd.regrain(hist, grain)
        col = dd.METRICS[metric_label]
        fig = go.Figure(go.Scatter(x=g["date_local"], y=g[col], mode="lines",
                                   name="Actual", line=dict(color=SERIES_COLOR["Actual"])))
        simple = not (methods or tiers or merchants)
        if grain == "Month" and col == "tpv_brl" and simple:
            ms = CLS["monthly_summary"].copy()
            ms["month"] = pd.to_datetime(ms["month"])
            ms = ms[ms["country"].isin(countries or ["BR", "CL", "MX"])].groupby("month")[
                ["budget_v1_tpv"]].sum().reset_index()
            fig.add_trace(go.Scatter(x=ms["month"], y=ms["budget_v1_tpv"], name="Budget v1",
                                     mode="lines+markers",
                                     line=dict(color=SERIES_COLOR["Budget v1"], dash="dot")))
        fig.add_vline(x=as_of, line_dash="dash", line_color=C["muted"])
        fig.add_annotation(x=as_of, y=1, yref="paper", text="cut-off", showarrow=False,
                           xanchor="right", font=dict(color=C["muted"]))
        st.plotly_chart(style(fig.update_layout(title=f"{metric_label} by {grain.lower()}",
                                                yaxis_title="BRL")), width="stretch")
        fig2 = go.Figure(go.Scatter(x=g["date_local"], y=g["take_rate"], mode="lines",
                                    line=dict(color=SERIES_COLOR["Actual"])))
        st.plotly_chart(style(fig2.update_layout(title="Take rate (Σ fee / Σ TPV)",
                                                 yaxis_tickformat=".2%"), 260),
                        width="stretch")
        k = st.columns(3)
        k[0].metric("TPV in view", money(hist["tpv_brl"].sum()))
        k[1].metric("Fee revenue in view", money(hist["fee_brl"].sum()))
        k[2].metric("Take rate in view", f"{hist['fee_brl'].sum() / hist['tpv_brl'].sum():.2%}")
        st.caption("Ratios are sums over the view (never averages of daily ratios). Net revenue "
                   "and contribution follow contract F08/F11.")
        download(g, "history_filtered", "dl_hist")

# ---------------------------------------------------------------- Forecast
with tabs[2]:
    f = dd.forecast_path(B, target, model)
    if target == "tpv_total":
        hist_y = B["total"].set_index("date_local")["tpv_brl"]
    elif target == "net_revenue_total":
        hist_y = B["total"].set_index("date_local")["net_revenue_brl"]
    elif target == "contribution_total":
        hist_y = B["total"].set_index("date_local")["contribution_brl"]
    else:
        c = target.split("_")[1]
        hist_y = B["segment"][B["segment"]["country"] == c].groupby("date_local")["tpv_brl"].sum()
    train = hist_y[(hist_y.index <= as_of) & (hist_y.index >= as_of - pd.Timedelta(days=120))]
    fig = go.Figure()
    for lvl, a in (("95", 0.12), ("80", 0.25)):
        fig.add_trace(go.Scatter(x=pd.concat([f["date"], f["date"][::-1]]),
                                 y=pd.concat([f[f"hi{lvl}"], f[f"lo{lvl}"][::-1]]), fill="toself",
                                 fillcolor=f"rgba(235,104,52,{a})", line=dict(width=0),
                                 name=f"{lvl}% interval", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=train.index, y=train.values, name="Train (last 120 d)",
                             line=dict(color=SERIES_COLOR["Train"])))
    fig.add_trace(go.Scatter(x=f["date"], y=f["yhat"], name=f"Forecast ({model})",
                             line=dict(color=SERIES_COLOR["Forecast"])))
    fig.add_trace(go.Scatter(x=f["date"], y=f["actual"], name="Actual (holdout)",
                             line=dict(color=SERIES_COLOR["Actual"])))
    st.plotly_chart(style(fig.update_layout(title=f"{target_label}: {model} from {as_of.date()}",
                                            yaxis_title="BRL"), 420), width="stretch")
    a_sum, f_sum = float(f["actual"].sum()), float(f["yhat"].sum())
    k = st.columns(4)
    k[0].metric("92-day forecast", money(f_sum), pct((f_sum - a_sum) / a_sum) + " vs actual",
                delta_color="off")
    k[1].metric("Daily WAPE (holdout)", f"{M.wape(f['actual'], f['yhat']):.1%}")
    k[2].metric("80% interval coverage", f"{M.coverage(f['actual'], f['lo80'], f['hi80']):.0%}"
                if f["lo80"].notna().any() else "n/a")
    k[3].metric("95% interval coverage", f"{M.coverage(f['actual'], f['lo95'], f['hi95']):.0%}"
                if f["lo95"].notna().any() else "n/a")
    m90 = B["bt_metrics"]
    m90 = m90[(m90["target"] == target) & (m90["model"] == model)]
    st.markdown("**Historical error of this model (rolling-origin backtest, validation only)**")
    st.dataframe(m90[["horizon", "n_origins", "wape", "bias", "cov80", "cov95", "sec_per_fit"]]
                 .style.format({"wape": "{:.1%}", "bias": "{:+.1%}", "cov80": "{:.0%}",
                                "cov95": "{:.0%}", "sec_per_fit": "{:.2f}"}), hide_index=True)
    st.caption("Intervals describe the noise seen in the training window. They cannot anticipate a "
               "regime change such as seasonal peaks that the history never contained.")
    download(f.drop(columns=["step"], errors="ignore"), f"forecast_{target}_{model}", "dl_fc")

# ---------------------------------------------------------------- Models
with tabs[3]:
    mt = B["bt_metrics"][B["bt_metrics"]["target"] == target].copy()
    hz = st.radio("Horizon (days)", sorted(mt["horizon"].unique()), horizontal=True, index=1)
    sel = mt[mt["horizon"] == hz].set_index("model").reindex(MODELS).reset_index()
    fig = go.Figure(go.Bar(x=sel["model"], y=sel["wape"],
                           marker_color=[SERIES_COLOR["Forecast"] if m == champs[target]
                                         else SERIES_COLOR["Budget v1"] for m in sel["model"]],
                           text=[f"{v:.1%}" for v in sel["wape"]], textposition="outside"))
    st.plotly_chart(style(fig.update_layout(title=f"Validation WAPE at {hz} days · {target_label} "
                                            "(champion highlighted)", yaxis_tickformat=".0%")),
                    width="stretch")
    st.dataframe(sel[["model", "n_origins", "mae", "rmse", "wape", "bias", "wape_sd_origins",
                      "cov80", "cov95", "width80", "sec_per_fit"]].style.format({
        "mae": "{:,.0f}", "rmse": "{:,.0f}", "wape": "{:.1%}", "bias": "{:+.1%}",
        "wape_sd_origins": "{:.1%}", "cov80": "{:.0%}", "cov95": "{:.0%}", "width80": "{:,.0f}",
        "sec_per_fit": "{:.2f}"}), hide_index=True)
    ho = B["holdout"][B["holdout"]["target"] == target]
    hrows = [{"model": m, "T4 daily WAPE": M.wape(x["actual"], x["yhat"]),
              "T4 total error": (x["yhat"].sum() - x["actual"].sum()) / x["actual"].sum()}
             for m, x in ho.groupby("model")]
    st.markdown("**Holdout T4 (shown for transparency; never used to select a model)**")
    st.dataframe(pd.DataFrame(hrows).style.format({"T4 daily WAPE": "{:.1%}",
                                                   "T4 total error": "{:+.1%}"}), hide_index=True)
    st.caption("Selection rule: composite WAPE over 7/30/90 days on validation only; a complex "
               "model must beat the best baseline by more than one paired standard error.")
    download(mt, f"backtest_metrics_{target}", "dl_mt")

# ---------------------------------------------------------------- Scenarios
with tabs[4]:
    st.markdown("### Business scenarios (assumptions, not prediction intervals)")
    presets = {k: v for k, v in B["scen_cfg"]["scenarios"].items()}
    names = [*presets, "custom"]
    pick = st.selectbox("Preset", names, index=1)
    start = presets.get(pick, presets["base"])
    labels = {"merchants": "Active merchants", "volume_per_merchant": "Payments per merchant",
              "ticket": "Average ticket", "take_rate": "Take rate",
              "refund_cb": "Refund + chargeback share of fee", "proc_cost": "Processing cost / TPV",
              "var_cost": "Other variable cost / TPV"}
    adj = {}
    cols = st.columns(4)
    for i, (k, lab) in enumerate(labels.items()):
        adj[k] = cols[i % 4].slider(lab, -30, 30, int(round(start[k] * 100)), 1,
                                    format="%d%%", key=f"s_{pick}_{k}") / 100
    pl = sc.apply_scenario(CLS["base_tpv"], CLS["base_ratios"], adj)
    tot = pl[["tpv", "net", "contribution"]].sum()
    h = CLS["headline"].set_index("metric")
    out = pd.DataFrame({
        "metric": ["TPV", "Net revenue", "Contribution margin"],
        "scenario": [tot.tpv, tot.net, tot.contribution],
        "forecast base": [h.loc[m, "forecast_composed"] for m in
                          ("TPV", "Net revenue", "Contribution margin")],
        "budget v1": [h.loc[m, "budget"] for m in ("TPV", "Net revenue", "Contribution margin")],
        "actual": [h.loc[m, "actual"] for m in ("TPV", "Net revenue", "Contribution margin")]})
    out["scenario vs base"] = out["scenario"] / out["forecast base"] - 1
    st.dataframe(out.style.format({c: "{:,.0f}" for c in ("scenario", "forecast base", "budget v1",
                                                          "actual")} | {"scenario vs base": "{:+.1%}"}),
                 hide_index=True)
    st.caption("TPV = merchants × payments/merchant × ticket (a product: interactions are "
               "explicit). Scenario values were fixed before comparing with the realized quarter.")
    st.markdown("### Statistical band (separate from the scenarios)")
    st.dataframe(CLS["band"][["metric", "champion", "n_origins", "implied_lo", "point", "implied_hi",
                            "actual", "actual_inside_band"]].style.format({
        c: "{:,.0f}" for c in ("implied_lo", "point", "implied_hi", "actual")}), hide_index=True)
    st.caption("Empirical 10–90% band from backtest 90-day window-sum errors of the frozen "
               "champion (overlapping windows, small n). It measures model error, not business "
               "hypotheses.")
    s = CLS["sensitivity"]
    s = s[s["change"] > 0].copy()
    fig = go.Figure(go.Bar(y=s["driver"], x=s["d_contribution"], orientation="h",
                           marker_color=C["primary"]))
    st.plotly_chart(style(fig.update_layout(title=f"Contribution impact of +"
                                            f"{B['scen_cfg']['sensitivity']['step']:.0%} on one "
                                            "driver (others at base)", xaxis_title="BRL"), 320),
                    width="stretch")
    download(CLS["scenarios"], "scenarios", "dl_sc")

# ---------------------------------------------------------------- Variance bridge
with tabs[5]:
    options = {"Budget v1 → Actual": "budget_to_actual", "Budget v1 → Forecast": "budget_to_forecast",
               "Forecast → Actual": "forecast_to_actual"}
    if CLS["budget2"] is not None:
        options["Budget v2 → Actual"] = "budget_v2_to_actual"
    which = st.selectbox("Bridge", list(options))
    br = CLS[options[which]]
    meas = ["absolute" if k == "start" else "total" if k == "end" else "relative"
            for k in br["kind"]]
    fig = go.Figure(go.Waterfall(x=br["step"], y=br["effect"], measure=meas,
                                 increasing=dict(marker=dict(color=C["positive"])),
                                 decreasing=dict(marker=dict(color=C["negative"])),
                                 totals=dict(marker=dict(color=C["muted"]))))
    st.plotly_chart(style(fig.update_layout(title=f"Contribution margin bridge: {which}",
                                            xaxis_tickangle=-35), 460), width="stretch")
    resid = float(br.loc[br["kind"] == "residual", "effect"].iloc[0])
    st.caption(f"Closes with the total variation (residual {resid:+.4f}). Fee effects are pure "
               "volume / country mix / take rate plus an explicit interaction term; costs split "
               "into volume and rate/mix. Arithmetic, not causes.")
    st.dataframe(br.style.format({"effect": "{:+,.0f}"}), hide_index=True)
    st.markdown("**TPV drivers, Jul–Sep → Oct–Dec actual (LMDI, descriptive)**")
    st.dataframe(CLS["lmdi"].style.format({"from": "{:,.2f}", "to": "{:,.2f}", "effect": "{:+,.0f}"}),
                 hide_index=True)
    st.markdown("**Budget v1 ratios vs observed**")
    st.dataframe(CLS["ratio_check"].style.format({
        c: "{:.4f}" for c in ("budget_v1", "trailing_90d_at_as_of", "actual_t4")}
        | {"actual_vs_budget_rel": "{:+.1%}"}), hide_index=True)
    download(br, f"bridge_{options[which]}", "dl_br")

# ---------------------------------------------------------------- Alerts
with tabs[6]:
    def sev_style(v: str) -> str:
        return f"color: {SEV_COLOR.get(v, C['text'])}; font-weight: 600"

    for title, key in (("At the cut-off (ex-ante, information ≤ cut-off only)", "alerts_ex_ante"),
                       ("After the close (ex-post)", "alerts_ex_post")):
        a = CLS[key]
        n = a["severity"].value_counts().to_dict()
        st.markdown(f"### {title}")
        st.caption(f"red {n.get('red', 0)} · amber {n.get('amber', 0)} · ok {n.get('ok', 0)}")
        st.dataframe(a.style.map(sev_style, subset=["severity"]).format(
            {"value": "{:+.3f}", "amber": "{:.2f}", "red": "{:.2f}"}), hide_index=True)
        download(a, key, f"dl_{key}")
    st.caption("Thresholds live in configs/alerts.yaml (edit and rerun `cli close`). Severity is "
               "colour AND text. Generic round numbers set before looking at T4.")

# ---------------------------------------------------------------- About & export
with tabs[7]:
    man = B["manifest"]
    st.markdown("### About the data")
    st.markdown(
        "- **Source:** P1 synthetic payments (seed " f"{man['p1']['seed']}) aggregated to daily "
        "series by merchant, segment and total, in BRL (FX of the local creation date).\n"
        "- **Labels:** payments, fees, costs = `synthetic`/`derived`; refunds, chargebacks, "
        "incentives, variable costs and both budgets = `synthetic` assumptions.\n"
        "- **Metric contracts:** TPV counts successful payments once (never attempts); take rate "
        "= Σ fee / Σ TPV; net revenue and contribution follow F08/F11; WAPE/Bias by ratio of sums, "
        "Bias > 0 = over-forecast.\n"
        f"- **Cut-off / training day:** {as_of.date()}; horizon {hmax} days; splits "
        f"{man['splits']}.\n"
        f"- **Versions:** assumptions {man['assumptions_version']}, backtest {BT['version']}, "
        f"budget v1 (as-of 2024-12-31, frozen, purposeful growth/mix error), budget v2 (as-of "
        f"{as_of.date()}, run-rate, frozen).\n"
        "- **Known limits:** one year of history (no annual seasonality learnable); one holdout "
        "quarter; budget v1 processing-cost and refund+chargeback assumptions were not calibrated "
        "to P1; holidays are a curated rule set [TO VERIFY]; scenarios are assumptions.")
    st.json({"mart_checks": man["checks"], "tables": {k: v["rows"] for k, v in
                                                       man["tables"].items()}}, expanded=False)
    st.markdown("### Export")
    c1, c2, c3 = st.columns(3)
    with c1:
        download(CLS["monthly_summary"], "monthly_actual_vs_budget", "dl_monthly")
        download(CLS["headline"], "closing_headline", "dl_head")
    with c2:
        download(CLS["budget_to_actual"], "bridge_budget_to_actual", "dl_b2a")
        download(CLS["scenarios"], "scenarios_table", "dl_sc2")
    with c3:
        meta = {"as_of": str(as_of.date()), "backtest_version": BT["version"],
                "assumptions_version": man["assumptions_version"], "p1_seed": man["p1"]["seed"]}
        st.download_button("Download executive one-pager (HTML)",
                           build_onepager(CLS, meta).encode("utf-8"), "p2_executive_one_pager.html",
                           "text/html", key="dl_onepager")
