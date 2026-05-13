"""Page 2: FIRE Scenarios — Coast/Lean/Fat/Barista crossover analysis."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import run_yearly_projection, dca_crossover_year, salary_crossover_year
from engines.calculation_engine import (
    fire_target, lean_fire_target, fat_fire_target, barista_fire_target,
    coast_fire_target, fire_age
)

st.set_page_config(page_title="FIRE Scenarios", page_icon="🎯", layout="wide")
st.title("🎯 FIRE Scenarios")

with st.sidebar:
    st.header("💰 Inputs")
    current_age   = st.number_input("Current Age",            min_value=18, max_value=80,  value=30)
    salary        = st.number_input("Annual Salary (AUD)",    min_value=0, value=100_000, step=5_000)
    salary_growth = st.number_input("Salary Growth (%/yr)",   min_value=0.0, value=3.0, step=0.5)
    portfolio     = st.number_input("Starting Portfolio",     min_value=0, value=50_000, step=5_000)
    dca_method    = st.radio("DCA Method", ["Fixed Monthly Amount", "Percentage of Salary"])
    if dca_method == "Fixed Monthly Amount":
        dca_value = st.number_input("Monthly DCA (AUD)", min_value=0, value=1_500, step=100)
    else:
        dca_value = st.number_input("Salary %", min_value=0.0, max_value=100.0, value=20.0)
    dca_grows     = st.checkbox("DCA grows with salary", value=True)
    stop_at_coast = st.toggle("Stop DCA at Coast Year", value=False)
    st.divider()
    st.header("📉 Spending Targets")
    lean_spending    = st.number_input("Lean FIRE Spending/yr",   min_value=0, value=40_000, step=5_000)
    fat_spending     = st.number_input("Fat FIRE Spending/yr",    min_value=0, value=120_000, step=5_000)
    barista_income   = st.number_input("Barista Part-Time Income", min_value=0, value=20_000, step=2_000)
    barista_spending = st.number_input("Barista Total Spending",   min_value=0, value=60_000, step=5_000)
    swr              = st.slider("SWR (%)", 2.0, 6.0, 4.0, 0.25) / 100.0
    st.divider()
    inflation_rate = st.slider("Inflation (%)", 0.0, 10.0, 2.5, 0.1)
    horizon_years  = st.slider("Horizon (Years)", 5, 60, 35)

result = load_latest_backtest_csv()
if result is None:
    st.warning("No backtest CSV found. Run `rolling_backtest_suite.py` first.")
    st.stop()
data, _ = result

all_strategies = data.strategies
selected = st.multiselect("Strategies to compare", all_strategies, default=all_strategies[:min(3, len(all_strategies))])
if not selected:
    st.error("Select at least one strategy.")
    st.stop()

proj_df = run_yearly_projection(
    data.cagr_df, selected, portfolio, dca_method, dca_value, dca_grows, stop_at_coast,
    salary_growth, salary, horizon_years, "Decimal (0.05 = 5%)", inflation_rate, True,
)

lean_num    = lean_fire_target(lean_spending, swr)
fat_num     = fat_fire_target(fat_spending, swr)
barista_num = barista_fire_target(barista_spending, barista_income, swr)

t_col1, t_col2, t_col3 = st.columns(3)
with t_col1:
    st.metric("🥦 Lean FIRE", f"${lean_num:,.0f}", help=f"${lean_spending:,}/yr at {swr*100:.1f}% SWR")
with t_col2:
    st.metric("🥩 Fat FIRE",  f"${fat_num:,.0f}",  help=f"${fat_spending:,}/yr at {swr*100:.1f}% SWR")
with t_col3:
    st.metric("☕ Barista FIRE", f"${barista_num:,.0f}",
              help=f"${barista_spending:,}/yr - ${barista_income:,} part-time income at {swr*100:.1f}% SWR")

st.divider()
st.subheader("🚀 The Double Crossover")
fig = go.Figure()
ages = proj_df["Year"] + current_age

fig.add_trace(go.Scatter(x=ages, y=proj_df["Salary"], name="Annual Salary",
                          line=dict(color=COLORS["yellow"], width=3),
                          hovertemplate="Salary: $%{y:,.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=ages, y=proj_df["Yearly_DCA"], name="Annual DCA",
                          line=dict(color=COLORS["soft_yellow"], width=2, dash="dot"),
                          hovertemplate="DCA: $%{y:,.0f}<extra></extra>"))

for i, strat in enumerate(selected):
    color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
    profit = proj_df[f"{strat}_Yearly_Profit"]
    fig.add_trace(go.Scatter(x=ages, y=profit, name=f"{strat} Annual Profit",
                              line=dict(color=color, width=2),
                              hovertemplate=f"{strat}: $%{{y:,.0f}}<extra></extra>"))
    dca_yr = dca_crossover_year(proj_df, strat)
    sal_yr = salary_crossover_year(proj_df, strat)
    if dca_yr and dca_yr < len(proj_df):
        fig.add_annotation(x=dca_yr + current_age, y=float(proj_df["Yearly_DCA"].iloc[dca_yr]),
                           text=f"Coast Yr {dca_yr}", showarrow=True, arrowhead=2, ax=-40, ay=-40,
                           bgcolor=COLORS["blue"], font=dict(color="white", size=11))
    if sal_yr and sal_yr < len(proj_df):
        fig.add_annotation(x=sal_yr + current_age, y=float(proj_df["Salary"].iloc[sal_yr]),
                           text=f"FI Yr {sal_yr}", showarrow=True, arrowhead=1, ax=40, ay=-40,
                           bgcolor=color, font=dict(color="white", size=11))

fig.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                  xaxis_title="Age", yaxis_title="Annual Amount (Real AUD)",
                  hovermode="x unified", height=550,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)

milestones = []
for strat in selected:
    sal_yr = salary_crossover_year(proj_df, strat)
    if sal_yr:
        milestones.append({"Strategy": strat, "FI Year": sal_yr, "FI Age": current_age + sal_yr})
if milestones:
    milestones.sort(key=lambda x: x["FI Year"])
    best = milestones[0]
    cols = st.columns(len(milestones))
    for i, m in enumerate(milestones):
        with cols[i]:
            st.metric(f"🏁 {m['Strategy']}", f"Age {m['FI Age']}", f"Year {m['FI Year']}")
    st.success(f"🎉 Earliest FI: **{best['Strategy']}** at age **{best['FI Age']}**")

st.warning("⚠️ Projections use median historical CAGR. Not a guarantee of future performance.")
