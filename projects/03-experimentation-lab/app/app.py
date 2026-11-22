"""P3 Experimentation Lab dashboard (Streamlit). All data is SYNTHETIC.

Run: python -m fintech_lab.p3_experiments.cli dashboard

The scenario selector only chooses WHICH dataset is loaded. Analysis rules, windows, margins and the
decision come from the locked protocol and cannot be changed here. This app never reads the
simulator's true-effect config.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fintech_lab.p3_experiments.lock import ProtocolLockError, verify_lock
from fintech_lab.p3_experiments.power import P3_ROOT, REPO_ROOT, load_protocol
from fintech_lab.p3_experiments.report import run

DATA_ROOT = Path(os.environ.get("P3_DATA_ROOT", REPO_ROOT / "data" / "p3"))
TOKENS = json.loads((REPO_ROOT / "shared" / "design_tokens" / "tokens.json").read_text())
C = TOKENS["color"]
ARM_COLOR = {"A": "#2a78d6", "B": "#eb6834"}  # fixed per arm, never by rank
SCENARIOS = ["null", "positive", "negative", "srm", "missing"]
DECISION_COLOR = {"LAUNCH": C["positive"], "DO NOT LAUNCH": C["negative"],
                  "INCONCLUSIVE": C["warning"], "INVALID": C["muted"]}  # fmt: skip

st.set_page_config(page_title="P3 · Experimentation Lab", page_icon="🧪", layout="wide")
st.markdown(
    f"""<style>
    html, body, [class*="css"] {{ font-family: {TOKENS["font"]["family"]}; }}
    .synthetic-badge {{ display:inline-block; padding:2px 10px; border-radius:999px;
        background:{C["surface"]}; color:{C["text"]}; border:1px solid {C["muted"]};
        font-size:0.8rem; font-weight:600; }}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
        color:{C["muted"]} !important; opacity:1 !important; }}
    div[data-testid="stMetric"] {{ background:{C["surface"]}; border-radius:8px; padding:10px 14px; }}
    </style>""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Running the locked analysis…")
def analysis(root: str, scenario: str) -> dict:
    return run(Path(root) / scenario)


@st.cache_data(show_spinner=False)
def protocol() -> dict:
    return load_protocol()


def pp(v: float) -> str:
    return "n/a" if v != v else f"{v * 100:+.2f} p.p."


def style(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=48, b=10),
                      font=dict(family=TOKENS["font"]["family"], color=C["text"], size=13))  # fmt: skip
    return fig


st.markdown("# P3 · A/B Testing Lab")
st.markdown('<span class="synthetic-badge">SYNTHETIC DATA</span>', unsafe_allow_html=True)
st.caption("Experiment P3-EXP-001 · risk-based 3DS (B) vs mandatory 3DS (A). Synthetic scenarios, "
           "hypothetical economics; nothing here is a real result.")

with st.sidebar:
    scenario = st.radio("Scenario (selects the dataset only)", SCENARIOS, index=1)
    st.caption("Rules are fixed by the locked protocol; changing the scenario cannot change them.")

try:
    verify_lock()
except ProtocolLockError as e:
    st.error(f"Protocol lock check failed: {e}")
    st.stop()
if not (DATA_ROOT / scenario / "manifest.json").exists():
    st.error(f"Dataset not found for scenario '{scenario}' in {DATA_ROOT}. "
             "Run `python -m fintech_lab.p3_experiments.cli generate`.")  # fmt: skip
    st.stop()

try:
    res = analysis(str(DATA_ROOT), scenario)
except ValueError as e:  # e.g. DataNotMatureError: never show effects on censored data
    st.error(f"Analysis refused: {e}")
    st.stop()
proto = protocol()
m, cnt, g, p, dec = res["meta"], res["counts"], res["gates"], res["primary"], res["decision"]

INVALID_NOTE = ("Result is INVALID (a validity gate failed): the numbers on this tab are shown for "
                "transparency only and must not be interpreted as an effect.")  # fmt: skip
tabs = st.tabs(["Overview & protocol", "Funnel", "Results", "Guardrails", "Data quality",
                "Sensitivity & Monte Carlo", "Decision"])  # fmt: skip

with tabs[0]:
    col = DECISION_COLOR[dec["decision"]]
    st.markdown(f"### Decision: <span style='color:{col}'>{dec['decision']}</span>",
                unsafe_allow_html=True)  # fmt: skip
    k = st.columns(4)
    k[0].metric("Exposed users A", f"{cnt['exposed_a']:,}")
    k[1].metric("Exposed users B", f"{cnt['exposed_b']:,}")
    k[2].metric("Seed", m["seed"])
    k[3].metric("Protocol", f"v{m['protocol_version']}", help="SHA-256 locked; amendments: "
                f"{m['amendments']}")  # fmt: skip
    st.markdown(
        f"- **Question:** {' '.join(proto['experiment']['question'].split())}\n"
        f"- **Unit / allocation:** `{proto['assignment']['unit']}`, 50/50, "
        f"`{proto['assignment']['method']}`\n"
        f"- **Windows:** conversion {m['window_days']['conversion']} d after first exposure; "
        f"chargeback maturation {m['window_days']['chargeback']} d\n"
        f"- **Primary:** P01 `{proto['primary']['name']}` (user grain, ITT), α="
        f"{proto['primary']['alpha']}, power {proto['primary']['power']}, MDE "
        f"{proto['primary']['mde_abs'] * 100:.1f} p.p. (assumed baseline "
        f"{proto['primary']['baseline_assumption']:.0%})\n"
        f"- **Lock:** {m['lock_algorithm']} locked at {m['locked_at']}, verified at load."
    )
    with st.expander("Preregistered protocol (docs/protocol.md)"):
        st.markdown((P3_ROOT / "docs" / "protocol.md").read_text(encoding="utf-8"))

with tabs[1]:
    rows = []
    for arm, f in res["funnel"].items():
        for stage in ("exposed", "attempted", "approved"):
            rows.append({"arm": arm, "stage": stage, "users": f[stage],
                         "share_of_exposed": f[stage] / f["exposed"]})  # fmt: skip
    df = pd.DataFrame(rows)
    fig = go.Figure()
    for arm in ("A", "B"):
        d = df[df.arm == arm]
        fig.add_bar(x=d["stage"], y=d["share_of_exposed"], name=f"Arm {arm}",
                    marker_color=ARM_COLOR[arm], text=[f"{v:.1%}" for v in d["share_of_exposed"]],
                    customdata=d["users"], hovertemplate="%{x}: %{customdata:,} users<extra></extra>")  # fmt: skip
    fig.update_layout(barmode="group", yaxis_tickformat=".0%",
                      title="User funnel (share of exposed users, user grain)")  # fmt: skip
    st.plotly_chart(style(fig), width="stretch")
    with st.expander("Data table"):
        st.dataframe(df, width="stretch", hide_index=True)
    st.caption(f"Candidates {cnt['candidates']:,} → eligible {cnt['eligible']:,} → exposed "
               f"{cnt['exposed_a'] + cnt['exposed_b']:,}. Eligibility excludes internal and "
               "pre-fraud-blocked users before exposure.")  # fmt: skip

with tabs[2]:
    if not g["all_pass"]:
        st.warning(INVALID_NOTE)
    k = st.columns(4)
    k[0].metric("P01 arm A", f"{p['p_a']:.2%}", help="Exposed users with ≥1 approval within 7 d ÷ exposed users")  # fmt: skip
    k[1].metric("P01 arm B", f"{p['p_b']:.2%}")
    k[2].metric("Absolute difference", pp(p["diff"]))
    k[3].metric("Relative uplift", f"{p['rel'] * 100:+.2f}%")
    fig = go.Figure(go.Scatter(x=[p["diff"] * 100], y=["B − A"], mode="markers",
                               marker=dict(size=12, color=C["primary"]),
                               error_x=dict(type="data", symmetric=False,
                                            array=[(p["ci_high"] - p["diff"]) * 100],
                                            arrayminus=[(p["diff"] - p["ci_low"]) * 100])))  # fmt: skip
    fig.add_vline(x=0, line_dash="dash", line_color=C["muted"])
    fig.update_layout(title="P01 difference with 95% CI (p.p.)", xaxis_title="percentage points")
    st.plotly_chart(style(fig, 240), width="stretch")
    st.markdown(f"95% CI [{pp(p['ci_low'])}, {pp(p['ci_high'])}] · p = {p['p_value']:.4g} "
                f"(two-proportion z, pooled SE; Wald CI) · design MDE at observed n "
                f"{pp(p['mde_abs_at_observed_n'])}.")  # fmt: skip
    st.info("A confidence interval that includes 0 is **not** evidence of no effect.")

with tabs[3]:
    if not g["all_pass"]:
        st.warning(INVALID_NOTE)
    gr = pd.DataFrame(res["guardrails"])
    gr["d / margin"] = gr["diff"] / gr["margin"]
    gr["lo / margin"] = gr["ci_low"] / gr["margin"]
    gr["hi / margin"] = gr["ci_high"] / gr["margin"]
    fig = go.Figure(go.Scatter(
        x=gr["d / margin"], y=gr["id"] + " " + gr["name"], mode="markers",
        marker=dict(size=11, color=[{"pass": C["positive"], "fail": C["negative"],
                                     "undetermined": C["warning"]}[s] for s in gr["status"]]),
        error_x=dict(type="data", symmetric=False, array=gr["hi / margin"] - gr["d / margin"],
                     arrayminus=gr["d / margin"] - gr["lo / margin"])))  # fmt: skip
    fig.add_vline(x=1, line_dash="dash", line_color=C["negative"], annotation_text="margin")
    fig.add_vline(x=0, line_color=C["muted"])
    fig.update_layout(title="Degradation d = B − A as a multiple of the margin (95% CI)",
                      xaxis_title="d ÷ margin (≤ 1 on the upper bound ⇒ pass)")  # fmt: skip
    st.plotly_chart(style(fig, 340), width="stretch")
    show = gr[["id", "name", "est_a", "est_b", "diff", "ci_low", "ci_high", "margin", "status"]]
    st.dataframe(show, width="stretch", hide_index=True)
    st.caption("pass: upper bound ≤ margin · fail: lower bound > margin · undetermined: otherwise. "
               "All guardrails must pass to launch (intersection-union). G3: p95 latency in ms "
               "(user-cluster bootstrap); G4 margin is relative.")  # fmt: skip

with tabs[4]:
    s, a, e, mi = g["srm"], g["assignment_integrity"], g["events_before_exposure"], g["missing_events"]
    k = st.columns(4)
    k[0].metric("SRM p-value", f"{s['p_value']:.3g}", help=f"χ² vs 50/50; INVALID if < {s['threshold']}")  # fmt: skip
    k[1].metric("Arm mismatch vs hash", a["arm_mismatch_vs_hash"])
    k[2].metric("Events before exposure", e["count"])
    k[3].metric("Incomplete trails B − A", f"{mi['diff']:+.2%}")
    st.table(pd.DataFrame({
        "gate": ["SRM", "Assignment integrity", "Events before exposure", "Missing events"],
        "status": ["pass" if x["pass"] else "FAIL" for x in (s, a, e, mi)],
        "detail": [f"A={s['n_a']:,} B={s['n_b']:,}", f"{a['duplicate_users']} duplicates",
                   f"{e['count']} events",
                   f"A {mi['share_a']:.2%} · B {mi['share_b']:.2%} (max 2% / diff 0.5 p.p.)"]}))  # fmt: skip
    if not g["all_pass"]:
        st.error("A validity gate failed: effect estimates are shown for transparency but the "
                 "result is INVALID and must not be interpreted.")  # fmt: skip

with tabs[5]:
    if not g["all_pass"]:
        st.warning(INVALID_NOTE)
    sv = res["sensitivity"]
    st.markdown("**Non-decisional checks of P01**")
    st.table(pd.DataFrame([
        {"check": "Primary", "diff": pp(p["diff"]), "95% CI": f"[{pp(p['ci_low'])}, {pp(p['ci_high'])}]"},
        {"check": f"Excluding {sv['incomplete_users']} incomplete trails",
         "diff": pp(sv["exclude_incomplete_trails"]["diff"]),
         "95% CI": f"[{pp(sv['exclude_incomplete_trails']['ci_low'])}, "
                   f"{pp(sv['exclude_incomplete_trails']['ci_high'])}]"},
        {"check": "HC1 robust SE (OLS)", "diff": pp(sv["robust_hc1"]["diff"]),
         "95% CI": f"[{pp(sv['robust_hc1']['ci_low'])}, {pp(sv['robust_hc1']['ci_high'])}]"},
    ]))  # fmt: skip
    mc = P3_ROOT / "reports" / "monte_carlo.csv"
    st.markdown("**Monte Carlo verification of the engine** (controlled synthetic scenarios; "
                "G3/G4 not covered: [TO VERIFY])")  # fmt: skip
    if mc.exists():
        st.dataframe(pd.read_csv(mc, comment="#"), width="stretch", hide_index=True)
    else:
        st.info("Run `python -m fintech_lab.p3_experiments.cli montecarlo` to produce this table.")

with tabs[6]:
    if not g["all_pass"]:
        st.warning(INVALID_NOTE)
    st.markdown(f"### {dec['decision']}  ·  {dec['rule']}")
    for r in dec["reasons"]:
        st.markdown(f"- {r}")
    ec = res["economics"]
    st.markdown("#### Hypothetical economics (does not change the decision)")
    st.caption(ec["label"])
    k = st.columns(3)
    k[0].metric("Δ value per user", f"R$ {ec['diff_per_user']:+.3f}")
    k[1].metric("Annualised Δ", f"R$ {ec['annual_delta']:,.0f}",
                help=f"95% CI [{ec['annual_ci_low']:,.0f}, {ec['annual_ci_high']:,.0f}]")  # fmt: skip
    k[2].metric("Year-1 net of assumed cost", f"R$ {ec['year1_net']:,.0f}")
    st.markdown("#### Exploratory segments (no multiplicity control; never used to decide)")
    seg = res["segments"]
    if len(seg):
        st.dataframe(seg, width="stretch", hide_index=True)
    else:
        st.caption("No segments.")
    st.caption("Limitations: ITT effect on the simulated population only; chargeback maturation of "
               "30 d is short; interference assumed negligible; no external validity.")  # fmt: skip
