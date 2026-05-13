"""Page 2: FIRE Scenarios — Coast/Lean/Fat/Barista crossover analysis."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import run_yearly_projection, dca_crossover_year, salary_crossover_year
from engines.calculation_engine import (
    fire_target, lean_fire_target, fat_fire_target, barista_fire_target,
    coast_fire_target, fire_age, preservation_age,
)
from engines.tax_engine import gross_withdrawal_for_net_spend

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
    median_spending  = st.number_input("Your FIRE Spending/yr",   min_value=0, value=80_000, step=5_000,
                                       help="Your personal target spending in retirement, after tax.")
    fat_spending     = st.number_input("Fat FIRE Spending/yr",    min_value=0, value=120_000, step=5_000)
    barista_income   = st.number_input("Barista Part-Time Income", min_value=0, value=20_000, step=2_000)
    barista_spending = st.number_input("Barista Total Spending",   min_value=0, value=60_000, step=5_000)
    swr              = st.slider("SWR (%)", 2.0, 6.0, 4.0, 0.25) / 100.0
    st.divider()
    inflation_rate = st.slider("Inflation (%)", 0.0, 10.0, 2.5, 0.1)
    horizon_years  = st.slider("Horizon (Years)", 5, 60, 35)
    st.divider()
    st.header("🏦 Superannuation")
    birth_year    = st.number_input("Birth Year", min_value=1940, max_value=2005, value=1990, step=1)
    _default_pres = preservation_age(birth_year)
    pres_age      = st.number_input(
        "Super Access Age",
        min_value=55, max_value=75, value=_default_pres, step=1,
        help=f"Auto-set to {_default_pres} from your birth year. Override here if the law changes.",
    )
    super_balance = st.number_input("Current Super Balance (AUD)", min_value=0, value=50_000, step=5_000)
    super_return  = st.slider("Super Annual Return (%)", 3.0, 12.0, 7.0, 0.5)
    sgc_rate      = st.slider(
        "Super Contribution Rate (%)", 8.0, 30.0, 11.5, 0.5,
        help="Employer SGC is 11.5% in 2024-25, rising to 12% from 1 July 2025. "
             "Add voluntary contributions here too.",
    )

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

bridge_cols = st.columns(4)

# Tax-adjusted gross withdrawals needed to fund each target after tax
lean_gross    = gross_withdrawal_for_net_spend(lean_spending)
median_gross  = gross_withdrawal_for_net_spend(median_spending)
fat_gross     = gross_withdrawal_for_net_spend(fat_spending)
barista_gross = gross_withdrawal_for_net_spend(max(barista_spending - barista_income, 0))

lean_num_adj    = lean_gross    / swr
median_num_adj  = median_gross  / swr
fat_num_adj     = fat_gross     / swr
barista_num_adj = barista_gross / swr

# Projected age to reach each FIRE target — find best (earliest) strategy
def _best_fire_age(target: float) -> tuple[int | None, str | None]:
    candidates = [(fire_age(current_age, proj_df, target, s), s) for s in selected]
    candidates = [(a, s) for a, s in candidates if a is not None]
    if not candidates:
        return None, None
    return min(candidates, key=lambda x: x[0])

lean_age,    lean_strat    = _best_fire_age(lean_num_adj)
median_age,  median_strat  = _best_fire_age(median_num_adj)
fat_age,     fat_strat     = _best_fire_age(fat_num_adj)
barista_age, barista_strat = _best_fire_age(barista_num_adj)

t_col1, t_col2, t_col3, t_col4 = st.columns(4)
with t_col1:
    lean_delta = f"Age {lean_age} · ${lean_gross:,.0f}/yr gross" if lean_age else "Not in horizon"
    st.metric("🥦 Lean FIRE (Tax-Adjusted)", f"${lean_num_adj:,.0f}",
              delta=lean_delta, delta_color="normal" if lean_age else "off",
              help=f"Portfolio to fund ${lean_spending:,}/yr after-tax at {swr*100:.1f}% SWR. "
                   f"Earliest via: {lean_strat or 'N/A'}")
with t_col2:
    med_delta = f"Age {median_age} · ${median_gross:,.0f}/yr gross" if median_age else "Not in horizon"
    st.metric("🎯 Your FIRE (Tax-Adjusted)", f"${median_num_adj:,.0f}",
              delta=med_delta, delta_color="normal" if median_age else "off",
              help=f"Portfolio to fund ${median_spending:,}/yr after-tax at {swr*100:.1f}% SWR. "
                   f"Earliest via: {median_strat or 'N/A'}")
with t_col3:
    fat_delta = f"Age {fat_age} · ${fat_gross:,.0f}/yr gross" if fat_age else "Not in horizon"
    st.metric("🥩 Fat FIRE (Tax-Adjusted)", f"${fat_num_adj:,.0f}",
              delta=fat_delta, delta_color="normal" if fat_age else "off",
              help=f"Portfolio to fund ${fat_spending:,}/yr after-tax at {swr*100:.1f}% SWR. "
                   f"Earliest via: {fat_strat or 'N/A'}")
with t_col4:
    bar_delta = f"Age {barista_age} · ${barista_gross:,.0f}/yr gross" if barista_age else "Not in horizon"
    st.metric("☕ Barista FIRE (Tax-Adjusted)", f"${barista_num_adj:,.0f}",
              delta=bar_delta, delta_color="normal" if barista_age else "off",
              help=f"Portfolio to fund ${barista_spending:,}/yr after-tax minus ${barista_income:,} "
                   f"part-time at {swr*100:.1f}% SWR. Earliest via: {barista_strat or 'N/A'}")

st.caption(
    f"💡 **Tax-adjusted** figures show the gross withdrawal needed to yield your target spending "
    f"**after** income tax, Medicare levy, and LITO.  "
    f"Your FIRE number: **${median_num_adj:,.0f}** "
    f"(${median_spending:,}/yr after-tax · gross ${median_gross:,.0f}/yr · "
    f"{'age ' + str(median_age) if median_age else 'not in horizon'})."
)

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
    ay_offset = -40 - i * 25
    if dca_yr and dca_yr < len(proj_df):
        fig.add_annotation(x=dca_yr + current_age, y=float(proj_df["Yearly_DCA"].iloc[dca_yr]),
                           text=f"Coast {strat[:8]} yr {dca_yr}", showarrow=True, arrowhead=2,
                           ax=-40, ay=ay_offset,
                           bgcolor=COLORS["blue"], font=dict(color="white", size=10))
    if sal_yr and sal_yr < len(proj_df):
        fig.add_annotation(x=sal_yr + current_age, y=float(proj_df["Salary"].iloc[sal_yr]),
                           text=f"FI {strat[:8]} yr {sal_yr}", showarrow=True, arrowhead=1,
                           ax=40, ay=ay_offset,
                           bgcolor=color, font=dict(color="white", size=10))

# Super preservation age vertical line
if pres_age <= current_age + horizon_years:
    fig.add_vline(x=pres_age, line_color=COLORS["purple"], line_dash="dot", line_width=2,
                  annotation_text=f"Super access age {pres_age}",
                  annotation_font_color=COLORS["purple"],
                  annotation_position="top right")

fig.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                  xaxis=dict(title="Age", dtick=5),
                  yaxis=dict(tickformat="$.3s", title="Annual Amount (Real AUD)"),
                  hovermode="x unified", height=550,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, width='stretch')

with st.expander("📖 How to read the Double Crossover chart"):
    st.markdown("""
**The Double Crossover** reveals two critical moments on your path to FIRE:

| Crossover | What it means |
|-----------|---------------|
| **Annual Profit > Annual DCA** (Coast point) | Your portfolio's yearly growth exceeds what you're contributing. You could stop investing and still reach FIRE. |
| **Annual Profit > Annual Salary** (FI point) | Your portfolio generates more each year than your job does. You are financially independent. |

**Reading the lines:**
- **Yellow** — your gross salary, growing with salary growth rate
- **Dotted yellow** — your annual DCA contribution
- **Coloured lines** — each strategy's annual investment profit (growth minus contributions)

**What to look for:**
- The earlier the crossovers occur, the sooner you reach each milestone
- A steep profit line = strong compounding effect
- If profit never crosses salary in your horizon, extend the horizon or increase DCA

> Tax-adjusted FIRE numbers account for income tax and Medicare levy using 2024-25 rates + LITO.
""")

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

st.divider()
st.subheader("🏦 Super Access Strategy")
sc1, sc2, sc3 = st.columns(3)
sc1.metric("🔑 Super Preservation Age", str(pres_age),
           help="Age you can first access your superannuation (based on birth year)")

# Project super balance to preservation age:
# each year — grow existing balance, add net-of-tax employer/voluntary contributions
# salary grows at salary_growth rate; SGC contributions taxed at 15% flat
years_to_pres  = max(pres_age - current_age, 0)
_r             = super_return / 100.0
_sg            = salary_growth / 100.0
_sgc           = sgc_rate / 100.0
_super_bal     = float(super_balance)
_current_sal   = float(salary)
_annual_contribs_total = 0.0

for _ in range(years_to_pres):
    net_contrib       = _current_sal * _sgc * (1.0 - 0.15)   # 15% contributions tax
    _super_bal        = _super_bal * (1.0 + _r) + net_contrib
    _annual_contribs_total += net_contrib
    _current_sal     *= (1.0 + _sg)

super_at_pres       = _super_bal
avg_annual_contrib  = _annual_contribs_total / years_to_pres if years_to_pres > 0 else 0.0

sc2.metric(
    f"💰 Projected Super at Age {pres_age}", f"${super_at_pres:,.0f}",
    help=(
        f"Starting balance: ${super_balance:,}  ·  "
        f"Avg annual contribution (net of 15% tax): ~${avg_annual_contrib:,.0f}  ·  "
        f"Return: {super_return}%/yr  ·  Salary growth: {salary_growth}%/yr  ·  "
        f"Over {years_to_pres} years"
    ),
)

super_swr_income = super_at_pres * swr
sc3.metric("📥 Super SWR Income", f"${super_swr_income:,.0f}/yr",
           help=f"Annual income from super at {swr*100:.1f}% SWR from age {pres_age}")

# Bridge period — years between earliest FI and super access
best_sal_yr = min((salary_crossover_year(proj_df, s) for s in selected if salary_crossover_year(proj_df, s)), default=None)
if best_sal_yr:
    fire_age_est = current_age + best_sal_yr
    bridge = max(pres_age - fire_age_est, 0)
    if bridge > 0:
        st.info(f"🌉 **Bridge period: {bridge} years** (age {fire_age_est} → {pres_age}). "
                f"You'll draw from your non-super portfolio for {bridge} years before super kicks in. "
                f"Super then contributes ~${super_swr_income:,.0f}/yr, reducing required non-super drawdown.")
    else:
        st.success(f"✅ You reach FI at age {fire_age_est}, **after** your super preservation age ({pres_age}). "
                   f"Super is immediately accessible — it contributes ~${super_swr_income:,.0f}/yr to your income.")

st.warning("⚠️ Projections use median historical CAGR. Not a guarantee of future performance.")
