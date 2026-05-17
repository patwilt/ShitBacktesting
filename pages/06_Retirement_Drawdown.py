"""Retirement Drawdown — slider-adjustable withdrawal with depletion year indicator."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go

from utils.colors import COLORS, STRATEGY_COLORS, CHART_LAYOUT
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import depletion_year, swr_income
from utils import shared_profile as profile

st.set_page_config(page_title="Retirement Drawdown", page_icon="💸", layout="wide")
profile.init()
st.title("💸 Retirement Drawdown")
st.caption("Step 6 of your journey: stress-test your retirement income. Model safe withdrawal rates, inflation, and portfolio depletion risk.")

# Default portfolio defaults to household net worth when available; otherwise
# fall back to (portfolio + household super) so couples don't see a tiny solo
# default that ignores their partner's super.
_partnered     = profile.is_partnered()
_pf_net_worth  = profile.get("pf_net_worth")
if _pf_net_worth is not None:
    _default_portf = int(_pf_net_worth)
else:
    _default_portf = int((profile.get("pf_portfolio") or 0)
                         + profile.household_super_balance())
    if _default_portf <= 0:
        _default_portf = 1_500_000
_pf_asp         = profile.get("pf_annual_spending")
_default_withdraw = int(_pf_asp) if _pf_asp is not None else 80_000

with st.sidebar:
    profile.sidebar_summary()
    if profile.is_set():
        st.caption("✅ Pre-filled from profile. Adjust locally here.")
        if _partnered:
            st.caption("👥 Couple mode: portfolio default includes household super.")
    st.header("💰 Portfolio")
    portfolio       = st.number_input("Retirement Portfolio (AUD)", min_value=0,
                                      value=_default_portf, step=50_000)
    annual_return   = st.slider("Annual Portfolio Return (%, nominal)", 0.0, 20.0,
                                profile.get("pf_portfolio_return"), 0.1,
                                help="Nominal return before inflation. App converts to real return internally.") / 100.0
    inflation_rate  = st.slider("Inflation Rate (%)", 0.0, 10.0,
                                profile.get("pf_inflation"), 0.1) / 100.0
    st.divider()
    st.header("💸 Withdrawal")
    swr_rate    = st.slider("Safe Withdrawal Rate (%)", 2.0, 10.0, profile.get("pf_swr"), 0.25) / 100.0
    swr_default = swr_income(portfolio, swr_rate)
    st.caption(f"4% SWR baseline: ${swr_default:,.0f}/yr")
    _withdrawal_default = max(
        min(_default_withdraw, min(int(portfolio), 500_000)),
        10_000
    )
    annual_withdrawal = st.slider(
        "Annual Withdrawal (AUD)",
        min_value=10_000, max_value=min(int(portfolio), 500_000),
        value=_withdrawal_default, step=1_000,
        help="Drag to see how long your portfolio lasts. Pre-filled from your Budget page spending."
    )
    st.divider()
    max_years = st.slider("Simulation Horizon (Years)", 10, 100, 50, 5)

result = load_latest_backtest_csv()
if result is None:
    st.warning("No backtest CSV found.")
    st.stop()
data, _ = result

dep_year = depletion_year(portfolio, annual_withdrawal, annual_return, inflation_rate, max_years)

if dep_year:
    if dep_year < 20:
        color = COLORS["red"]
        icon  = "🚨"
        label = f"Portfolio depletes in **{dep_year} years**"
    elif dep_year <= 30:
        color = COLORS["orange"]
        icon  = "⚠️"
        label = f"Portfolio lasts **{dep_year} years**"
    else:
        color = COLORS["yellow"]
        icon  = "✅"
        label = f"Portfolio lasts **{dep_year} years**"
else:
    color = COLORS["mint"]
    icon  = "🏆"
    label = f"Portfolio survives all **{max_years} years**. Safe zone!"

st.markdown(f"### {icon} {label}")

swr_colA, swr_colB, swr_colC = st.columns(3)
swr_colA.metric("Annual Withdrawal",       f"${annual_withdrawal:,.0f}")
swr_colB.metric("Effective SWR",           f"{(annual_withdrawal / portfolio * 100) if portfolio > 0 else 0:.2f}%")
swr_colC.metric("Depletion Year",          str(dep_year) if dep_year else f">{max_years} yrs")

st.divider()
st.subheader("Portfolio Balance Over Time")

balance   = float(portfolio)
real_r_plot = (1.0 + annual_return) / (1.0 + inflation_rate) - 1.0
years_plot = []
values_plot = []
for y in range(max_years + 1):
    years_plot.append(y)
    values_plot.append(max(balance, 0))
    if balance <= 0:
        break
    # Withdrawal stays constant in real terms; balance in today's AUD
    balance = balance * (1.0 + real_r_plot) - annual_withdrawal

fig = go.Figure()

# Per-year zone markers: green when balance is healthy, amber as the buffer
# erodes, red once it drops below 25% of the starting portfolio. This gives a
# subtle visual signal of risk along the line without needing a second axis.
zone_color = [
    COLORS["red"]    if v <= portfolio * 0.25
    else COLORS["orange"] if v <= portfolio * 0.50
    else COLORS["mint"]
    for v in values_plot
]

fig.add_trace(go.Scatter(
    x=years_plot, y=values_plot,
    mode="lines+markers",
    name="Portfolio Balance",
    line=dict(color=COLORS["blue"], width=3),
    marker=dict(color=zone_color, size=7, line=dict(width=0)),
    fill="tozeroy",
    fillcolor="rgba(66, 117, 160, 0.15)",
    hovertemplate="Year %{x}<br>Balance: $%{y:,.0f}<extra></extra>",
))

safe_zone_y = portfolio * 0.50
fig.add_hrect(y0=0, y1=safe_zone_y, fillcolor="rgba(168, 72, 72, 0.08)", layer="below", line_width=0)
fig.add_hline(y=safe_zone_y, line_dash="dash", line_color=COLORS["orange"],
              annotation_text="50%: Caution Zone", annotation_font_color=COLORS["orange"])
fig.add_hline(y=0, line_color=COLORS["red"], line_width=2,
              annotation_text="Depletion", annotation_font_color=COLORS["red"])

if dep_year and dep_year <= max_years:
    fig.add_vline(x=dep_year, line_color=COLORS["red"], line_dash="dash",
                  annotation_text=f"Depletes year {dep_year}", annotation_font_color=COLORS["red"])

fig.update_layout(
    **CHART_LAYOUT,
    xaxis=dict(title="Years in Retirement", dtick=5),
    yaxis=dict(tickformat="$.3s", title="Portfolio Balance (Real AUD, today's dollars)"),
    height=500,
)
st.plotly_chart(fig, width='stretch')

with st.expander("📖 How to read this chart"):
    st.markdown("""
**Portfolio Balance Over Time** simulates your retirement portfolio being drawn down each year.

- **Blue line / shaded area**: your portfolio balance, year by year
- **Orange dashed line (50%)**: caution zone: below this your portfolio may not last
- **Red zone (shading)**: danger zone: below 50% of starting balance
- **Red vertical line**: the year your portfolio hits zero (depletion year)

**The withdrawal slider** adjusts your annual drawdown. The depletion year updates in real time.

**Inflation effect:** Your withdrawal amount stays constant in **real** (today's) purchasing power.
The chart shows balances in today's dollars. The real return (nominal minus inflation) is used internally.

**Safe zone guide:**
| Depletion Year | Signal |
|----------------|--------|
| Never depletes | 🏆 Sustainable indefinitely |
| > 30 years | ✅ Generally safe for a 30-year retirement |
| 20–30 years | ⚠️ Moderate risk, consider reducing spending |
| < 20 years | 🚨 High risk, portfolio likely insufficient |

> Values shown in **real** (inflation-adjusted, today's) AUD. Your annual withdrawal maintains constant purchasing power. In nominal terms you would draw more each year due to inflation.
""")

st.divider()
st.subheader("Strategy-Specific Depletion Comparison")
strategy_dep_data = []
for strat in data.strategies:
    median_return = float(data.cagr_df[strat].median())
    dep = depletion_year(portfolio, annual_withdrawal, median_return, inflation_rate, max_years)
    strategy_dep_data.append({
        "Strategy": strat,
        "Median Return (%)": f"{median_return*100:.1f}%",
        "Depletion Year": dep if dep else f">{max_years}",
    })
import pandas as pd
dep_df = pd.DataFrame(strategy_dep_data).set_index("Strategy")
st.dataframe(dep_df, width='stretch')

st.caption("⚠️ Values in real AUD (today's purchasing power). Nominal returns converted to real returns internally. Uses median historical CAGR from backtest data.")
