"""Page 1: Dashboard — FIRE overview with key metrics and net worth timeline."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import run_yearly_projection
from engines.calculation_engine import fire_target, fire_age, coast_fire_target, preservation_age
from engines.tax_engine import gross_withdrawal_for_net_spend

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("📊 Dashboard")
st.caption("Your FIRE snapshot at a glance.")

with st.sidebar:
    st.header("👤 Your Details")
    current_age       = st.number_input("Current Age",            min_value=18, max_value=80,  value=30, step=1)
    target_retire_age = st.number_input("Target Retirement Age",  min_value=current_age+1, max_value=100, value=55, step=1)
    st.divider()
    st.header("💰 Finances")
    current_portfolio = st.number_input("Current Portfolio (AUD)", min_value=0, value=50_000, step=5_000)
    monthly_dca       = st.number_input("Monthly DCA (AUD)",       min_value=0, value=1_500,  step=100)
    salary            = st.number_input("Annual Salary (AUD)",     min_value=0, value=100_000, step=5_000)
    birth_year    = st.number_input("Birth Year", min_value=1940, max_value=2005, value=1990, step=1)
    super_balance = st.number_input("Super Balance (AUD)", min_value=0, value=50_000, step=5_000)
    st.divider()
    st.header("📉 Assumptions")
    inflation_rate  = st.slider("Inflation Rate (%)",  0.0, 10.0, 2.5, 0.1, help="Annual CPI assumption")
    annual_return   = st.slider("Expected Return (%)", 0.0, 20.0, 7.0, 0.1, help="Median annual portfolio return")
    target_spending = st.number_input("Annual Retirement Spending (AUD)", min_value=0, value=80_000, step=5_000)
    swr             = st.slider("Safe Withdrawal Rate (%)", 2.0, 6.0, 4.0, 0.25, help="Annual % withdrawn in retirement") / 100.0

result = load_latest_backtest_csv()
if result is None:
    st.warning("No backtest CSV found. Run `rolling_backtest_suite.py` first, or upload a CSV on the FIRE Scenarios page.")
    st.stop()

data, csv_path = result
st.caption(f"Using: `{csv_path}`")

years_to_retire = target_retire_age - current_age
fire_num        = fire_target(target_spending, swr)
coast_num       = coast_fire_target(fire_num, years_to_retire, annual_return / 100.0)
fire_num_tax_adj = gross_withdrawal_for_net_spend(target_spending) / swr
pres_age         = preservation_age(birth_year)

strategy_cols = data.strategies
proj_df = run_yearly_projection(
    data.cagr_df,
    strategy_cols,
    initial_portfolio=current_portfolio,
    dca_method="Fixed Monthly Amount",
    dca_value=monthly_dca,
    dca_grows=False,
    stop_at_coast=False,
    salary_growth=3.0,
    initial_salary=salary,
    horizon_years=min(years_to_retire, 50),
    return_format="Decimal (0.05 = 5%)",
    inflation_rate=inflation_rate,
    adjust_inflation=True,
)

first_strat = strategy_cols[0]
projected_at_retire = proj_df[f"{first_strat}_Total"].iloc[-1] if not proj_df.empty else 0
fire_age_val = fire_age(current_age, proj_df, fire_num, first_strat)
years_to_fire = (fire_age_val - current_age) if fire_age_val else None

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("🎯 FIRE Number (Tax-Adj.)", f"${fire_num_tax_adj:,.0f}",
              help=f"Gross withdrawal ÷ SWR to yield ${target_spending:,}/yr after-tax. Accounts for income tax and Medicare levy.")
with col2:
    st.metric("🌊 Coast FIRE Number", f"${coast_num:,.0f}",
              help=f"Amount needed today to coast to FIRE by age {target_retire_age}")
with col3:
    if fire_age_val:
        st.metric("🔥 Projected FIRE Age", str(fire_age_val), delta=f"{years_to_fire} years away")
    else:
        st.metric("🔥 Projected FIRE Age", "Not in horizon", delta="Increase DCA or extend horizon")
with col4:
    st.metric(f"📈 Portfolio at Age {target_retire_age}", f"${projected_at_retire:,.0f}",
              delta=f"{'Above' if projected_at_retire >= fire_num else 'Below'} FIRE number")
with col5:
    years_to_pres = max(pres_age - current_age, 0)
    st.metric("🏦 Super Access Age", str(pres_age),
              delta=f"{years_to_pres} yrs away" if years_to_pres > 0 else "Accessible now",
              help="Age you can access your superannuation. Based on birth year under ATO preservation rules.")

st.divider()
st.subheader("Net Worth Timeline")

fig = go.Figure()
for i, strat in enumerate(strategy_cols):
    color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
    fig.add_trace(go.Scatter(
        x=proj_df["Year"] + current_age,
        y=proj_df[f"{strat}_Total"],
        name=strat,
        line=dict(color=color, width=2),
        hovertemplate=f"{strat}<br>Age %{{x}}<br>${{y:,.0f}}<extra></extra>",
    ))

fig.add_hline(y=fire_num, line_dash="dash", line_color=COLORS["yellow"],
              annotation_text=f"FIRE Number ${fire_num/1e6:.1f}M",
              annotation_font_color=COLORS["yellow"])

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    xaxis_title="Age",
    yaxis_title="Portfolio Value (Real AUD)",
    hovermode="x unified",
    height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

st.caption("All values in real (inflation-adjusted) dollars. Projections use median historical CAGR from backtest data.")
st.warning("⚠️ This is a projection, not a guarantee. Past performance does not predict future returns.")
