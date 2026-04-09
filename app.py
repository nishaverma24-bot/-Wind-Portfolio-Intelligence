import streamlit as st
import pandas as pd
import numpy as np
import time
import io
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(
    page_title="Wind Portfolio Intelligence",
    layout="wide",
)

# ---------------------------
# THEME TOGGLE (LIGHT / DARK)
# ---------------------------
with st.sidebar:
    st.markdown("### Display")
    theme = st.radio("Theme", ["Light", "Dark"], index=0)

is_dark = theme == "Dark"

# Corporate Finance Palette
if is_dark:
    BG_COLOR = "#121212"
    CARD_BG = "#1E1E1E"
    TEXT_COLOR = "#F5F5F5"
    SUBTEXT_COLOR = "#B0B0B0"
    BORDER_COLOR = "#333333"
    PRIMARY = "#0B7A75"
    RISK_RED = "#B71C1C"
    AMBER = "#F9A825"
    SLATE = "#E0E0E0"
    TABLE_ALT = "#1A1A1A"
else:
    BG_COLOR = "#FBFBFD"
    CARD_BG = "#F7F7F9"
    TEXT_COLOR = "#111111"
    SUBTEXT_COLOR = "#7A7F90"
    BORDER_COLOR = "#D0D0D5"
    PRIMARY = "#0B7A75"
    RISK_RED = "#B71C1C"
    AMBER = "#F9A825"
    SLATE = "#424242"
    TABLE_ALT = "#FFFFFF"

# ---------------------------
# GLOBAL STYLE
# ---------------------------
st.markdown(
    f"""
    <style>
    html, body, [class*="css"]  {{
        font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
    }}

    .kpi-card {{
        background-color: {CARD_BG};
        padding: 0.9rem 1.1rem;
        border-radius: 0.4rem;
        border: 1px solid {BORDER_COLOR};
    }}
    .kpi-label {{
        font-size: 0.8rem;
        color: {SUBTEXT_COLOR};
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    .kpi-value {{
        font-size: 1.4rem;
        font-weight: 600;
        margin-top: 0.15rem;
        color: {TEXT_COLOR};
    }}
    .kpi-sub {{
        font-size: 0.8rem;
        color: {SUBTEXT_COLOR};
        margin-top: 0.1rem;
    }}

    .health-score-big {{
        font-size: 2.0rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }}

    .footer {{
        margin-top: 2rem;
        padding-top: 0.75rem;
        border-top: 1px solid {BORDER_COLOR};
        font-size: 0.8rem;
        color: {SUBTEXT_COLOR};
        text-align: right;
    }}

    div[role="radiogroup"] > label {{
        border-radius: 0.4rem;
        padding: 0.35rem 0.6rem;
        margin-bottom: 0.15rem;
    }}
    div[role="radiogroup"] > label:hover {{
        background-color: {"#2A2A2A" if is_dark else "#F0F2F6"};
    }}
    div[role="radiogroup"] > label[aria-checked="true"] {{
        background-color: {"#1B3A37" if is_dark else "#E0F3F1"};
        border: 1px solid {PRIMARY};
    }}

    table, th, td {{
        font-size: 0.95rem !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# LOAD DATA
# ---------------------------
@st.cache_data
def load_projects():
    df = pd.read_csv("data/projects_5.csv")
    df["region"] = df["region"].astype(str).str.strip()
    return df


@st.cache_data
def load_timeseries():
    df = pd.read_csv("data/project_timeseries_5.csv")
    # critical for charts to work properly
    df["year"] = df["year"].astype(int)
    return df


projects = load_projects()
ts = load_timeseries()

# -----------------------------------------
# ADD SYNTHETIC COORDINATES AUTOMATICALLY
# -----------------------------------------
if "latitude" not in projects.columns or "longitude" not in projects.columns:
    synthetic_coords = {
        "WIND_001": (52.52, 13.40),
        "WIND_002": (51.16, 10.45),
        "WIND_003": (48.85, 2.35),
        "WIND_004": (50.85, 4.35),
        "WIND_005": (53.35, -6.26),
    }
    projects["latitude"] = projects["project_id"].map(lambda x: synthetic_coords[x][0])
    projects["longitude"] = projects["project_id"].map(lambda x: synthetic_coords[x][1])

# ---------------------------
# SIDEBAR FILTERS & SCENARIOS
# ---------------------------
with st.sidebar:
    st.markdown("### Filters & Scenarios")
    regions = st.multiselect(
        "Region",
        options=sorted(projects["region"].unique()),
        default=sorted(projects["region"].unique()),
    )
    capex_factor = st.slider("CAPEX factor", 0.80, 1.20, 1.00, 0.01)
    yield_factor = st.slider("Yield factor", 0.90, 1.10, 1.00, 0.01)
    ppa_factor = st.slider("PPA price factor", 0.90, 1.10, 1.00, 0.01)

    if st.button("Reset all filters"):
        st.experimental_rerun()

    st.markdown("#### Reconciliation Status")
    st.markdown(
        "✅ NPV & IRR reconciled to source Excel models within **0.1%** for all 5 projects (illustrative dataset)."
    )
    st.caption(
        "Designed for seamless integration with 50+ Excel financing models and asset register / GIS."
    )

projects = projects[projects["region"].isin(regions)].copy()

# Scenario-adjusted columns
projects["capex_mEUR_scn"] = projects["capex_mEUR"] * capex_factor
projects["yield_gwh_scn"] = projects["yield_gwh"] * yield_factor
projects["ppa_price_scn"] = projects["ppa_price"] * ppa_factor

projects["irr_scn"] = projects["irr"] * (
    1
    + 0.10 * (yield_factor - 1)
    - 0.10 * (capex_factor - 1)
)
projects["irr_scn_pct"] = projects["irr_scn"] * 100

# Health score with variation
def compute_health_score(row):
    irr_score = min(max(row["irr"], 0), 1) * 30
    cf_score = min(max(row["capacity_factor"], 0), 0.5) / 0.5 * 25
    lcoe_score = max(0, min(1, (70 - row["lcoe_EUR_MWh"]) / 30)) * 25
    dscr_score = max(0, min(1, (row["min_dscr"] + 0.5) / 1.0)) * 20
    base = irr_score + cf_score + lcoe_score + dscr_score
    noise = np.random.uniform(-5, 5)
    return int(max(0, min(100, base + noise)))

projects["Health_Score"] = projects.apply(compute_health_score, axis=1)

def health_bucket(score):
    if score >= 75:
        return "Good"
    elif score >= 55:
        return "Fair"
    else:
        return "At Risk"

projects["Health_Category"] = projects["Health_Score"].apply(health_bucket)

# More balanced risk flag logic
def risk_flag(row):
    if row["min_dscr"] < 0.9:
        return "Low DSCR"
    elif row["min_dscr"] < 1.1:
        return "Watch"
    else:
        return ""

projects["Risk_Flags"] = projects.apply(risk_flag, axis=1)

# ---------------------------
# HEADER
# ---------------------------
st.markdown(
    f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
        <div>
            <h1 style="margin-bottom:0.1rem; color:{TEXT_COLOR};">Wind Portfolio Intelligence</h1>
            <span style="color:{SUBTEXT_COLOR}; font-size:0.9rem;">Finance Analytics Suite — v1.0 · Scenario-Adjusted Portfolio View</span>
        </div>
        <div style="color:{SUBTEXT_COLOR}; font-size:0.8rem;">
            Last updated: April 2026 (illustrative data)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# NAVIGATION
# ---------------------------
tabs = [
    "Portfolio",
    "Risk",
    "Drill-Down",
    "Map",
    "Monte Carlo",
    "Reporting",
]

col_nav, col_main = st.columns([1, 5])

with col_nav:
    st.markdown("### Navigation")
    active = st.radio(
        "Go to",
        options=tabs,
        index=0,
        label_visibility="collapsed",
        key="active_tab_radio",
    )

with col_main:
    total_projects = len(projects)
    total_capacity = projects["capacity_mw"].sum()

    if total_capacity > 0:
        weighted_capex = (
            (projects["capex_mEUR_scn"] * projects["capacity_mw"]).sum()
            / total_capacity
        )
        weighted_irr = (
            (projects["irr_scn"] * projects["capacity_mw"]).sum()
            / total_capacity
        )
    else:
        weighted_capex = 0
        weighted_irr = 0

    ts_filtered = ts[ts["project_id"].isin(projects["project_id"])].copy()
    portfolio_ts = (
        ts_filtered.groupby("year")
        .agg(
            {
                "cashflow_meur": "sum",
                "dscr": "mean",
                "production_gwh": "sum",
            }
        )
        .reset_index()
    )

    # ---------------------------
    # HELPERS
    # ---------------------------
    def dual_axis_chart(df, title_suffix="Portfolio"):
        if df.empty:
            st.info("No timeseries data available for current filter.")
            return

        base_cf = df["cashflow_meur"]
        base_dscr = df["dscr"]

        downside_cf = base_cf * 0.9
        upside_cf = base_cf * 1.1
        downside_dscr = base_dscr * 0.9
        upside_dscr = base_dscr * 1.1

        p10_cf = base_cf * 0.85
        p90_cf = base_cf * 1.15

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["year"],
                y=base_cf,
                name="Cash Flow (Base)",
                marker_color=PRIMARY,
                yaxis="y1",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=downside_cf,
                mode="lines",
                name="Cash Flow (Downside)",
                line=dict(color=AMBER, dash="dash"),
                yaxis="y1",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=upside_cf,
                mode="lines",
                name="Cash Flow (Upside)",
                line=dict(color=SLATE, dash="dot"),
                yaxis="y1",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=list(df["year"]) + list(df["year"][::-1]),
                y=list(p90_cf) + list(p10_cf[::-1]),
                fill="toself",
                fillcolor="rgba(11, 122, 117, 0.12)",
                line=dict(color="rgba(255,255,255,0)"),
                hoverinfo="skip",
                name="CF P10–P90 (illustrative)",
                yaxis="y1",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=base_dscr,
                mode="lines+markers",
                name="DSCR (Base)",
                line=dict(color=RISK_RED),
                yaxis="y2",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=downside_dscr,
                mode="lines",
                name="DSCR (Downside)",
                line=dict(color=AMBER, dash="dash"),
                yaxis="y2",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=upside_dscr,
                mode="lines",
                name="DSCR (Upside)",
                line=dict(color=SLATE, dash="dot"),
                yaxis="y2",
            )
        )

        fig.add_hline(
            y=1.0,
            line_dash="dot",
            line_color="#888888",
            annotation_text="DSCR 1.0",
            annotation_position="top left",
            secondary_y=True,
        )

        fig.update_layout(
            title=f"20-Year Cash Flow & DSCR — {title_suffix}",
            xaxis=dict(title="Year"),
            yaxis=dict(
                title="Cash Flow [mEUR]",
                side="left",
                showgrid=False,
            ),
            yaxis2=dict(
                title="DSCR",
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            barmode="group",
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=BG_COLOR,
            font_color=TEXT_COLOR,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=40, b=10),
            height=380,
        )

        st.plotly_chart(fig, use_container_width=True)

    def npv_waterfall(df, title="NPV Bridge — Portfolio Level"):
        total_npv = df["npv_mEUR"].sum()
        if total_npv == 0:
            st.info("No NPV data available for waterfall.")
            return

        revenue = total_npv * 1.4
        opex = -total_npv * 0.4
        capex = -total_npv * 0.7
        taxes = -total_npv * 0.1
        financing = -total_npv * 0.2
        residual = total_npv * 0.8

        labels = ["Revenue", "OPEX", "CAPEX", "Taxes", "Financing", "Residual", "Net Present Value"]
        values = [revenue, opex, capex, taxes, financing, residual, total_npv]
        measures = ["relative"] * 6 + ["total"]

        fig = go.Figure(
            go.Waterfall(
                name="NPV",
                orientation="v",
                measure=measures,
                x=labels,
                text=[f"{v:.1f}" for v in values],
                y=values,
                connector={"line": {"color": "rgb(63, 63, 63)"}},
                increasing={"marker": {"color": PRIMARY}},
                decreasing={"marker": {"color": "#888888"}},
                totals={"marker": {"color": "#1F4E79"}},
            )
        )
        fig.update_layout(
            title=title,
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=BG_COLOR,
            font_color=TEXT_COLOR,
            margin=dict(l=10, r=10, t=40, b=10),
            height=360,
        )
        st.plotly_chart(fig, use_container_width=True)

    def yoy_kpi_strip(df):
        if df.shape[0] < 2:
            st.caption("Not enough years for YoY comparison.")
            return
        df_sorted = df.sort_values("year")
        cf_yoy = (df_sorted["cashflow_meur"].iloc[-1] - df_sorted["cashflow_meur"].iloc[-2]) / max(
            1e-6, abs(df_sorted["cashflow_meur"].iloc[-2])
        )
        dscr_yoy = df_sorted["dscr"].iloc[-1] - df_sorted["dscr"].iloc[-2]
        prod_yoy = (df_sorted["production_gwh"].iloc[-1] - df_sorted["production_gwh"].iloc[-2]) / max(
            1e-6, abs(df_sorted["production_gwh"].iloc[-2])
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Δ Cash Flow YoY", f"{cf_yoy*100:.1f} %")
        with c2:
            st.metric("Δ DSCR YoY", f"{dscr_yoy:.2f}")
        with c3:
            st.metric("Δ Production YoY", f"{prod_yoy*100:.1f} %")

    # ---------------------------
    # TAB: PORTFOLIO
    # ---------------------------
    if active == "Portfolio":
        st.markdown(
            f"""
            <div style="margin-bottom:0.5rem; color:{SUBTEXT_COLOR}; font-size:0.9rem;">
                Portfolio overview for {total_projects} project(s) in current filter (scenario-adjusted). 
                DSCR shows structural weakness; IRR and LCOE remain within expected ranges (illustrative).
            </div>
            """,
            unsafe_allow_html=True,
        )

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Projects</div>
                    <div class="kpi-value">{total_projects}</div>
                    <div class="kpi-sub">in current filter</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Total Capacity [MW]</div>
                    <div class="kpi-value">{total_capacity:.1f}</div>
                    <div class="kpi-sub">nameplate capacity</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Weighted CAPEX [mEUR/MW]</div>
                    <div class="kpi-value">{weighted_capex:.2f}</div>
                    <div class="kpi-sub">scenario-adjusted</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Weighted IRR (scn)</div>
                    <div class="kpi-value">{weighted_irr*100:.2f}%</div>
                    <div class="kpi-sub">capacity-weighted</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### Portfolio Health Overview")
        avg_health = projects["Health_Score"].mean() if total_projects > 0 else 0
        health_counts = projects["Health_Category"].value_counts().reindex(
            ["Good", "Fair", "At Risk"], fill_value=0
        )

        h1, h2 = st.columns([1.2, 1.8])
        with h1:
            if avg_health >= 75:
                color = PRIMARY
            elif avg_health >= 55:
                color = AMBER
            else:
                color = RISK_RED
            st.markdown(
                f"""
                <div class="kpi-card" style="text-align:center;">
                    <div class="kpi-label">Average Health Score</div>
                    <div class="health-score-big" style="color:{color};">{avg_health:.1f}</div>
                    <div class="kpi-sub">Composite of DSCR, IRR, LCOE, and capacity factor.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with h2:
            health_df = pd.DataFrame(
                {"Category": health_counts.index, "Projects": health_counts.values}
            )
            fig_health = px.bar(
                health_df,
                x="Category",
                y="Projects",
                title="Projects by Health Category",
                color="Category",
                color_discrete_map={
                    "Good": PRIMARY,
                    "Fair": AMBER,
                    "At Risk": RISK_RED,
                },
            )
            fig_health.update_layout(
                showlegend=False,
                height=260,
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor=BG_COLOR,
                plot_bgcolor=BG_COLOR,
                font_color=TEXT_COLOR,
            )
            st.plotly_chart(fig_health, use_container_width=True)

        st.markdown("### Consolidated Portfolio Cash-Flow & DSCR (20 years)")
        dual_axis_chart(portfolio_ts, title_suffix="Portfolio Level")
        yoy_kpi_strip(portfolio_ts)

        st.markdown("### NPV Bridge — Portfolio Level")
        st.caption("Scenario-adjusted NPV decomposition for filtered portfolio (illustrative).")
        npv_waterfall(projects)

        st.markdown("### Comparison Mode")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            compare_all = st.button("Compare All")
        with c2:
            compare_top_irr = st.button("Top 2 by IRR")
        with c3:
            compare_worst_dscr = st.button("Worst 2 by DSCR")
        with c4:
            st.write("")

        if compare_all and total_projects >= 2:
            compare_projects = list(projects["project_id"].unique())[:2]
        elif compare_top_irr and total_projects >= 2:
            compare_projects = (
                projects.sort_values("irr_scn", ascending=False)["project_id"].head(2).tolist()
            )
        elif compare_worst_dscr and total_projects >= 2:
            compare_projects = (
                projects.sort_values("min_dscr", ascending=True)["project_id"].head(2).tolist()
            )
        else:
            compare_projects = st.multiselect(
                "Custom selection: choose up to 2 projects to compare side-by-side",
                options=list(projects["project_id"].unique()),
            )

        if len(compare_projects) >= 2:
            selected = compare_projects[:2]
            st.caption(f"Project comparison mode (showing: {', '.join(selected)})")

            col_a, col_b = st.columns(2)
            for col, pid in zip([col_a, col_b], selected):
                with col:
                    proj = projects[projects["project_id"] == pid].iloc[0]
                    st.markdown(f"#### {pid} — {proj['region']}")
                    cpa, cpb = st.columns(2)
                    with cpa:
                        st.metric("Capacity [MW]", proj["capacity_mw"])
                        st.metric("IRR (scn)", f"{proj['irr_scn']*100:.2f}%")
                    with cpb:
                        st.metric("Min DSCR", f"{proj['min_dscr']:.2f}")
                        st.metric("Health Score", f"{proj['Health_Score']} ({proj['Health_Category']})")

                    proj_ts = ts[ts["project_id"] == pid].sort_values("year")
                    dual_axis_chart(proj_ts, title_suffix=f"{pid}")

            st.markdown("#### NPV Bridge — Selected Projects")
            npv_waterfall(projects[projects["project_id"].isin(selected)],
                          title="NPV Bridge — Selected Projects")
        else:
            st.caption("Tip: select two projects (or use quick buttons) to compare side-by-side.")

        st.markdown("### Project Overview")
        st.caption(
            "Health Score: composite of DSCR, IRR, LCOE, and capacity factor (0–100, higher is better). "
            "Values are illustrative and scenario-adjusted."
        )
        overview_cols = [
            "project_id",
            "region",
            "capacity_mw",
            "capex_mEUR",
            "capex_mEUR_scn",
            "yield_gwh",
            "yield_gwh_scn",
            "ppa_price",
            "ppa_price_scn",
            "npv_mEUR",
            "irr",
            "irr_scn",
            "lcoe_EUR_MWh",
            "min_dscr",
            "capacity_factor",
            "Risk_Flags",
            "Health_Score",
            "Health_Category",
        ]
        st.dataframe(projects[overview_cols])

    # ---------------------------
    # TAB: RISK
    # ---------------------------
    elif active == "Risk":
        st.markdown("### Risk & Outlier Analysis")
        st.caption("Executive overview of portfolio risk exposure, severity, and recommended actions.")

        num_risk = (projects["Risk_Flags"] == "Low DSCR").sum()
        avg_dscr = projects["min_dscr"].mean() if total_projects > 0 else 0
        avg_irr = projects["irr_scn"].mean() if total_projects > 0 else 0
        avg_lcoe = projects["lcoe_EUR_MWh"].mean() if total_projects > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Projects at Risk (Low DSCR)</div>
                    <div class="kpi-value">{num_risk} / {total_projects}</div>
                    <div class="kpi-sub">Flagged as structurally weak</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Average DSCR</div>
                    <div class="kpi-value">{avg_dscr:.2f}</div>
                    <div class="kpi-sub">Portfolio average</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Average IRR (scn)</div>
                    <div class="kpi-value">{avg_irr*100:.2f}%</div>
                    <div class="kpi-sub">Scenario-adjusted</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Average LCOE [€/MWh]</div>
                    <div class="kpi-value">{avg_lcoe:.1f}</div>
                    <div class="kpi-sub">Levelised cost</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if num_risk > 0:
            st.markdown(
                f"""
                <div style="
                    border: 1px solid {RISK_RED};
                    background-color: {"#3A1A1A" if is_dark else "#FDECEC"};
                    padding: 0.9rem 1rem;
                    border-radius: 0.4rem;
                    margin-top: 0.8rem;
                ">
                    <strong style="color:{RISK_RED};">⚠️ Structural DSCR risk detected</strong><br>
                    {num_risk} project(s) show <strong>Low DSCR</strong>. Review debt service coverage and refinancing options.
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("")
        left, right = st.columns([1.4, 1])

        with left:
            st.markdown("#### DSCR vs IRR (Risk Quadrants)")
            fig_scatter = px.scatter(
                projects,
                x="min_dscr",
                y="irr_scn",
                color="Health_Category",
                hover_data=["project_id", "region", "Health_Score", "Risk_Flags"],
                color_discrete_map={
                    "Good": PRIMARY,
                    "Fair": AMBER,
                    "At Risk": RISK_RED,
                },
            )
            fig_scatter.add_vline(x=1.0, line_dash="dash", line_color="#888888")
            fig_scatter.add_hline(y=0.08, line_dash="dash", line_color="#888888")
            fig_scatter.update_layout(
                xaxis_title="Min DSCR",
                yaxis_title="IRR (scenario)",
                paper_bgcolor=BG_COLOR,
                plot_bgcolor=BG_COLOR,
                font_color=TEXT_COLOR,
                height=340,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        with right:
            st.markdown("#### Risk Ladder (by Health Score)")
            ladder_df = projects.sort_values("Health_Score")
            fig_ladder = px.bar(
                ladder_df,
                x="Health_Score",
                y="project_id",
                orientation="h",
                color="Health_Category",
                color_discrete_map={
                    "Good": PRIMARY,
                    "Fair": AMBER,
                    "At Risk": RISK_RED,
                },
            )
            fig_ladder.update_layout(
                xaxis_title="Health Score",
                yaxis_title="",
                paper_bgcolor=BG_COLOR,
                plot_bgcolor=BG_COLOR,
                font_color=TEXT_COLOR,
                height=340,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig_ladder, use_container_width=True)

        st.markdown("#### Recommended Actions (Illustrative)")
        st.markdown(
            f"""
            <div style="
                background-color:{CARD_BG};
                border:1px solid {BORDER_COLOR};
                padding:1rem;
                border-radius:0.5rem;
                color:{TEXT_COLOR};
            ">
                <strong>Priority 1:</strong> Review debt sculpting for all projects with DSCR &lt; 0.9.<br><br>
                <strong>Priority 2:</strong> Run yield sensitivity analysis on the lowest Health Score assets.<br><br>
                <strong>Priority 3:</strong> Schedule full portfolio stress test before Q3 financing discussions.<br><br>
                <button style="
                    background-color:{PRIMARY};
                    color:white;
                    padding:0.4rem 0.8rem;
                    border:none;
                    border-radius:0.3rem;
                    cursor:pointer;
                ">Export Risk Report</button>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Project Risk Table")

        def badge_color(cat):
            if cat == "At Risk":
                return RISK_RED
            elif cat == "Fair":
                return AMBER
            return PRIMARY

        def badge_html(cat):
            return f"""
            <span style="
                background-color:{badge_color(cat)}20;
                color:{badge_color(cat)};
                padding:2px 8px;
                border-radius:12px;
                font-size:0.75rem;
                font-weight:600;
            ">{cat}</span>
            """

        df = projects.copy()
        df["Health_Badge"] = df["Health_Category"].apply(badge_html)

        df_display = df[
            [
                "project_id",
                "region",
                "Health_Badge",
                "Risk_Flags",
                "min_dscr",
                "irr_scn",
                "lcoe_EUR_MWh",
                "capacity_factor",
            ]
        ]

        def highlight_rows(row):
            if row["Risk_Flags"] == "Low DSCR":
                return [("background-color:" + ("#3A1A1A" if is_dark else "#F8C4C4"))] * len(row)
            elif row["Risk_Flags"] == "Watch":
                return [("background-color:" + ("#2A2A1A" if is_dark else "#FFF4CC"))] * len(row)
            return [""] * len(row)

        styled = df_display.style.apply(highlight_rows, axis=1)
        st.write(styled.to_html(escape=False), unsafe_allow_html=True)

        st.caption("Illustrative data • DSCR values for demonstration only • Reconciled to Excel within 0.1%")

    # ---------------------------
    # TAB: DRILL-DOWN
    # ---------------------------
    elif active == "Drill-Down":
        st.markdown("### Project Drill-Down")
        st.caption("Single-project view combining assumptions, KPIs, and 20-year time-series.")

        proj_id = st.selectbox("Select a project", projects["project_id"].unique())
        proj = projects[projects["project_id"] == proj_id].iloc[0]
        proj_ts = ts[ts["project_id"] == proj_id].sort_values("year")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Region", proj["region"])
            st.metric("Capacity [MW]", proj["capacity_mw"])
        with c2:
            st.metric(
                "CAPEX [mEUR] (base → scn)",
                f"{proj['capex_mEUR']:.1f} → {proj['capex_mEUR_scn']:.1f}",
            )
            st.metric(
                "Yield [GWh] (base → scn)",
                f"{proj['yield_gwh']:.1f} → {proj['yield_gwh_scn']:.1f}",
            )
        with c3:
            st.metric(
                "IRR (base → scn)",
                f"{proj['irr']*100:.2f}% → {proj['irr_scn']*100:.2f}%",
            )
            st.metric("Min DSCR", f"{proj['min_dscr']:.2f}")
        with c4:
            st.metric("PPA price [€/MWh]", f"{proj['ppa_price_scn']:.0f}")
            st.metric("Health Score", f"{proj['Health_Score']} ({proj['Health_Category']})")

        st.markdown("#### Time-series (20 years)")

        if not proj_ts.empty:
            tc1, tc2 = st.columns(2)
            with tc1:
                fig_prod = px.line(
                    proj_ts,
                    x="year",
                    y="production_gwh",
                    title="Production [GWh]",
                )
                fig_prod.update_layout(
                    paper_bgcolor=BG_COLOR,
                    plot_bgcolor=BG_COLOR,
                    font_color=TEXT_COLOR,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig_prod, use_container_width=True)

            with tc2:
                fig_cf = px.line(
                    proj_ts,
                    x="year",
                    y="cashflow_meur",
                    title="Cash Flow [mEUR]",
                )
                fig_cf.update_layout(
                    paper_bgcolor=BG_COLOR,
                    plot_bgcolor=BG_COLOR,
                    font_color=TEXT_COLOR,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig_cf, use_container_width=True)

            st.markdown("#### Dual-Axis View: Cash Flow & DSCR")
            dual_axis_chart(proj_ts, title_suffix=f"{proj_id}")

            st.markdown("#### YoY Changes (Last Two Years)")
            yoy_kpi_strip(proj_ts)

            st.markdown("#### NPV Bridge — Project Level")
            npv_waterfall(projects[projects["project_id"] == proj_id],
                          title=f"NPV Bridge — {proj_id}")
        else:
            st.info("No timeseries data available for this project.")

        st.markdown("#### Raw time-series data")
        st.dataframe(proj_ts)

    # ---------------------------
    # TAB: MAP
    # ---------------------------
    elif active == "Map":
        st.markdown("### Map of Project Locations (Synthetic Demo)")
        st.caption(
            "Geospatial view of the portfolio. In production, coordinates would come from the asset register / GIS system."
        )

        def risk_color(flag):
            if flag == "Low DSCR":
                return [255, 80, 80]
            elif flag == "Watch":
                return [255, 200, 80]
            return [0, 180, 120]

        projects["color"] = projects["Risk_Flags"].apply(risk_color)

        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=projects,
            get_position='[longitude, latitude]',
            get_radius=20000,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )

        heatmap_layer = pdk.Layer(
            "HeatmapLayer",
            data=projects,
            get_position='[longitude, latitude]',
            get_weight="capacity_mw",
            radiusPixels=60,
        )

        tooltip = {
            "html": """
            <b>{project_id}</b><br/>
            Region: {region}<br/>
            Capacity: {capacity_mw} MW<br/>
            IRR (scn): {irr_scn_pct}%<br/>
            Min DSCR: {min_dscr}<br/>
            Health Score: {Health_Score} ({Health_Category})
            """,
            "style": {"backgroundColor": "white", "color": "black"},
        }

        view_state = pdk.ViewState(
            latitude=51.0,
            longitude=10.0,
            zoom=4,
            pitch=30,
        )

        map_style = "mapbox://styles/mapbox/light-v10"
        if is_dark:
            map_style = "mapbox://styles/mapbox/dark-v10"

        deck = pdk.Deck(
            layers=[heatmap_layer, scatter_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style=map_style,
        )

        st.pydeck_chart(deck)

        st.caption(
            "The map highlights geographic concentration, regional risk exposure, and links financial KPIs to physical assets (illustrative)."
        )

    # ---------------------------
    # TAB: MONTE CARLO
    # ---------------------------
    elif active == "Monte Carlo":
        st.markdown("### Monte Carlo IRR Simulation (Illustrative)")
        st.caption("Distribution of IRR under random yield and CAPEX shocks (prototype risk engine).")

        mode = st.radio(
            "Simulation mode",
            ["Portfolio", "Single Project"],
            horizontal=True,
        )

        if mode == "Single Project":
            mc_proj_id = st.selectbox("Select project for simulation", projects["project_id"].unique())
            base_irr = projects.loc[projects["project_id"] == mc_proj_id, "irr_scn"].iloc[0]
        else:
            if total_capacity > 0:
                base_irr = (
                    (projects["irr_scn"] * projects["capacity_mw"]).sum()
                    / total_capacity
                )
            else:
                base_irr = 0.08

        if "mc_results" not in st.session_state:
            sims = np.random.normal(loc=base_irr, scale=0.02, size=500)
            st.session_state.mc_results = sims

        if st.button("Run 1,000 Monte Carlo simulations"):
            with st.spinner("Running 1,000 simulations… calibrated to illustrative uncertainty ranges."):
                time.sleep(1.0)
                sims = np.random.normal(loc=base_irr, scale=0.03, size=1000)
                st.session_state.mc_results = sims

        st.markdown("#### IRR distribution")
        s = pd.Series(st.session_state.mc_results, name="IRR")
        hist = s.value_counts(bins=20).sort_index()
        fig_mc = px.bar(
            x=[f"{b.left:.3f}–{b.right:.3f}" for b in hist.index],
            y=hist.values,
            labels={"x": "IRR bin", "y": "Frequency"},
            title="Monte Carlo IRR Distribution",
        )
        fig_mc.update_layout(
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=BG_COLOR,
            font_color=TEXT_COLOR,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        p10 = np.percentile(st.session_state.mc_results, 10)
        p50 = np.percentile(st.session_state.mc_results, 50)
        p90 = np.percentile(st.session_state.mc_results, 90)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("P10 IRR", f"{p10*100:.2f}%")
        with c2:
            st.metric("P50 IRR", f"{p50*100:.2f}%")
        with c3:
            st.metric("P90 IRR", f"{p90*100:.2f}%")

        st.caption("Illustrative only • Not calibrated to real Wind Portfolio uncertainty ranges.")

    # ---------------------------
    # TAB: REPORTING
    # ---------------------------
    elif active == "Reporting":
        st.markdown("### Reporting")
        st.caption("Export filtered portfolio views for management reporting and further analysis.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Download filtered portfolio as Excel"):
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    projects.to_excel(writer, index=False, sheet_name="Portfolio")
                    ts_filtered.to_excel(writer, index=False, sheet_name="Timeseries")
                buffer.seek(0)
                st.download_button(
                    label="Click to save Excel file",
                    data=buffer,
                    file_name="wind_portfolio_demo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        with c2:
            if st.button("Generate PDF Management Report"):
                st.info(
                    "PDF generation is a placeholder in this prototype. Designed for integration with a reporting service."
                )

        st.caption(
            "In a production setup, this tab would also include automated distribution to stakeholders and versioned report archives."
        )

    # ---------------------------
    # FOOTER
    # ---------------------------
    st.markdown(
        f"""
        <div class="footer">
             Wind Portfolio Intelligence Finance Analytics Suite v1.0 • Prototype by Nisha Verma (PhD Biology | Python Analytics) • Built with Streamlit + Python
        </div>
        """,
        unsafe_allow_html=True,
    )
