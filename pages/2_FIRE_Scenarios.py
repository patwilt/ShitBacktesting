"""Page 2: FIRE Scenarios — Coast/Lean/Fat/Barista crossover analysis."""
from __future__ import annotations
import pandas as pd
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

# ── Two-bucket drawdown chart ─────────────────────────────────────────────────
st.divider()
st.subheader("📊 Two-Bucket Drawdown Projection")

# Determine FIRE age and median portfolio return
fire_age_target = median_age if median_age else (current_age + horizon_years)
years_to_fire   = max(fire_age_target - current_age, 0)
port_return     = float(data.cagr_df[median_strat].median()) if (median_strat and median_strat in data.cagr_df.columns) else 0.07

# Non-super balance at FIRE age (from projection)
_strat_col = f"{median_strat}_Total" if (median_strat and f"{median_strat}_Total" in proj_df.columns) else f"{selected[0]}_Total"
non_super_at_fire = float(proj_df[_strat_col].iloc[min(years_to_fire, len(proj_df) - 1)])

# Super balance at FIRE age (accumulate with SGC contributions up to FIRE age)
_r2, _sg2, _sgc2 = super_return / 100.0, salary_growth / 100.0, sgc_rate / 100.0
_sb2, _sal2 = float(super_balance), float(salary)
for _ in range(years_to_fire):
    _sb2  = _sb2 * (1.0 + _r2) + _sal2 * _sgc2 * 0.85
    _sal2 *= (1.0 + _sg2)
super_at_fire = _sb2

# ── Controls ──────────────────────────────────────────────────────────────────
ctrl1, ctrl2 = st.columns([2, 1])
with ctrl1:
    sim_end_age = st.slider("Project to Age (death)", min_value=fire_age_target + 5, max_value=100, value=90, step=1)
with ctrl2:
    bridge_withdrawal = st.number_input(
        "Strat A — Bridge Withdrawal (AUD/yr)",
        min_value=0, value=int(median_gross), step=1_000,
        help="Strategy A only: annual withdrawal from non-super during bridge. Strategy B computes its own optimal rate.",
    )

inf_r = inflation_rate / 100.0
sim_ages = list(range(fire_age_target, sim_end_age + 1))

# ── Helper: simulate two-bucket drawdown with a fixed initial withdrawal ──────
def _sim_buckets(
    ns0: float, sup0: float,
    w0_bridge: float, w0_post: float,
) -> tuple[list[float], list[float]]:
    """
    Simulate from fire_age_target to sim_end_age.
    Bridge phase (before pres_age): draw w_bridge from non-super; super compounds.
    Post-pres phase: draw w_post from super first; overflow to non-super if super empty.
    Both w values inflate by inf_r each year.
    """
    ns, sup = ns0, sup0
    w_b, w_p = w0_bridge, w0_post
    ns_out, sup_out = [], []
    for age in sim_ages:
        ns_out.append(max(ns, 0.0))
        sup_out.append(max(sup, 0.0))
        if age < pres_age:
            ns  = max(ns, 0.0) * (1.0 + port_return) - w_b
            sup = max(sup, 0.0) * (1.0 + _r2)
            w_b *= (1.0 + inf_r)
        else:
            draw = w_p
            sup_growth = max(sup, 0.0) * (1.0 + _r2)
            if sup_growth >= draw:
                sup = sup_growth - draw
                ns  = max(ns, 0.0) * (1.0 + port_return)
            else:
                leftover = draw - sup_growth
                sup = 0.0
                ns  = max(ns, 0.0) * (1.0 + port_return) - leftover
            w_p *= (1.0 + inf_r)
    return ns_out, sup_out

# ── Strategy A: SWR — draw SWR% of super post-preservation; non-super compounds
swr_post_w = (
    max(
        float(
            max(
                max(non_super_at_fire, 0.0) * (1.0 + port_return) ** max(pres_age - fire_age_target, 0),
                0.0,
            )
        ),
        0.0,
    ) * 0.0  # placeholder; we'll compute below
)

# Properly compute super at pres_age (compounding, no contributions post-FIRE)
_ns_p, _sup_p, _wb = non_super_at_fire, super_at_fire, float(bridge_withdrawal)
for _age in range(fire_age_target, pres_age):
    _ns_p  = max(_ns_p, 0.0) * (1.0 + port_return) - _wb
    _sup_p = max(_sup_p, 0.0) * (1.0 + _r2)
    _wb   *= (1.0 + inf_r)
super_at_pres_unlocked = max(_sup_p, 0.0)
swr_post_w = super_at_pres_unlocked * swr

ns_A, sup_A = _sim_buckets(non_super_at_fire, super_at_fire, float(bridge_withdrawal), swr_post_w)

# ── Strategy B: Deplete BOTH to $0 by sim_end_age ────────────────────────────
# Binary-search for the uniform withdrawal W (applied from FIRE age, inflation-adj)
# that makes combined(ns + sup) = 0 at sim_end_age.
# Single W is used for both bridge AND post-pres phases.

def _end_total(w0: float) -> float:
    """Return combined portfolio balance at sim_end_age (can be negative = over-drawn)."""
    ns, sup, w = non_super_at_fire, super_at_fire, w0
    for age in range(fire_age_target, sim_end_age):
        if age < pres_age:
            ns  = ns * (1.0 + port_return) - w
            sup = sup * (1.0 + _r2)
        else:
            sup_after = sup * (1.0 + _r2) - w
            if sup_after >= 0:
                sup = sup_after
                ns  = ns * (1.0 + port_return)
            else:
                ns  = ns * (1.0 + port_return) + sup_after  # sup_after < 0
                sup = 0.0
        w *= (1.0 + inf_r)
    return ns + sup

# Bracket: lo leaves money on table; hi bankrupts before sim_end_age
_lo_b, _hi_b = float(bridge_withdrawal) * 0.5, (non_super_at_fire + super_at_fire) * 0.3
for _ in range(80):
    _mid = (_lo_b + _hi_b) / 2.0
    if _end_total(_mid) > 0:
        _lo_b = _mid
    else:
        _hi_b = _mid
deplete_both_w = (_lo_b + _hi_b) / 2.0

ns_B, sup_B = _sim_buckets(non_super_at_fire, super_at_fire, deplete_both_w, deplete_both_w)

# ── Strategy C: Non-Super First ───────────────────────────────────────────────
# Find max bridge withdrawal W that depletes non-super to ~$0 by preservation age,
# then switches entirely to SWR from super for the rest of retirement.
bridge_years = max(pres_age - fire_age_target, 0)
if bridge_years > 0:
    def _ns_at_pres_bridge(w0: float) -> float:
        ns, w = non_super_at_fire, w0
        for _age in range(fire_age_target, pres_age):
            ns = max(ns, 0.0) * (1.0 + port_return) - w
            w *= (1.0 + inf_r)
        return ns
    _lo_c, _hi_c = 0.0, non_super_at_fire * 2.0
    for _ in range(80):
        _mid_c = (_lo_c + _hi_c) / 2.0
        if _ns_at_pres_bridge(_mid_c) > 0:
            _lo_c = _mid_c
        else:
            _hi_c = _mid_c
    strat_C_bridge_w = (_lo_c + _hi_c) / 2.0
else:
    strat_C_bridge_w = swr_post_w

ns_C, sup_C = _sim_buckets(non_super_at_fire, super_at_fire, strat_C_bridge_w, swr_post_w)
total_C = [ns + s for ns, s in zip(ns_C, sup_C)]

# ── Strategy C FIRE age ───────────────────────────────────────────────────────
# Only need non-super to cover the finite bridge period at the desired spend rate,
# NOT an infinite SWR portfolio — so the required amount is much lower → FIRE earlier.
_real_r_C = port_return - inf_r
fire_age_C: int | None = None
for _yr in range(len(proj_df)):
    _age_yr = current_age + _yr
    if _age_yr >= pres_age:
        fire_age_C = _age_yr
        break
    _byr = max(pres_age - _age_yr, 1)
    if abs(_real_r_C) < 1e-9:
        _req_C = float(bridge_withdrawal) * float(_byr)
    else:
        _req_C = float(bridge_withdrawal) * (1.0 - (1.0 + _real_r_C) ** (-_byr)) / _real_r_C
    _ns_yr = float(proj_df[_strat_col].iloc[_yr]) if _strat_col in proj_df.columns else 0.0
    if _ns_yr >= _req_C:
        fire_age_C = _age_yr
        break

total_A = [ns + s for ns, s in zip(ns_A, sup_A)]
total_B = [ns + s for ns, s in zip(ns_B, sup_B)]

# ── Metrics ───────────────────────────────────────────────────────────────────
ma1, ma2, ma3 = st.columns(3)
ma1.metric(
    "🌉 Strat A — Bridge Withdrawal",
    f"${bridge_withdrawal:,.0f}/yr",
    help=f"Your input. Drawn from non-super over the {bridge_years}-year bridge (age {fire_age_target}–{pres_age}).",
)
ma2.metric(
    "♻️ Strat A — Post-Super SWR",
    f"${swr_post_w:,.0f}/yr",
    help=f"{swr*100:.1f}% SWR on ${super_at_pres_unlocked:,.0f} super at age {pres_age}. Super never depletes.",
)
ma3.metric(
    "💥 Strat B — Spend Everything",
    f"${deplete_both_w:,.0f}/yr",
    delta=f"+${deplete_both_w - bridge_withdrawal:,.0f}/yr vs A",
    help=f"Single inflation-adjusted rate that drains BOTH buckets to $0 by age {sim_end_age}.",
)

st.divider()
mc1, mc2, mc3 = st.columns(3)
mc1.metric(
    "🏃 Strat C — Max Bridge Spend",
    f"${strat_C_bridge_w:,.0f}/yr",
    delta=f"+${strat_C_bridge_w - bridge_withdrawal:,.0f}/yr vs A bridge",
    help=(
        f"Spends non-super completely by age {pres_age}, then SWR from super. "
        f"Higher bridge spend, non-super hits $0 exactly at super unlock."
    ),
)
_fire_C_str = f"Age {fire_age_C}" if fire_age_C else "Beyond horizon"
_fire_C_delta = (
    f"{fire_age_target - fire_age_C} yrs earlier" if (fire_age_C and fire_age_C < fire_age_target)
    else ("Same date" if fire_age_C == fire_age_target else "Later")
)
mc2.metric(
    "🎯 Strat C — FIRE Age",
    _fire_C_str,
    delta=_fire_C_delta,
    help=(
        f"With Strat C you only need enough non-super to fund ${bridge_withdrawal:,.0f}/yr "
        f"for the bridge period — much less than an infinite-horizon SWR portfolio. "
        f"Strat A requires age {fire_age_target}."
    ),
)
mc3.metric(
    "📦 Strat C — Post-Super Income",
    f"${swr_post_w:,.0f}/yr",
    help=f"After non-super is spent, ${super_at_pres_unlocked:,.0f} of super funds ${swr_post_w:,.0f}/yr at {swr*100:.1f}% SWR.",
)

# ── Chart ─────────────────────────────────────────────────────────────────────
fig_buckets = go.Figure()

fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=ns_A,
    name="Non-Super — A", fill="tozeroy",
    line=dict(color=COLORS["blue"], width=2),
    fillcolor="rgba(9,132,227,0.12)",
    hovertemplate="Age %{x}<br>Non-Super A: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=total_A,
    name="Total — A (SWR, sustainable)", fill="tonexty",
    line=dict(color=COLORS["purple"], width=2),
    fillcolor="rgba(108,92,231,0.18)",
    hovertemplate="Age %{x}<br>Total A: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=total_B,
    name="Total — B (Deplete Both)",
    line=dict(color=COLORS["orange"], width=2, dash="dash"),
    hovertemplate="Age %{x}<br>Total B: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=ns_C,
    name="Non-Super — C (empties at pres. age)",
    line=dict(color=COLORS["yellow"], width=2, dash="longdash"),
    hovertemplate="Age %{x}<br>Non-Super C: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=total_C,
    name="Total — C (Non-Super First)",
    line=dict(color=COLORS["mint"], width=2, dash="longdash"),
    hovertemplate="Age %{x}<br>Total C: $%{y:,.0f}<extra></extra>",
))

fig_buckets.add_vline(
    x=pres_age, line_color=COLORS["teal"], line_dash="dash", line_width=2,
    annotation_text=f"Super unlocked (age {pres_age})",
    annotation_font_color=COLORS["teal"], annotation_position="top left",
)
fig_buckets.add_vline(
    x=sim_end_age, line_color=COLORS["muted"], line_dash="dot", line_width=1,
    annotation_text=f"Target age {sim_end_age}",
    annotation_font_color=COLORS["muted"], annotation_position="top right",
)
if fire_age_C and fire_age_target <= fire_age_C <= sim_end_age and fire_age_C != fire_age_target:
    fig_buckets.add_vline(
        x=fire_age_C, line_color=COLORS["mint"], line_dash="dot", line_width=2,
        annotation_text=f"🎯 Strat C FIRE (age {fire_age_C})",
        annotation_font_color=COLORS["mint"], annotation_position="top right",
    )

for target, label, clr in [
    (lean_num_adj,   "Lean FIRE",  COLORS["green"]),
    (median_num_adj, "Your FIRE",  COLORS["yellow"]),
    (fat_num_adj,    "Fat FIRE",   COLORS["orange"]),
]:
    fig_buckets.add_hline(
        y=target, line_dash="dot", line_color=clr, line_width=1,
        annotation_text=label, annotation_font_color=clr,
        annotation_position="bottom right",
    )

nsA_dep  = next((sim_ages[i] for i, v in enumerate(ns_A)  if v <= 0), None)
supB_dep = next((sim_ages[i] for i, v in enumerate(sup_B) if v <= 0), None)
nsC_dep  = next((sim_ages[i] for i, v in enumerate(ns_C)  if v <= 0), None)
if nsA_dep:
    fig_buckets.add_vline(x=nsA_dep, line_color=COLORS["red"], line_dash="dot",
                          annotation_text=f"⚠️ A: non-super depletes (age {nsA_dep})",
                          annotation_font_color=COLORS["red"], annotation_position="top right")
if supB_dep and supB_dep < sim_end_age:
    fig_buckets.add_vline(x=supB_dep, line_color=COLORS["pink"], line_dash="longdash",
                          annotation_text=f"B: super→non-super (age {supB_dep})",
                          annotation_font_color=COLORS["pink"], annotation_position="top left")
if nsC_dep:
    fig_buckets.add_vline(x=nsC_dep, line_color=COLORS["yellow"], line_dash="dot",
                          annotation_text=f"C: non-super→super (age {nsC_dep})",
                          annotation_font_color=COLORS["yellow"], annotation_position="bottom right")

fig_buckets.update_layout(
    template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
    xaxis=dict(title="Age", dtick=5),
    yaxis=dict(tickformat="$.3s", title="Portfolio Balance (Real AUD)"),
    hovermode="x unified", height=540,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_buckets, width="stretch")

# Early FIRE banner for Strategy C
if fire_age_C and fire_age_C < fire_age_target:
    _bridge_at_C = max(pres_age - fire_age_C, 0)
    st.info(
        f"⚡ **Strategy C lets you FIRE at age {fire_age_C}** — "
        f"{fire_age_target - fire_age_C} year(s) earlier than Strategy A. "
        f"At age {fire_age_C} your non-super portfolio only needs to fund "
        f"${bridge_withdrawal:,.0f}/yr for {_bridge_at_C} years (until super unlocks at {pres_age}), "
        f"not an infinite-horizon portfolio."
    )

# ── Milestone table ────────────────────────────────────────────────────────────
_milestone_ages: set[int] = {sim_ages[0], sim_end_age}
if pres_age in sim_ages:
    _milestone_ages.add(pres_age)
for _dep in [supB_dep, nsC_dep, nsA_dep]:
    if _dep and _dep in sim_ages:
        _milestone_ages.add(_dep)
if fire_age_C and fire_age_C in sim_ages:
    _milestone_ages.add(fire_age_C)

_rows = []
for i, age in enumerate(sim_ages):
    if age not in _milestone_ages:
        continue
    evts = []
    if i == 0:
        evts.append("🔥 FIRE")
    if age == pres_age:
        evts.append("🔑 Super unlocked")
    if fire_age_C and age == fire_age_C and fire_age_C != fire_age_target:
        evts.append("🎯 Strat C FIRE")
    if supB_dep and age == supB_dep:
        evts.append("🔀 B: super→non-super")
    if nsC_dep and age == nsC_dep:
        evts.append("🔀 C: non-super→super")
    if nsA_dep and age == nsA_dep:
        evts.append("⚠️ A: non-super depletes")
    if age == sim_end_age:
        evts.append(f"🪦 Target age {sim_end_age}")
    _rows.append({
        "Age": age,
        "Event": " | ".join(evts) if evts else "—",
        "Total A":     f"${total_A[i]:,.0f}",
        "Non-Super A": f"${ns_A[i]:,.0f}",
        "Super A":     f"${sup_A[i]:,.0f}",
        "Total B":     f"${total_B[i]:,.0f}",
        "Total C":     f"${total_C[i]:,.0f}",
        "Non-Super C": f"${ns_C[i]:,.0f}",
        "Super C":     f"${sup_C[i]:,.0f}",
    })
if _rows:
    st.dataframe(pd.DataFrame(_rows).set_index("Age"), use_container_width=True)

with st.expander("📖 How to read the Three-Strategy chart"):
    _pres_ns_A = next((ns_A[i] for i, a in enumerate(sim_ages) if a == pres_age), 0) if pres_age in sim_ages else 0
    st.markdown(f"""
All three strategies assume you FIRE at age **{fire_age_target}** and draw non-super first.

| | A ♻️ Sustainable | B 💥 Spend Everything | C 🏃 Non-Super First |
|---|---|---|---|
| **Bridge spend** | ${bridge_withdrawal:,.0f}/yr (your input) | ${deplete_both_w:,.0f}/yr | ${strat_C_bridge_w:,.0f}/yr |
| **Post-super** | ${swr_post_w:,.0f}/yr SWR forever | Both to $0 by {sim_end_age} | ${swr_post_w:,.0f}/yr SWR from super |
| **Non-super at {pres_age}** | ~${_pres_ns_A:,.0f} (keeps compounding) | Depleted | ~$0 (intentionally) |
| **Residual wealth** | Large | $0 | Super only |
| **Could FIRE as early as** | Age {fire_age_target} | Age {fire_age_target} | **Age {fire_age_C if fire_age_C else "?"}** |

**Why Strategy C unlocks earlier FIRE:** Instead of needing a portfolio large enough to fund you
*forever* (SWR), you only need enough to fund **${bridge_withdrawal:,.0f}/yr for {max(pres_age - (fire_age_C or fire_age_target), 0)} years** until super
kicks in. That's a finite annuity — a much smaller number — so you cross the threshold earlier.

| Colour | Meaning |
|--------|---------|
| Blue fill → purple fill | Non-super + total — Strategy A |
| Orange dashed | Total — Strategy B |
| Yellow long-dash | Non-super — Strategy C (depletes at preservation age) |
| Green long-dash | Total — Strategy C |
| Teal vertical | Super preservation age |
| Yellow vertical | Strategy C: non-super→super switch |
""")


st.warning("⚠️ Projections use median historical CAGR. Not a guarantee of future performance.")
