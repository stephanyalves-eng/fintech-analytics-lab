"""P1 Payment Intelligence dashboard (Streamlit).

Run: python -m fintech_lab.p1_payments.cli dashboard

All data is SYNTHETIC (generated); every figure here is derived from it. Fees / take rate /
contribution depend on a synthetic MDR and are [TO VERIFY] — not real revenue.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from fintech_lab.p1_payments import dashboard_data as dd
from fintech_lab.p1_payments import diagnostics as dg
from fintech_lab.p1_payments import scenarios as sc
from fintech_lab.p1_payments.generator import REPO_ROOT

DB_PATH = Path(os.environ.get("P1_DB_PATH", REPO_ROOT / "data" / "p1" / "p1.duckdb"))
DATA_DIR = Path(os.environ.get("P1_DATA_DIR", REPO_ROOT / "data" / "p1" / "default"))
TOKENS = json.loads((REPO_ROOT / "shared" / "design_tokens" / "tokens.json").read_text())
C = TOKENS["color"]
# Categorical slots in fixed order (validated: adjacent CVD ΔE >= 9.1, light surface).
# Colour follows the entity, never its rank, so filtering never repaints survivors.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
COUNTRY_COLORS = {"BR": SERIES[0], "MX": SERIES[1], "CL": SERIES[2]}
ACQ_ORDER = ["ACQ_BR_A", "ACQ_BR_B", "PIX_BR", "ACQ_MX_A", "ACQ_MX_B", "ACQ_CL_A", "ACQ_CL_B"]
ACQ_COLORS = dict(zip(ACQ_ORDER, SERIES, strict=True))
CAT_COLORS = {"soft": SERIES[3], "hard": SERIES[6], "technical": SERIES[1]}

HELP = {
    "m02": "M02 · grain: payment. Succeeded payments ÷ payments started. Main conversion KPI.",
    "m01": "M01 · grain: attempt. Approved attempts ÷ all attempts (incl. errors). "
    "Retries inflate the denominator, so M01 < M02.",
    "tpv": "M07 · grain: payment. Σ amount × synthetic FX (local creation date) of succeeded "
    "payments, in BRL. Retries never add TPV.",
    "m12": "M12 · attempts ÷ payments.",
    "m10": "M10 · grain: attempt. Error (timeout/acquirer error) attempts ÷ all attempts.",
    "m05": "M05 · grain: payment. Payments succeeded after attempt 1 ÷ payments whose 1st "
    "attempt failed soft or technical (hard declines excluded: not retryable).",
    "m09": "M09 · processing cost (BRL, all attempts) ÷ succeeded payments.",
}

st.set_page_config(page_title="P1 · Payment Intelligence", page_icon="💳", layout="wide")
st.markdown(
    f"""<style>
    html, body, [class*="css"] {{ font-family: {TOKENS["font"]["family"]}; }}
    .synthetic-badge {{ display:inline-block; padding:2px 10px; border-radius:999px;
        background:{C["surface"]}; color:{C["text"]}; border:1px solid {C["muted"]};
        font-size:0.8rem; font-weight:600; }}
    div[data-testid="stMetric"] {{ background:{C["surface"]}; border-radius:8px;
        padding:10px 14px; }}
    </style>""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data access (cached)
@st.cache_resource(show_spinner=False)
def get_con(path: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path, read_only=True)


def _f(key: tuple) -> dd.Filters:
    return dd.Filters(key[0], key[1], key[2], key[3], key[4])


@st.cache_data(show_spinner=False)
def q(fn_name: str, key: tuple, path: str) -> object:
    return getattr(dd, fn_name)(get_con(path), _f(key))


@st.cache_data(show_spinner=False)
def scenario_bases(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = get_con(path)
    return dg.run(con, "s1_reroute_base"), dg.run(con, "s2_retry_base")


@st.cache_data(show_spinner=False)
def opts(path: str) -> dict:
    return dd.options(get_con(path))


def style(fig, height: int = 340):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=48, b=10),
        font=dict(family=TOKENS["font"]["family"], color=C["text"], size=13),
        legend=dict(orientation="h", yanchor="top", y=-0.2, x=0, title=None),
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(showgrid=False, linecolor="#d0d4da")
    fig.update_yaxes(gridcolor="#eceef1", zeroline=False)
    return fig


def table(df: pd.DataFrame, label: str = "Data table") -> None:
    with st.expander(label):
        st.dataframe(df, width="stretch", hide_index=True)


def pct(v: float | None, d: int = 1) -> str:
    return "—" if v is None else f"{v * 100:.{d}f}%"


def brl(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e6:
        return f"R$ {v / 1e6:,.2f} M"
    return f"R$ {v:,.0f}"


# ---------------------------------------------------------------- header + error state
st.title("Payment Intelligence")
st.markdown(
    '<span class="synthetic-badge">SYNTHETIC DATA · derived metrics · not real performance</span>',
    unsafe_allow_html=True,
)

if not DB_PATH.exists():
    st.error(
        f"Warehouse not found at `{DB_PATH}`. Build it with "
        "`python -m fintech_lab.p1_payments.cli dashboard` (generates + builds if missing)."
    )
    st.stop()

DB = str(DB_PATH)
try:
    o = opts(DB)
except duckdb.Error as exc:  # corrupted / incompatible warehouse
    st.error(f"Could not read the warehouse: {exc}")
    st.stop()

# ---------------------------------------------------------------- filters (sidebar)
with st.sidebar:
    st.header("Filters")
    dmin, dmax = o["date_min"], o["date_max"]
    rng = st.date_input(
        "Payment creation date (merchant local)",
        value=(dmin, dmax),
        min_value=dmin,
        max_value=dmax,
        help="Period rule: both payment and attempt metrics use the payment's local creation date.",
    )
    d_from, d_to = (rng[0], rng[1]) if isinstance(rng, tuple) and len(rng) == 2 else (dmin, dmax)
    countries = st.multiselect("Country", o["countries"], placeholder="All countries")
    methods = st.multiselect("Payment method", o["methods"], placeholder="All methods")
    acqs = st.multiselect("Acquirer", o["acquirers"], placeholder="All acquirers")
    st.caption(
        "Empty selection = all. **Acquirer filter:** attempt metrics use the attempt's "
        "acquirer; payment metrics use the *first-attempt* acquirer (a payment may touch two)."
    )
    st.caption("Currency: consolidated in BRL with synthetic daily FX.")

key = (d_from, d_to, tuple(countries), tuple(methods), tuple(acqs))
with st.spinner("Querying warehouse…"):
    k = q("kpis", key, DB)

tabs = st.tabs(
    [
        "Executive Overview",
        "Authorization & Declines",
        "Acquirer Performance",
        "Retry Recovery",
        "Scenario Simulator",
        "About the Data",
    ]
)
EMPTY = "No payments match these filters. Widen the date range or clear a filter."


def empty() -> bool:
    if k["payments"] == 0 and k["attempts"] == 0:
        st.info(EMPTY, icon="ℹ️")
        return True
    return False


# ---------------------------------------------------------------- 1 executive
with tabs[0]:
    if not empty():
        c = st.columns(4)
        c[0].metric("Payment success (M02)", pct(k["m02"]), help=HELP["m02"])
        c[1].metric("Attempt auth rate (M01)", pct(k["m01"]), help=HELP["m01"])
        c[2].metric("Approved TPV (M07, BRL)", brl(k["tpv_brl"]), help=HELP["tpv"])
        c[3].metric(
            "Attempts per payment (M12)",
            "—" if k["m12"] is None else f"{k['m12']:.3f}",
            help=HELP["m12"],
        )
        st.caption(
            f"Denominators: M02 = {k['payments']:,} payments · M01 = {k['attempts']:,} attempts."
        )
        d = q("daily", key, DB)
        d["M02 (7-day)"] = d["succeeded"].rolling(7, 1).sum() / d["payments"].rolling(7, 1).sum()
        d["M01 (7-day)"] = d["approved"].rolling(7, 1).sum() / d["attempts"].rolling(7, 1).sum()
        long = d.melt("day", ["M02 (7-day)", "M01 (7-day)"], "metric", "rate")
        fig = px.line(
            long,
            x="day",
            y="rate",
            color="metric",
            color_discrete_sequence=[SERIES[0], SERIES[1]],
            title="Payment success vs attempt authorization (7-day ratio of sums)",
        )
        fig.update_traces(line_width=2, hovertemplate="%{x|%d %b %Y}: %{y:.1%}")
        fig.update_yaxes(tickformat=".0%", title=None)
        fig.update_xaxes(title=None)
        st.plotly_chart(style(fig), width="stretch")
        table(d[["day", "payments", "succeeded", "m02", "attempts", "approved", "m01", "tpv_brl"]])
        m = q("monthly_tpv", key, DB)
        fig = px.bar(
            m,
            x="month",
            y="tpv_brl",
            color="country",
            color_discrete_map=COUNTRY_COLORS,
            title="Approved TPV by month (BRL, synthetic FX)",
        )
        fig.update_traces(
            marker_line_width=2, marker_line_color="white", hovertemplate="%{x|%b %Y}: R$ %{y:,.0f}"
        )
        fig.update_yaxes(title=None, tickprefix="R$ ")
        fig.update_xaxes(title=None)
        st.plotly_chart(style(fig), width="stretch")
        table(m)

# ---------------------------------------------------------------- 2 declines
with tabs[1]:
    if not empty():
        dec = q("declines", key, DB)
        c = st.columns(3)
        for i, cat in enumerate(["soft", "hard", "technical"]):
            share = dec.loc[dec["category"] == cat, "share_of_attempts"].sum()
            lbl = {
                "soft": "Soft declines (M03)",
                "hard": "Hard declines (M03)",
                "technical": "Technical errors (M10)",
            }[cat]
            c[i].metric(lbl, pct(share), help="Share of ALL filtered attempts.")
        if dec.empty:
            st.info("No failed attempts in this selection.", icon="ℹ️")
        else:
            top = dec.head(12).sort_values("failed_attempts")
            fig = px.bar(
                top,
                y="decline_code",
                x="m04_share_of_failed",
                color="category",
                orientation="h",
                color_discrete_map=CAT_COLORS,
                title="Failure codes · M04 share of failed attempts",
            )
            fig.update_traces(
                hovertemplate="%{y}: %{x:.1%}", marker_line_width=2, marker_line_color="white"
            )
            fig.update_xaxes(tickformat=".0%", title="share of failed attempts (declined + error)")
            fig.update_yaxes(title=None)
            st.plotly_chart(style(fig, 420), width="stretch")
            st.caption(
                "Soft/hard come from the issuer; technical (timeout, acquirer error) from the "
                "processing chain. Only soft and technical are retried."
            )
            table(dec)

# ---------------------------------------------------------------- 3 acquirers
with tabs[2]:
    if not empty():
        a = q("acquirers", key, DB)
        if a.empty:
            st.info(EMPTY, icon="ℹ️")
        else:
            fig = px.bar(
                a,
                x="acquirer_id",
                y="m01",
                color="acquirer_id",
                color_discrete_map=ACQ_COLORS,
                text=a["m01"].map(lambda v: f"{v:.1%}"),
                title="Attempt authorization rate (M01) by acquirer — raw, not mix-adjusted",
            )
            fig.update_traces(
                textposition="outside", hovertemplate="%{x}: %{y:.1%}", showlegend=False
            )
            fig.update_yaxes(tickformat=".0%", title=None, range=[0, 1.05])
            fig.update_xaxes(title=None)
            st.plotly_chart(style(fig), width="stretch")
            st.caption(
                "Raw M01 mixes method, ticket and merchant differences (Simpson risk). The "
                "mix-adjusted comparison is in the diagnostic memo (table 1.3). PIX_BR is a "
                "different rail, not a card-acquirer peer."
            )
            eh = q("error_by_hour", key, DB)
            fig = px.line(
                eh,
                x="hour",
                y="m10",
                color="acquirer_id",
                color_discrete_map=ACQ_COLORS,
                facet_col="country",
                category_orders={"country": ["BR", "MX", "CL"]},
                markers=True,
                title="Technical error rate (M10) by merchant local hour · shaded = peak 19–22h",
            )
            fig.for_each_annotation(lambda an: an.update(text=an.text.split("=")[-1]))
            fig.update_traces(line_width=2, marker_size=6, hovertemplate="%{x}h: %{y:.2%}")
            fig.add_vrect(
                x0=18.5, x1=22.5, fillcolor="#e3e7ee", opacity=1, line_width=0, layer="below",
                row="all", col="all",
            )  # fmt: skip
            fig.update_yaxes(tickformat=".1%", title=None)
            fig.update_xaxes(title=None, dtick=4)
            st.plotly_chart(style(fig, 380), width="stretch")
            show = a.assign(
                m01=a["m01"].map(pct),
                m10=a["m10"].map(lambda v: pct(v, 2)),
                m03_soft=a["m03_soft"].map(pct),
                m03_hard=a["m03_hard"].map(pct),
            )
            st.dataframe(show, width="stretch", hide_index=True)
            table(eh, "Data table · error by hour")

# ---------------------------------------------------------------- 4 retries
with tabs[3]:
    if not empty():
        c = st.columns(3)
        c[0].metric("Retry recovery (M05)", pct(k["m05"]), help=HELP["m05"])
        c[1].metric(
            "Payments with retryable 1st failure",
            f"{k['first_failed_retryable']:,}",
            help="Denominator of M05.",
        )
        c[2].metric(
            "Cost per successful payment (M09)",
            "—" if k["m09"] is None else f"R$ {k['m09']:.3f}",
            help=HELP["m09"],
        )
        rr = q("retry_recovery", key, DB)
        if rr.empty:
            st.info("No payments with a retryable first failure in this selection.", icon="ℹ️")
        else:
            fig = px.bar(
                rr,
                x="country",
                y="m05",
                color="first_category",
                barmode="group",
                color_discrete_map=CAT_COLORS,
                title="M05 by first failure category",
            )
            fig.update_traces(
                hovertemplate="%{x}: %{y:.1%}", marker_line_width=2, marker_line_color="white"
            )
            fig.update_yaxes(tickformat=".0%", title=None)
            fig.update_xaxes(title=None)
            st.plotly_chart(style(fig), width="stretch")
            table(rr)
        lad = q("attempt_ladder", key, DB)
        if not lad.empty:
            fig = px.bar(
                lad,
                x="attempt_no",
                y="m01",
                color="route",
                barmode="group",
                color_discrete_sequence=[SERIES[0], SERIES[2], SERIES[1]],
                title="Marginal M01 by attempt number and routing",
            )
            fig.update_traces(
                hovertemplate="attempt %{x}: %{y:.1%}",
                marker_line_width=2,
                marker_line_color="white",
            )
            fig.update_yaxes(tickformat=".0%", title=None)
            fig.update_xaxes(title=None, dtick=1, tickprefix="attempt ")
            st.plotly_chart(style(fig), width="stretch")
            st.caption(
                "Observational. Later attempts are a selected, riskier population "
                "(survivorship), so lower M01 at attempt 3 is not the effect of retrying."
            )
            table(lad)

# ---------------------------------------------------------------- 5 scenarios
with tabs[4]:
    st.warning(
        "Hypothetical simulation under explicit assumptions on synthetic data. Not a forecast, "
        "not realized uplift, not causal proof. Fees and contribution use a synthetic MDR "
        "[TO VERIFY]. Runs on the full dataset (sidebar filters do not apply here).",
        icon="⚠️",
    )
    s1_base, s2_base = scenario_bases(DB)
    cp = s2_base.set_index("country")["payments"]
    st.subheader("S1 · Reroute soft-decline retries to the alternative acquirer")
    c = st.columns(3)
    theta = c[0].slider(
        "θ — transfer of the observed switched-vs-same gap",
        0.0,
        1.0,
        0.5,
        0.05,
        help="0 = rerouting changes nothing; 1 = rerouted payments behave like "
        "the observed switched arm (success and cost).",
    )
    take1 = c[1].slider("Take-rate multiplier (S1)", 0.5, 1.5, 1.0, 0.1)
    cost1 = c[2].slider("Cost-gap multiplier (S1)", 0.5, 1.5, 1.0, 0.1)
    r1 = sc.simulate_s1(s1_base, cp, sc.S1Assumptions(theta, take1, cost1))
    fig = px.bar(
        r1,
        x="first_acquirer_id",
        y="d_succeeded",
        color="country",
        color_discrete_map=COUNTRY_COLORS,
        error_y=r1["d_succeeded_hi95"] - r1["d_succeeded"],
        error_y_minus=r1["d_succeeded"] - r1["d_succeeded_lo95"],
        title="Δ succeeded payments if retries leave this acquirer (95% CI)",
    )
    fig.update_traces(hovertemplate="from %{x}: %{y:+,.0f}")
    fig.update_yaxes(title=None, zeroline=True, zerolinecolor=C["muted"])
    fig.update_xaxes(title="reroute FROM (to the same-country alternative)")
    st.plotly_chart(style(fig), width="stretch")
    st.dataframe(
        r1.drop(columns=["theta", "take_mult"]).round(2),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Strata = country × first acquirer × method × amount band; strata with < 30 payments "
        "per arm are excluded (see coverage). Picking only positive directions invites the "
        "winner's curse."
    )
    st.subheader("S2 · Max attempts per payment (observed policy = 3)")
    c = st.columns(3)
    cap = c[0].radio("Retry cap", [2, 3, 4], index=2, horizontal=True)
    delta = c[1].slider(
        "δ — attempt-4 approval vs attempt-3 (cap 4 only)",
        0.25,
        1.25,
        0.75,
        0.05,
        disabled=cap != 4,
    )
    take2 = c[2].slider("Take-rate multiplier (S2)", 0.5, 1.5, 1.0, 0.1)
    r2 = sc.simulate_s2(s2_base, sc.S2Assumptions(cap=cap, delta=delta, take_mult=take2))
    tot = r2[r2["country"] == "TOTAL"].iloc[0]
    c = st.columns(3)
    c[0].metric(
        "M02 under scenario",
        pct(tot["m02_scenario"], 2),
        delta=f"{tot['d_m02_pp']:+.2f} pp vs cap 3",
    )
    c[1].metric("Δ approved TPV (BRL)", brl(tot["d_tpv_brl"]))
    c[2].metric("Δ est. contribution (BRL) [TO VERIFY]", brl(tot["d_net_contribution_brl"]))
    if cap == 4:
        st.caption("cap 4 is an EXTRAPOLATION: a 4th attempt was never observed.")
    st.dataframe(r2.round(4), width="stretch", hide_index=True)

# ---------------------------------------------------------------- 6 about
with tabs[5]:
    mf = DATA_DIR / "manifest.json"
    man = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
    st.subheader("Provenance")
    st.markdown(
        f"""
- **data_origin:** `synthetic` (generator) → every metric here is `derived`.
- **Seed:** `{man.get("seed", "[TO VERIFY]")}` · **content SHA-256:**
  `{man.get("dataset_content_sha256", "[TO VERIFY]")}`
- **Rows:** {", ".join(f"{t} = {v['rows']:,}" for t, v in man.get("tables", {}).items()) or "—"}
- **Warehouse:** `{DB_PATH.name}` (DuckDB) · rendered {date.today().isoformat()}
- Patterns (acquirer gaps, peak-hour errors) were **planted by the generator**
  (`configs/generator.yaml`). The dashboard demonstrates method, not market facts.
"""
    )
    st.subheader("Metric definitions")
    st.dataframe(
        pd.DataFrame(
            [
                ("M01", "attempt", "approved attempts", "all attempts (incl. errors)"),
                ("M02", "payment", "succeeded payments", "payments started"),
                ("M03", "attempt", "soft / hard declined attempts", "all attempts"),
                ("M04", "attempt", "failed attempts with code X", "declined + error attempts"),
                (
                    "M05",
                    "payment",
                    "succeeded after attempt 1",
                    "1st attempt failed soft/technical",
                ),
                ("M07", "payment", "Σ amount × FX of succeeded (BRL)", "—"),
                ("M09", "payment", "processing cost (BRL)", "succeeded payments"),
                ("M10", "attempt", "error attempts", "all attempts"),
                ("M12", "payment", "attempts", "payments"),
            ],
            columns=["ID", "Grain", "Numerator", "Denominator"],
        ),
        width="stretch",
        hide_index=True,
    )
    st.subheader("Methodology & limits")
    st.markdown(
        """
- Ratios are always Σ numerator ÷ Σ denominator over the filtered rows (never an average of
  rates). Rolling lines use 7-day ratios of sums.
- Period = payment creation date in the merchant's local time zone; storage is UTC.
- Money is never summed across currencies without FX; BRL consolidation uses the synthetic
  rate of the payment's local creation date.
- TPV is counted per succeeded payment, so retries never inflate it (reconciliation check).
- Take rate, fees and contribution: synthetic MDR, **[TO VERIFY]**, not real revenue.
- Full diagnostic memo: `projects/01-payment-intelligence/reports/diagnostic_memo.md`.
"""
    )
