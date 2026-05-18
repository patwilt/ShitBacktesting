"""FIRE Scenarios — Coast/Lean/Fat/Barista crossover analysis."""
from __future__ import annotations
import math
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.colors import COLORS, STRATEGY_COLORS, CHART_LAYOUT
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import run_yearly_projection, dca_crossover_year, salary_crossover_year
from engines.calculation_engine import (
    fire_target, lean_fire_target, fat_fire_target, barista_fire_target,
    coast_fire_target, fire_age, preservation_age,
)
from engines.tax_engine import gross_withdrawal_for_net_spend
from utils import shared_profile as profile

st.set_page_config(page_title="FIRE Scenarios", page_icon="🎯", layout="wide")
profile.init()
st.title("🎯 FIRE Scenarios")
st.caption("Step 6 of your journey: model different paths to financial independence. Compare strategies, DCA rates, and FIRE timelines side by side.")

_pf_monthly_savings     = profile.get("pf_monthly_savings")
_pf_annual_spending     = profile.get("pf_annual_spending")
_pf_investable_surplus  = profile.get("pf_monthly_investable_surplus")
_pf_wants_purchase      = bool(profile.get("pf_wants_to_purchase"))

# Mortgage data — read early so it can influence FIRE crossover calculations
_pf_mortgage_monthly = profile.get("pf_mortgage_monthly")
_pf_loan_term_years  = profile.get("pf_loan_term_years")
_pf_purchase_yrs     = profile.get("pf_purchase_years_from_now")
_pf_loan_amount      = profile.get("pf_mortgage_loan_amount")
_pf_mortgage_rate    = profile.get("pf_mortgage_rate")
_pf_property_value   = profile.get("pf_property_value")

_has_mortgage_data = (
    _pf_wants_purchase
    and _pf_mortgage_monthly is not None
    and _pf_loan_term_years  is not None
    and _pf_loan_amount      is not None
    and _pf_mortgage_rate    is not None
)

# When a property purchase is planned and the full investable surplus is known
# (post-mortgage, post-living-expenses), use that as the DCA default. This gives a
# realistic "how much can I actually invest each month after buying?" starting point.
# Otherwise fall back to the Budget page monthly savings surplus.
if _pf_wants_purchase and _pf_investable_surplus is not None:
    _default_dca = max(int(_pf_investable_surplus), 0)
elif _pf_monthly_savings is not None:
    _default_dca = int(_pf_monthly_savings)
else:
    _default_dca = 1_500
_default_spending    = int(_pf_annual_spending) if _pf_annual_spending is not None else 80_000
_default_salary_growth = float(profile.get("pf_salary_growth") or 3.0)

# When partnered, default the salary input to the household total so DCA-as-%
# and salary-crossover projections match real household earnings. The user can
# still override locally without touching the profile.
_partnered      = profile.is_partnered()
_default_salary = profile.household_gross_income() if _partnered else profile.get("pf_gross_income")
_default_super  = profile.household_super_balance() if _partnered else profile.get("pf_super_balance")

with st.sidebar:
    profile.sidebar_summary()
    if profile.is_set():
        st.caption("✅ Pre-filled from profile. Adjust locally here.")
    st.header("💰 Inputs")
    current_age   = st.number_input("Current Age", min_value=18, max_value=80, step=1, value=profile.get("pf_age"))
    salary_label  = "Household Salary (AUD)" if _partnered else "Annual Salary (AUD)"
    salary        = st.number_input(salary_label, min_value=0,
                                    value=int(_default_salary), step=5_000,
                                    help=("Combined household gross income (you + partner). "
                                          "Tax in this projection is approximated; for accurate "
                                          "per-partner tax breakdown see the Budget page.") if _partnered
                                    else "Pre-filled from your profile.")
    salary_growth = st.number_input("Salary Growth (%/yr)", min_value=0.0,
                                    value=_default_salary_growth, step=0.5,
                                    help="Pre-filled from your profile. Set it once on the Home page.")
    portfolio     = st.number_input("Starting Portfolio", min_value=0, step=5_000, value=profile.get("pf_portfolio"))
    dca_method    = st.radio("DCA Method", ["Fixed Monthly Amount", "Percentage of Salary"])
    if dca_method == "Fixed Monthly Amount":
        dca_value = st.number_input("Monthly DCA (AUD)", min_value=0, value=_default_dca, step=100,
                                    help="Monthly investment amount. Pre-filled from your Budget page monthly savings surplus.")
    else:
        dca_value = st.number_input("Salary %", min_value=0.0, max_value=100.0, value=20.0)
    if _pf_wants_purchase and _pf_investable_surplus is not None:
        st.caption(
            f"💡 From Home Deposit plan: **${max(int(_pf_investable_surplus), 0):,}/mo** "
            f"investable surplus (after mortgage + living expenses) → used as DCA."
        )
    elif _pf_monthly_savings is not None:
        st.caption(f"💡 From Budget: **${int(_pf_monthly_savings):,}/mo** surplus → used as DCA.")
    dca_grows     = st.checkbox("DCA grows with salary", value=True)
    stop_at_coast = st.toggle("Stop DCA at Coast Year", value=False)
    st.divider()
    st.header("📉 Spending Targets")
    # Lean/fat default relative to budget spending if available, else hard-coded
    _lean_default = int(_pf_annual_spending * 0.65) if _pf_annual_spending is not None else 40_000
    _fat_default  = int(_pf_annual_spending * 1.50) if _pf_annual_spending is not None else 120_000
    lean_spending    = st.number_input("Lean FIRE Spending/yr",   min_value=0, value=_lean_default, step=5_000,
                                       help="Frugal retirement budget. Defaults to 65% of your Budget page annual spending.")
    median_spending  = st.number_input("Your FIRE Spending/yr",   min_value=0,
                                       value=_default_spending, step=5_000,
                                       help="Your personal retirement spending target. Pre-filled from your Budget page annual spending.")
    fat_spending     = st.number_input("Fat FIRE Spending/yr",    min_value=0, value=_fat_default, step=5_000,
                                       help="Comfortable retirement budget. Defaults to 150% of your Budget page annual spending.")
    if _pf_annual_spending is not None:
        st.caption(f"💡 From Budget: **${int(_pf_annual_spending):,}/yr** spending → used as Your FIRE target.")
    barista_income   = st.number_input("Barista Part-Time Income", min_value=0, value=20_000, step=2_000)
    barista_spending = st.number_input("Barista Total Spending",   min_value=0, value=60_000, step=5_000)
    swr          = st.slider("SWR (%)", 2.0, 6.0, min(6.0, max(2.0, float(profile.get("pf_swr")))), 0.25) / 100.0
    st.divider()
    inflation_rate = st.slider("Inflation (%)", 0.0, 10.0, min(10.0, max(0.0, float(profile.get("pf_inflation")))), 0.1)
    horizon_years  = st.slider("Horizon (Years)", 5, 60, 35)
    st.divider()
    st.header("📊 Return Assumption")
    return_percentile = st.select_slider(
        "Historical Return Percentile",
        options=[10, 25, 50, 75, 90],
        value=50,
        help=(
            "Selects which percentile of historical rolling-window CAGRs to use as the "
            "forward return for each strategy. "
            "50th = median (half of historical periods did better, half worse). "
            "25th = conservative (only 1-in-4 historical periods were this poor). "
            "Use 25th–50th for planning; 75th–90th to stress-test the upside."
        ),
    )
    if return_percentile < 50:
        st.caption(f"⚠️ Conservative view: {return_percentile}th percentile — only {return_percentile}% of historical windows were worse than this.")
    elif return_percentile == 50:
        st.caption("Base case: median historical return. ~50% of historical windows beat this.")
    st.divider()
    st.header("🏦 Superannuation")
    birth_year   = st.number_input("Birth Year", min_value=1940, max_value=2010, step=1, value=profile.get("pf_birth_year"))
    _default_pres = preservation_age(birth_year)
    pres_age      = st.number_input(
        "Super Access Age",
        min_value=55, max_value=75, value=_default_pres, step=1,
        help=f"Auto-set to {_default_pres} from your birth year. Override here if the law changes.",
    )
    super_label   = "Household Super Balance (AUD)" if _partnered else "Current Super Balance (AUD)"
    super_balance = st.number_input(super_label, min_value=0,
                                    value=int(_default_super), step=5_000,
                                    help=("Combined super across both partners. Australian super "
                                          "accounts are individual but for FIRE planning the "
                                          "household total drives the bridge-period maths.") if _partnered
                                    else None)
    super_return  = st.slider("Super Annual Return (%, nominal)", 3.0, 12.0, 7.0, 0.5,
                              help="Nominal return before inflation. App converts to real return internally.")
    sgc_rate      = st.slider(
        "Super Contribution Rate (%)", 8.0, 30.0, 12.0, 0.5,
        help="Employer SGC is 12% from 1 July 2025. Add voluntary contributions here too.",
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
    return_percentile=return_percentile,
)

lean_num    = lean_fire_target(lean_spending, swr)
fat_num     = fat_fire_target(fat_spending, swr)
barista_num = barista_fire_target(barista_spending, barista_income, swr)

# ── Mortgage balance helper (available to both metrics and chart) ─────────────
def _real_mort_balance(yr: int) -> float:
    """Remaining mortgage in real (today's) AUD at projection year yr.

    Returns 0 when there is no mortgage data, before purchase, or after payoff.
    The nominal balance is deflated by cumulative inflation so it is comparable
    with the portfolio values in proj_df (which are already in real AUD).
    """
    if not _has_mortgage_data:
        return 0.0
    _p_yr  = int(_pf_purchase_yrs) if _pf_purchase_yrs is not None else 0
    _po_yr = _p_yr + int(_pf_loan_term_years)
    if yr < _p_yr or yr >= _po_yr:
        return 0.0
    months  = (yr - _p_yr) * 12
    L       = float(_pf_loan_amount)
    r       = float(_pf_mortgage_rate) / 12.0
    pmt     = float(_pf_mortgage_monthly)
    if r < 1e-10:
        bal_nom = max(L - months * pmt, 0.0)
    else:
        fac     = (1.0 + r) ** months
        bal_nom = max(L * fac - pmt * (fac - 1.0) / r, 0.0)
    inf_ann = float(inflation_rate) / 100.0
    return bal_nom / (1.0 + inf_ann) ** yr if yr > 0 else bal_nom

bridge_cols = st.columns(4)

# Tax-adjusted gross withdrawals needed to fund each target after tax
lean_gross    = gross_withdrawal_for_net_spend(lean_spending)
median_gross  = gross_withdrawal_for_net_spend(median_spending)
fat_gross     = gross_withdrawal_for_net_spend(fat_spending)
# Barista FIRE: portfolio withdrawal is taxed on top of existing part-time income
# (income-stacking effect - the part-time income consumes low-bracket space first)
barista_net_draw = max(barista_spending - barista_income, 0)
barista_gross = gross_withdrawal_for_net_spend(barista_net_draw, existing_income=barista_income)

lean_num_adj    = lean_gross    / swr
median_num_adj  = median_gross  / swr
fat_num_adj     = fat_gross     / swr
barista_num_adj = barista_gross / swr

# Projected age to reach each FIRE target - find best (earliest) strategy
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

# Mortgage-adjusted crossover: portfolio must also cover the remaining loan balance.
# The effective target at year Y = FIRE_number + real_mortgage_balance(Y).
# This threshold decreases year-by-year and hits the standard FIRE_number once paid off.
def _best_mort_adj_fire_age(target: float) -> tuple[int | None, str | None]:
    candidates = []
    for s in selected:
        col = f"{s}_Total"
        if col not in proj_df.columns:
            continue
        for yr, port in enumerate(proj_df[col]):
            if float(port) >= target + _real_mort_balance(yr):
                candidates.append((current_age + yr, s))
                break
    if not candidates:
        return None, None
    return min(candidates, key=lambda x: x[0])

if _has_mortgage_data:
    median_age_adj, median_strat_adj = _best_mort_adj_fire_age(median_num_adj)
    lean_age_adj,   _                = _best_mort_adj_fire_age(lean_num_adj)
    fat_age_adj,    _                = _best_mort_adj_fire_age(fat_num_adj)
else:
    median_age_adj = median_strat_adj = lean_age_adj = fat_age_adj = None

t_col1, t_col2, t_col3, t_col4 = st.columns(4)
with t_col1:
    lean_delta = f"Age {lean_age} · ${lean_gross:,.0f}/yr gross" if lean_age else "Not in horizon"
    st.metric("Lean FIRE (Tax-Adjusted)", f"${lean_num_adj:,.0f}",
              delta=lean_delta, delta_color="normal" if lean_age else "off",
              help=f"Portfolio to fund ${lean_spending:,}/yr after-tax at {swr*100:.1f}% SWR. "
                   f"Earliest via: {lean_strat or 'N/A'}")
with t_col2:
    med_delta = f"Age {median_age} · ${median_gross:,.0f}/yr gross" if median_age else "Not in horizon"
    st.metric("Your FIRE (Tax-Adjusted)", f"${median_num_adj:,.0f}",
              delta=med_delta, delta_color="normal" if median_age else "off",
              help=f"Portfolio to fund ${median_spending:,}/yr after-tax at {swr*100:.1f}% SWR. "
                   f"Earliest via: {median_strat or 'N/A'}")
with t_col3:
    fat_delta = f"Age {fat_age} · ${fat_gross:,.0f}/yr gross" if fat_age else "Not in horizon"
    st.metric("Fat FIRE (Tax-Adjusted)", f"${fat_num_adj:,.0f}",
              delta=fat_delta, delta_color="normal" if fat_age else "off",
              help=f"Portfolio to fund ${fat_spending:,}/yr after-tax at {swr*100:.1f}% SWR. "
                   f"Earliest via: {fat_strat or 'N/A'}")
with t_col4:
    bar_delta = f"Age {barista_age} · ${barista_gross:,.0f}/yr gross" if barista_age else "Not in horizon"
    st.metric("Barista FIRE (Tax-Adjusted)", f"${barista_num_adj:,.0f}",
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

if _has_mortgage_data:
    _p_yr  = int(_pf_purchase_yrs) if _pf_purchase_yrs is not None else 0
    _po_yr = _p_yr + int(_pf_loan_term_years)

    # Balance remaining at each candidate FIRE age
    _bal_at_median = _real_mort_balance(median_age - current_age) if median_age else 0
    _bal_at_lean   = _real_mort_balance(lean_age   - current_age) if lean_age   else 0
    _bal_at_fat    = _real_mort_balance(fat_age    - current_age) if fat_age    else 0

    _delay_med = (median_age_adj - median_age) if (median_age_adj and median_age) else None
    _delay_lean = (lean_age_adj  - lean_age)   if (lean_age_adj   and lean_age)   else None
    _delay_fat  = (fat_age_adj   - fat_age)    if (fat_age_adj    and fat_age)    else None

    adj_a, adj_b, adj_c = st.columns(3)
    adj_a.metric(
        "Lean FIRE (Mortgage-Adjusted)",
        f"Age {lean_age_adj}" if lean_age_adj else "Not in horizon",
        delta=(f"+{_delay_lean} yr vs unadjusted" if (_delay_lean and _delay_lean > 0)
               else ("No delay — mortgage paid before Lean FIRE" if _delay_lean == 0 else None)),
        delta_color="inverse" if (_delay_lean and _delay_lean > 0) else "normal",
        help=(f"Mortgage adds ${_bal_at_lean:,.0f} to the required portfolio at unadjusted Lean FIRE age ({lean_age})."
              if lean_age else ""),
    )
    adj_b.metric(
        "Your FIRE (Mortgage-Adjusted)",
        f"Age {median_age_adj}" if median_age_adj else "Not in horizon",
        delta=(f"+{_delay_med} yr vs unadjusted" if (_delay_med and _delay_med > 0)
               else ("No delay — mortgage paid before FIRE" if _delay_med == 0 else None)),
        delta_color="inverse" if (_delay_med and _delay_med > 0) else "normal",
        help=(f"At unadjusted FIRE age ({median_age}), ${_bal_at_median:,.0f} mortgage balance "
              f"still outstanding. Portfolio must be ${median_num_adj + _bal_at_median:,.0f} "
              f"(= ${median_num_adj:,.0f} FIRE number + ${_bal_at_median:,.0f} mortgage) "
              f"before you can truly retire."
              if median_age else ""),
    )
    adj_c.metric(
        "Fat FIRE (Mortgage-Adjusted)",
        f"Age {fat_age_adj}" if fat_age_adj else "Not in horizon",
        delta=(f"+{_delay_fat} yr vs unadjusted" if (_delay_fat and _delay_fat > 0)
               else ("No delay — mortgage paid before Fat FIRE" if _delay_fat == 0 else None)),
        delta_color="inverse" if (_delay_fat and _delay_fat > 0) else "normal",
        help=(f"Mortgage adds ${_bal_at_fat:,.0f} to the required portfolio at unadjusted Fat FIRE age ({fat_age})."
              if fat_age else ""),
    )
    st.caption(
        f"🏠 **How mortgage-adjusted FIRE works:** your portfolio must cover **both** the SWR-based "
        f"spending number and the remaining loan balance at the point of retirement. "
        f"The required threshold decreases each year as the mortgage is paid down, "
        f"reaching the standard FIRE number at mortgage payoff (age {current_age + _po_yr})."
    )

st.divider()
st.subheader("The Double Crossover")
fig = go.Figure()
ages = proj_df["Year"] + current_age

fig.add_trace(go.Scatter(x=ages, y=proj_df["Salary"], name="Annual Salary",
                          line=dict(color=COLORS["yellow"], width=3),
                          hovertemplate="Salary: $%{y:,.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=ages, y=proj_df["Yearly_DCA"], name="Annual DCA",
                          line=dict(color=COLORS["soft_yellow"], width=2, dash="dot"),
                          hovertemplate="DCA: $%{y:,.0f}<extra></extra>"))

# Mortgage-adjusted FIRE target: a line that starts at FIRE_number + full_loan_balance
# and decreases year-by-year to FIRE_number once the mortgage is paid off.
if _has_mortgage_data:
    _adj_targets = [median_num_adj + _real_mort_balance(yr) for yr in range(len(proj_df))]
    fig.add_trace(go.Scatter(
        x=ages, y=_adj_targets,
        name="Mortgage-Adjusted FIRE Target",
        line=dict(color=COLORS["red"], width=2, dash="dot"),
        hovertemplate="Mortgage-Adj. Target: $%{y:,.0f}<extra></extra>",
    ))

for i, strat in enumerate(selected):
    color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
    profit = proj_df[f"{strat}_Yearly_Profit"]
    fig.add_trace(go.Scatter(x=ages, y=profit, name=f"{strat} Annual Profit",
                              line=dict(color=color, width=2),
                              hovertemplate=f"{strat}: $%{{y:,.0f}}<extra></extra>"))
    dca_yr = dca_crossover_year(proj_df, strat)
    sal_yr = salary_crossover_year(proj_df, strat)

    # Stagger annotation offsets per strategy so multiple crossovers in the same
    # area don't collide. Alternate side and step the vertical offset.
    side    = -1 if (i % 2 == 0) else 1
    ax_step = side * (40 + (i // 2) * 30)
    ay_step = -60 - (i // 2) * 35

    # Anchor each annotation to the profit line (which is what the crossover is
    # actually about), not the DCA/Salary line — that way the arrow points at
    # the strategy's curve regardless of whether DCA stops at coast.
    if dca_yr and dca_yr < len(proj_df):
        fig.add_annotation(
            x=dca_yr + current_age,
            y=float(profit.iloc[dca_yr]),
            text=f"Contrib X-over {strat[:8]} yr {dca_yr}",
            showarrow=True, arrowhead=2,
            ax=-abs(ax_step), ay=ay_step,
            bgcolor=COLORS["blue"], font=dict(color=COLORS["dark"], size=10),
        )
    if sal_yr and sal_yr < len(proj_df):
        fig.add_annotation(
            x=sal_yr + current_age,
            y=float(profit.iloc[sal_yr]),
            text=f"FI {strat[:8]} yr {sal_yr}",
            showarrow=True, arrowhead=1,
            ax=abs(ax_step), ay=ay_step,
            bgcolor=color, font=dict(color=COLORS["dark"], size=10),
        )

# Super preservation age vertical line
if pres_age <= current_age + horizon_years:
    fig.add_vline(x=pres_age, line_color=COLORS["purple"], line_dash="dot", line_width=2,
                  annotation_text=f"Super access age {pres_age}",
                  annotation_font_color=COLORS["purple"],
                  annotation_position="top right")

fig.update_layout(**CHART_LAYOUT,
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
| **Annual Profit > Annual DCA** (Contribution Crossover) | Your portfolio's yearly growth exceeds what you're contributing. A momentum milestone — note this is not the same as Coast FIRE (which requires the current balance to compound to your full FIRE number by retirement with no further contributions). |
| **Annual Profit > Annual Salary** (FI point) | Your portfolio generates more each year than your job does. You are financially independent. |

**Reading the lines:**
- **Yellow**: your gross salary, growing with salary growth rate
- **Dotted yellow**: your annual DCA contribution
- **Coloured lines**: each strategy's annual investment profit (growth minus contributions)

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
            st.metric(m["Strategy"], f"Age {m['FI Age']}", f"Year {m['FI Year']}")
    st.success(f"🎉 Earliest FI: **{best['Strategy']}** at age **{best['FI Age']}**")

st.divider()
st.subheader("Super Access Strategy")
sc1, sc2, sc3 = st.columns(3)
sc1.metric("Super Preservation Age", str(pres_age),
           help="Age you can first access your superannuation (based on birth year)")

# Project super balance to preservation age:
# each year: grow existing balance, add net-of-tax employer/voluntary contributions
# salary grows at salary_growth rate; SGC contributions taxed at 15% flat
years_to_pres  = max(pres_age - current_age, 0)
_r             = super_return / 100.0
_sg            = salary_growth / 100.0
_sgc           = sgc_rate / 100.0
_super_bal     = float(super_balance)
_current_sal   = float(salary)
_annual_contribs_total = 0.0

_r_acc = _r * (1.0 - 0.15)  # effective nominal return after 15% super earnings tax
for _ in range(years_to_pres):
    net_contrib       = _current_sal * _sgc * (1.0 - 0.15)   # 15% contributions tax
    _super_bal        = _super_bal * (1.0 + _r_acc) + net_contrib
    _annual_contribs_total += net_contrib
    _current_sal     *= (1.0 + _sg)

# Deflate nominal accumulation to real (today's purchasing power)
_inf_deflator = (1.0 + inflation_rate / 100.0) ** years_to_pres if years_to_pres > 0 else 1.0
super_at_pres       = _super_bal / _inf_deflator
avg_annual_contrib  = (_annual_contribs_total / years_to_pres / _inf_deflator) if years_to_pres > 0 else 0.0

sc2.metric(
    f"Projected Super at Age {pres_age} (Real)", f"${super_at_pres:,.0f}",
    help=(
        f"Starting balance: ${super_balance:,}  ·  "
        f"Avg annual contribution (net of 15% tax, real): ~${avg_annual_contrib:,.0f}  ·  "
        f"Nominal return: {super_return}%/yr  →  after 15% earnings tax: {_r_acc*100:.2f}%/yr  ·  "
        f"Inflation: {inflation_rate}%/yr  ·  "
        f"Real return (after earnings tax): {((1+_r_acc)/(1+inflation_rate/100)-1)*100:.2f}%/yr  ·  "
        f"Value in today's (real) AUD over {years_to_pres} years"
    ),
)

super_swr_income = super_at_pres * swr
sc3.metric(
    "Super SWR Income (Tax-Free)", f"${super_swr_income:,.0f}/yr",
    help=(
        f"Annual income from super at {swr*100:.1f}% SWR from age {pres_age}. "
        f"Super withdrawals are tax-free in pension phase (after age 60). "
        f"This ${super_swr_income:,.0f}/yr is directly comparable to after-tax spending — "
        f"it is NOT a gross amount requiring further tax deduction. "
        f"In contrast, the FIRE numbers above show the gross portfolio withdrawal needed to yield "
        f"a target after-tax spend from a non-super portfolio."
    ),
)

# Bridge period: years between earliest FI and super access
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
                   f"Super is immediately accessible, contributing ~${super_swr_income:,.0f}/yr to your income.")

# ── Two-bucket drawdown chart ─────────────────────────────────────────────────
st.divider()
st.subheader("Two-Bucket Drawdown Projection")

# Determine FIRE age and median portfolio return
fire_age_target = median_age if median_age else (current_age + horizon_years)
years_to_fire   = max(fire_age_target - current_age, 0)
port_return     = float(data.cagr_df[median_strat].median()) if (median_strat and median_strat in data.cagr_df.columns) else 0.07

# Non-super balance at FIRE age (from projection)
_strat_col = f"{median_strat}_Total" if (median_strat and f"{median_strat}_Total" in proj_df.columns) else f"{selected[0]}_Total"
non_super_at_fire = float(proj_df[_strat_col].iloc[min(years_to_fire, len(proj_df) - 1)])

# Super balance at FIRE age (accumulate with SGC contributions up to FIRE age in nominal,
# then deflate to real/today's AUD so it's comparable with non_super_at_fire from proj_df)
_r2, _sg2, _sgc2 = super_return / 100.0, salary_growth / 100.0, sgc_rate / 100.0
_r2_acc = _r2 * (1.0 - 0.15)  # after 15% super earnings tax (accumulation phase)
_sb2, _sal2 = float(super_balance), float(salary)
for _ in range(years_to_fire):
    _sb2  = _sb2 * (1.0 + _r2_acc) + _sal2 * _sgc2 * 0.85
    _sal2 *= (1.0 + _sg2)
# Deflate nominal accumulation → real (today's purchasing power)
super_at_fire = _sb2 / (1.0 + inflation_rate / 100.0) ** years_to_fire if years_to_fire > 0 else _sb2

# ── Controls ──────────────────────────────────────────────────────────────────
ctrl1, ctrl2 = st.columns([2, 1])
with ctrl1:
    sim_end_age = st.slider("Project to Age (death)", min_value=fire_age_target + 5, max_value=100, value=90, step=1)
with ctrl2:
    bridge_withdrawal = st.number_input(
        "Strat A: Bridge Withdrawal (AUD/yr)",
        min_value=0, value=int(median_gross), step=1_000,
        help="Strategy A only: annual withdrawal from non-super during bridge. Strategy B computes its own optimal rate.",
    )

inf_r = inflation_rate / 100.0
# Real returns: (1 + nominal) / (1 + inflation) - 1
# All bucket simulations use real returns so balances stay in today's AUD.
real_port_r    = (1.0 + port_return) / (1.0 + inf_r) - 1.0
real_sup_r     = (1.0 + _r2) / (1.0 + inf_r) - 1.0       # pension phase: 0% earnings tax
real_sup_r_acc = (1.0 + _r2_acc) / (1.0 + inf_r) - 1.0   # accumulation phase: 15% earnings tax
sim_ages = list(range(fire_age_target, sim_end_age + 1))

# ── Helper: simulate two-bucket drawdown with a fixed initial withdrawal ──────
def _sim_buckets(
    ns0: float, sup0: float,
    w0_bridge: float, w0_post: float,
) -> tuple[list[float], list[float]]:
    """
    Simulate from fire_age_target to sim_end_age using REAL returns.
    All values are in today's (real) AUD; withdrawals are constant in real terms.
    Bridge phase (before pres_age): draw w_bridge from non-super; super compounds.
    Post-pres phase: draw w_post from super first; overflow to non-super if super empty.
    """
    ns, sup = ns0, sup0
    w_b, w_p = w0_bridge, w0_post
    ns_out, sup_out = [], []
    for age in sim_ages:
        ns_out.append(max(ns, 0.0))
        sup_out.append(max(sup, 0.0))
        if age < pres_age:
            # Accumulation phase: super still subject to 15% earnings tax
            ns  = max(ns, 0.0) * (1.0 + real_port_r) - w_b
            sup = max(sup, 0.0) * (1.0 + real_sup_r_acc)
        else:
            # Pension phase: super earnings are tax-free
            draw = w_p
            sup_growth = max(sup, 0.0) * (1.0 + real_sup_r)
            if sup_growth >= draw:
                sup = sup_growth - draw
                ns  = max(ns, 0.0) * (1.0 + real_port_r)
            else:
                leftover = draw - sup_growth
                sup = 0.0
                ns  = max(ns, 0.0) * (1.0 + real_port_r) - leftover
    return ns_out, sup_out


# ── Helper: robust max-withdrawal binary search ──────────────────────────────
def _solve_max_withdrawal(
    end_balance_fn,
    initial_hi: float,
    *,
    max_hi: float = 1e12,
    iterations: int = 60,
) -> float:
    """
    Find the maximum withdrawal w such that end_balance_fn(w) >= 0.

    Uses doubling-then-binary-search so the answer is correct even when the
    caller's initial upper bound isn't large enough to actually bankrupt the
    bucket. A fixed upper bound under-spends silently; this helper guarantees
    the search interval brackets the root.

    Args:
        end_balance_fn: callable f(w) -> final balance (positive means w too low,
                        negative means w too high).
        initial_hi:     starting guess for the upper bound; will be doubled
                        until the bucket actually bankrupts.
        max_hi:         safety ceiling to prevent infinite expansion.
        iterations:     bisection rounds (60 gives ~1e-18 relative precision).
    """
    # If even no withdrawal leaves a deficit, the bucket can't sustain anything.
    if end_balance_fn(0.0) < 0:
        return 0.0
    lo = 0.0
    hi = max(float(initial_hi), 1.0)
    while end_balance_fn(hi) > 0 and hi < max_hi:
        hi *= 2.0
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if end_balance_fn(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# Strategy A: SWR - draw SWR% of super post-preservation; non-super compounds
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

# Properly compute super at pres_age in real terms (compound without contributions post-FIRE,
# using real super return; non-super uses real portfolio return)
_ns_p, _sup_p = non_super_at_fire, super_at_fire
for _age in range(fire_age_target, pres_age):
    _ns_p  = max(_ns_p, 0.0) * (1.0 + real_port_r) - float(bridge_withdrawal)
    # Bridge period: super still in accumulation phase → 15% earnings tax applies
    _sup_p = max(_sup_p, 0.0) * (1.0 + real_sup_r_acc)
super_at_pres_unlocked = max(_sup_p, 0.0)
swr_post_w = super_at_pres_unlocked * swr

ns_A, sup_A = _sim_buckets(non_super_at_fire, super_at_fire, float(bridge_withdrawal), swr_post_w)

# ── Strategy B: Deplete BOTH to $0 by sim_end_age ────────────────────────────
# Binary-search for the uniform withdrawal W (applied from FIRE age, inflation-adj)
# that makes combined(ns + sup) = 0 at sim_end_age.
# Single W is used for both bridge AND post-pres phases.

def _end_total(w0: float) -> float:
    """Return combined portfolio balance at sim_end_age using real returns (can be negative)."""
    ns, sup, w = non_super_at_fire, super_at_fire, w0
    for age in range(fire_age_target, sim_end_age):
        if age < pres_age:
            # Accumulation phase: 15% earnings tax on super growth
            ns  = ns * (1.0 + real_port_r) - w
            sup = sup * (1.0 + real_sup_r_acc)
        else:
            # Pension phase: tax-free super earnings
            sup_after = sup * (1.0 + real_sup_r) - w
            if sup_after >= 0:
                sup = sup_after
                ns  = ns * (1.0 + real_port_r)
            else:
                ns  = ns * (1.0 + real_port_r) + sup_after
                sup = 0.0
    return ns + sup

# Solve for the constant real withdrawal that depletes the combined bucket by
# sim_end_age. Doubling search guarantees the bracket actually contains the root
# even for short sim windows or fat-FIRE starting balances.
deplete_both_w = _solve_max_withdrawal(
    _end_total,
    initial_hi=(non_super_at_fire + super_at_fire) * 0.3,
)

ns_B, sup_B = _sim_buckets(non_super_at_fire, super_at_fire, deplete_both_w, deplete_both_w)

# ── Strategy C FIRE age (computed FIRST so starting values reflect early FIRE) ──
# Only need non-super to cover the finite bridge period, not an infinite SWR
# portfolio, so the required amount is much lower → potentially FIRE earlier.
fire_age_C: int | None = None
for _yr in range(len(proj_df)):
    _age_yr = current_age + _yr
    if _age_yr >= pres_age:
        fire_age_C = _age_yr
        break
    _byr = max(pres_age - _age_yr, 1)
    if abs(real_port_r) < 1e-9:
        _req_C = float(bridge_withdrawal) * float(_byr)
    else:
        _req_C = float(bridge_withdrawal) * (1.0 - (1.0 + real_port_r) ** (-_byr)) / real_port_r
    _ns_yr = float(proj_df[_strat_col].iloc[_yr]) if _strat_col in proj_df.columns else 0.0
    if _ns_yr >= _req_C:
        fire_age_C = _age_yr
        break

# bridge_years is for Strategy A's metric label (A always fires at fire_age_target)
bridge_years = max(pres_age - fire_age_target, 0)

# Strategy C: Non-Super First - correct starting values ─────────────────────
# CRITICAL FIX: if fire_age_C < fire_age_target, salary and SGC contributions
# STOP at fire_age_C, not fire_age_target. Super accumulates fewer years of SGC
# contributions → lower super balance at preservation age.
fire_age_C_start = (fire_age_C if (fire_age_C and fire_age_C < fire_age_target) else fire_age_target)
years_to_fire_C  = max(fire_age_C_start - current_age, 0)

if fire_age_C_start < fire_age_target:
    # Non-super: from proj_df at the earlier FIRE year (already in real AUD)
    non_super_at_fire_C = float(proj_df[_strat_col].iloc[min(years_to_fire_C, len(proj_df) - 1)])
    # Super: accumulated with SGC only up to fire_age_C_start, then deflated to real
    _sb_C, _sal_C = float(super_balance), float(salary)
    for _ in range(years_to_fire_C):
        _sb_C = _sb_C * (1.0 + _r2_acc) + _sal_C * _sgc2 * 0.85
        _sal_C *= (1.0 + _sg2)
    super_at_fire_C = _sb_C / (1.0 + inflation_rate / 100.0) ** years_to_fire_C if years_to_fire_C > 0 else _sb_C
    sim_ages_C = list(range(fire_age_C_start, sim_end_age + 1))
else:
    non_super_at_fire_C = non_super_at_fire
    super_at_fire_C     = super_at_fire
    sim_ages_C          = sim_ages

# Max bridge withdrawal that depletes non_super_at_fire_C to ~$0 by pres_age
bridge_years_C = max(pres_age - fire_age_C_start, 0)
if bridge_years_C > 0:
    def _ns_at_pres_bridge_C(w0: float) -> float:
        ns = non_super_at_fire_C
        for _age in range(fire_age_C_start, pres_age):
            ns = max(ns, 0.0) * (1.0 + real_port_r) - w0
        return ns
    strat_C_bridge_w = _solve_max_withdrawal(
        _ns_at_pres_bridge_C,
        initial_hi=non_super_at_fire_C,
    )
else:
    strat_C_bridge_w = swr_post_w

# Super at pres_age for C: grows WITHOUT contributions after fire_age_C_start
# Bridge is still accumulation phase (pre-preservation) → 15% earnings tax
super_at_pres_C = super_at_fire_C * (1.0 + real_sup_r_acc) ** bridge_years_C

# Post-pres for C: deplete super_at_pres_C to $0 by sim_end_age
_post_yrs_C = max(sim_end_age - pres_age, 1)

def _sup_end_C(w_post: float) -> float:
    sup = super_at_pres_C
    for _ in range(_post_yrs_C):
        sup = max(sup, 0.0) * (1.0 + real_sup_r) - w_post
    return sup

strat_C_post_w = _solve_max_withdrawal(
    _sup_end_C,
    initial_hi=max(super_at_pres_C * 0.5, 1.0),
)

# Simulate C over sim_ages_C (may start earlier than fire_age_target)
def _sim_C(ns0: float, sup0: float, w_bridge: float, w_post: float) -> tuple[list[float], list[float]]:
    ns, sup = ns0, sup0
    ns_out, sup_out = [], []
    for age in sim_ages_C:
        ns_out.append(max(ns, 0.0))
        sup_out.append(max(sup, 0.0))
        if age < pres_age:
            # Accumulation phase: 15% earnings tax
            ns  = max(ns, 0.0) * (1.0 + real_port_r) - w_bridge
            sup = max(sup, 0.0) * (1.0 + real_sup_r_acc)
        else:
            # Pension phase: tax-free earnings
            sup_growth = max(sup, 0.0) * (1.0 + real_sup_r)
            if sup_growth >= w_post:
                sup = sup_growth - w_post
                ns  = max(ns, 0.0) * (1.0 + real_port_r)
            else:
                sup = 0.0
                ns  = max(ns, 0.0) * (1.0 + real_port_r) - (w_post - sup_growth)
    return ns_out, sup_out

ns_C, sup_C = _sim_C(non_super_at_fire_C, super_at_fire_C, strat_C_bridge_w, strat_C_post_w)
total_C = [ns + s for ns, s in zip(ns_C, sup_C)]

total_A = [ns + s for ns, s in zip(ns_A, sup_A)]
total_B = [ns + s for ns, s in zip(ns_B, sup_B)]

# ── Metrics ───────────────────────────────────────────────────────────────────
ma1, ma2, ma3 = st.columns(3)
ma1.metric(
    "Strategy A: Bridge Withdrawal",
    f"${bridge_withdrawal:,.0f}/yr",
    help=f"Your input. Drawn from non-super over the {bridge_years}-year bridge (age {fire_age_target}–{pres_age}).",
)
ma2.metric(
    "Strategy A: Post-Super SWR",
    f"${swr_post_w:,.0f}/yr",
    help=f"{swr*100:.1f}% SWR on ${super_at_pres_unlocked:,.0f} super at age {pres_age}. Super never depletes.",
)
ma3.metric(
    "Strategy B: Spend Everything",
    f"${deplete_both_w:,.0f}/yr",
    delta=f"+${deplete_both_w - bridge_withdrawal:,.0f}/yr vs A",
    help=f"Single inflation-adjusted rate that drains BOTH buckets to $0 by age {sim_end_age}.",
)

st.divider()
mc1, mc2, mc3 = st.columns(3)
mc1.metric(
    "Strategy C: Max Bridge Spend",
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
    "Strategy C: FIRE Age",
    _fire_C_str,
    delta=_fire_C_delta,
    help=(
        f"With Strategy C you only need enough non-super to fund ${bridge_withdrawal:,.0f}/yr "
        f"for the bridge period, much less than an infinite-horizon SWR portfolio. "
        f"Strategy A requires age {fire_age_target}."
    ),
)
mc3.metric(
    "Strategy C: Post-Super Income",
    f"${strat_C_post_w:,.0f}/yr",
    help=(
        f"You FIRE at age {fire_age_C_start}, so SGC contributions stop then. "
        f"Super grows without contributions from age {fire_age_C_start} → {pres_age} "
        f"(real balance: ${super_at_pres_C:,.0f}), then drawn at ${strat_C_post_w:,.0f}/yr "
        f"to hit $0 by age {sim_end_age}. "
        f"Strategy A's sustainable SWR: ${swr_post_w:,.0f}/yr."
    ),
)

# ── Chart ─────────────────────────────────────────────────────────────────────
# Log scale can't plot 0, clamp depleted values to $1 so the line stays visible.
_log_floor = lambda vals: [max(v, 1.0) for v in vals]

_all_bucket_vals = [v for v in (ns_A + total_A + total_B + ns_C + total_C) if v > 0]
_data_max = max(_all_bucket_vals) if _all_bucket_vals else 10_000_000
_y_log_lo = math.log10(100_000)
_y_log_hi = math.log10(_data_max * 1.25)

fig_buckets = go.Figure()

fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=_log_floor(ns_A),
    name="Non-Super: A", fill="tozeroy",
    line=dict(color=COLORS["blue"], width=2),
    fillcolor="rgba(66,117,160,0.12)",
    hovertemplate="Age %{x}<br>Non-Super A: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=_log_floor(total_A),
    name="Total: A (SWR, sustainable)", fill="tonexty",
    line=dict(color=COLORS["purple"], width=2),
    fillcolor="rgba(112,96,168,0.18)",
    hovertemplate="Age %{x}<br>Total A: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages, y=_log_floor(total_B),
    name="Total: B (Deplete Both)",
    line=dict(color=COLORS["orange"], width=2, dash="dash"),
    hovertemplate="Age %{x}<br>Total B: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages_C, y=_log_floor(ns_C),
    name="Non-Super: C (empties at pres. age)",
    line=dict(color=COLORS["yellow"], width=2, dash="longdash"),
    hovertemplate="Age %{x}<br>Non-Super C: $%{y:,.0f}<extra></extra>",
))
fig_buckets.add_trace(go.Scatter(
    x=sim_ages_C, y=_log_floor(total_C),
    name="Total: C (Non-Super First)",
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

nsA_dep  = next((sim_ages[i]   for i, v in enumerate(ns_A)  if v <= 0), None)
supB_dep = next((sim_ages[i]   for i, v in enumerate(sup_B) if v <= 0), None)
nsC_dep  = next((sim_ages_C[i] for i, v in enumerate(ns_C)  if v <= 0), None)
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
    **CHART_LAYOUT,
    xaxis=dict(title="Age", dtick=5),
    yaxis=dict(
        type="log",
        range=[_y_log_lo, _y_log_hi],
        tickformat="$.3s",
        title="Portfolio Balance (Real AUD, log scale)",
    ),
    hovermode="x unified", height=540,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_buckets, width="stretch")

# Early FIRE banner for Strategy C
if fire_age_C and fire_age_C < fire_age_target:
    _bridge_at_C = max(pres_age - fire_age_C, 0)
    st.info(
        f"⚡ **Strategy C lets you FIRE at age {fire_age_C}**. "
        f"{fire_age_target - fire_age_C} year(s) earlier than Strategy A. "
        f"At age {fire_age_C} your non-super portfolio only needs to fund "
        f"${bridge_withdrawal:,.0f}/yr for {_bridge_at_C} years (until super unlocks at {pres_age}), "
        f"not an infinite-horizon portfolio."
    )

# ── Milestone table ────────────────────────────────────────────────────────────
# Build lookups so A/B (indexed by sim_ages) and C (indexed by sim_ages_C) can
# both be queried by age even when their simulation start ages differ.
_ab_idx  = {age: i for i, age in enumerate(sim_ages)}
_c_idx   = {age: i for i, age in enumerate(sim_ages_C)}

_milestone_ages: set[int] = {fire_age_target, fire_age_C_start, sim_end_age}
if pres_age in _ab_idx or pres_age in _c_idx:
    _milestone_ages.add(pres_age)
for _dep in [supB_dep, nsC_dep, nsA_dep]:
    if _dep is not None:
        _milestone_ages.add(_dep)
if fire_age_C and fire_age_C != fire_age_target:
    _milestone_ages.add(fire_age_C)

def _fmt(lst: list, idx_map: dict, age: int) -> str:
    i = idx_map.get(age)
    return f"${lst[i]:,.0f}" if i is not None else "-"

_rows = []
for age in sorted(_milestone_ages):
    if age < min(sim_ages[0], sim_ages_C[0]) or age > sim_end_age:
        continue
    evts = []
    if age == fire_age_target:
        evts.append("🔥 FIRE (A/B)")
    if fire_age_C and age == fire_age_C and fire_age_C != fire_age_target:
        evts.append("🎯 FIRE (C)")
    if fire_age_C_start == fire_age_target and age == fire_age_target:
        evts.append("🎯 FIRE (C)")  # same age, note it
    if age == pres_age:
        evts.append("🔑 Super unlocked")
    if supB_dep and age == supB_dep:
        evts.append("🔀 B: super→non-super")
    if nsC_dep and age == nsC_dep:
        evts.append("🔀 C: non-super→super")
    if nsA_dep and age == nsA_dep:
        evts.append("⚠️ A: non-super depletes")
    if age == sim_end_age:
        evts.append(f"🪦 Target age {sim_end_age}")
    _rows.append({
        "Age":         age,
        "Event":       " | ".join(evts) if evts else "-",
        "Total A":     _fmt(total_A, _ab_idx, age),
        "Non-Super A": _fmt(ns_A,    _ab_idx, age),
        "Super A":     _fmt(sup_A,   _ab_idx, age),
        "Total B":     _fmt(total_B, _ab_idx, age),
        "Total C":     _fmt(total_C, _c_idx,  age),
        "Non-Super C": _fmt(ns_C,    _c_idx,  age),
        "Super C":     _fmt(sup_C,   _c_idx,  age),
    })
if _rows:
    st.dataframe(pd.DataFrame(_rows).set_index("Age"), width="stretch")

with st.expander("📖 How to read the Three-Strategy chart"):
    _pres_ns_A = next((ns_A[i] for i, a in enumerate(sim_ages) if a == pres_age), 0) if pres_age in sim_ages else 0
    st.markdown(f"""
Strategies A & B FIRE at age **{fire_age_target}**. Strategy C can FIRE as early as age **{fire_age_C_start}**.

> ⚠️ **Key correction for Strategy C:** FIREing at {fire_age_C_start} means SGC contributions stop
> **{fire_age_target - fire_age_C_start} year(s) earlier**, so super at preservation age is only
> ~${super_at_pres_C:,.0f} vs ~${super_at_pres_unlocked:,.0f} for A & B.

| | A ♻️ Sustainable | B 💥 Spend Everything | C 🏃 Non-Super First |
|---|---|---|---|
| **FIRE age** | {fire_age_target} | {fire_age_target} | **{fire_age_C_start}** |
| **Bridge spend** | ${bridge_withdrawal:,.0f}/yr (your input) | ${deplete_both_w:,.0f}/yr | ${strat_C_bridge_w:,.0f}/yr |
| **Post-super** | ${swr_post_w:,.0f}/yr SWR forever | Both to $0 by {sim_end_age} | ${strat_C_post_w:,.0f}/yr to $0 by {sim_end_age} |
| **Super at {pres_age}** | ~${super_at_pres_unlocked:,.0f} | ~${super_at_pres_unlocked:,.0f} | ~${super_at_pres_C:,.0f} (fewer SGC yrs) |
| **Non-super at {pres_age}** | ~${_pres_ns_A:,.0f} (keeps compounding) | Depleted | ~$0 (intentionally) |
| **Residual wealth** | Large | $0 | $0 |

**Why Strategy C unlocks earlier FIRE:** You only need non-super to fund **${bridge_withdrawal:,.0f}/yr
for {bridge_years_C} years** (age {fire_age_C_start}\u2192{pres_age}): a finite annuity, much smaller
than an infinite-horizon SWR portfolio. The trade-off: less super at preservation age.

| Colour | Meaning |
|--------|---------|
| Blue fill → purple fill | Non-super + total: Strategy A |
| Orange dashed | Total: Strategy B |
| Yellow long-dash | Non-super: Strategy C (depletes at preservation age) |
| Green long-dash | Total: Strategy C |
| Teal vertical | Super preservation age |
| Yellow vertical | Strategy C: non-super→super switch |
""")


st.divider()

# ── Property & Mortgage Paydown ───────────────────────────────────────────────
_pf_mortgage_monthly = profile.get("pf_mortgage_monthly")
_pf_loan_term_years  = profile.get("pf_loan_term_years")
_pf_purchase_yrs     = profile.get("pf_purchase_years_from_now")
_pf_loan_amount      = profile.get("pf_mortgage_loan_amount")
_pf_mortgage_rate    = profile.get("pf_mortgage_rate")
_pf_property_value   = profile.get("pf_property_value")

if _has_mortgage_data:
    st.subheader("🏠 Property, Mortgage Paydown & Total Net Worth")
    st.caption(
        "Tracks remaining mortgage balance year-by-year (in today's real AUD), home equity as the "
        "property appreciates, and your combined net worth (investment portfolio + home equity)."
    )

    _prop_app_col, _, _ = st.columns(3)
    with _prop_app_col:
        prop_app_rate = st.slider(
            "Property Appreciation (%/yr)", 0.0, 12.0, 4.0, 0.25,
            key="fire_prop_app_rate",
            help="Annual nominal growth rate for the property value after purchase.",
        ) / 100.0

    mort_monthly         = float(_pf_mortgage_monthly)
    loan_term_yrs        = int(_pf_loan_term_years)
    purchase_yr          = int(_pf_purchase_yrs) if _pf_purchase_yrs is not None else 0
    loan_amount          = float(_pf_loan_amount)
    ann_rate             = float(_pf_mortgage_rate)
    prop_val_at_purchase = float(_pf_property_value) if _pf_property_value else loan_amount / 0.80
    monthly_rate         = ann_rate / 12.0
    payoff_yr            = purchase_yr + loan_term_yrs
    payoff_age           = current_age + payoff_yr
    _ann_mortgage        = mort_monthly * 12.0
    _inf_mult            = 1.0 + inf_r

    # ── Amortization helper (nominal $) ─────────────────────────────────────
    def _mort_balance_nom(months_since_purchase: int) -> float:
        """Remaining P&I loan balance (nominal $) after N months of repayments."""
        if months_since_purchase <= 0:
            return loan_amount
        n = float(months_since_purchase)
        if monthly_rate < 1e-10:
            return max(loan_amount - n * mort_monthly, 0.0)
        factor = (1.0 + monthly_rate) ** n
        return max(loan_amount * factor - mort_monthly * (factor - 1.0) / monthly_rate, 0.0)

    # ── Year-by-year schedule ────────────────────────────────────────────────
    horizon_yrs_list = list(range(horizon_years + 1))
    ages_hw          = [current_age + y for y in horizon_yrs_list]

    mort_bal_nom:  list[float | None] = []
    mort_bal_real: list[float | None] = []
    prop_val_real: list[float]        = []
    equity_real:   list[float]        = []

    for yr in horizon_yrs_list:
        if yr < purchase_yr:
            mort_bal_nom.append(None)
            mort_bal_real.append(None)
            prop_val_real.append(0.0)
            equity_real.append(0.0)
        else:
            years_owned = yr - purchase_yr
            months_paid = years_owned * 12
            bal_nom  = _mort_balance_nom(months_paid)
            # Deflate nominal balance to today's real AUD
            bal_real = bal_nom / (_inf_mult ** yr)
            # Property value: nominal appreciation from purchase date, then deflated
            pv_nom   = prop_val_at_purchase * (1.0 + prop_app_rate) ** years_owned
            pv_real  = pv_nom / (_inf_mult ** yr)
            eq_real  = max(pv_real - bal_real, 0.0)
            mort_bal_nom.append(bal_nom)
            mort_bal_real.append(bal_real)
            prop_val_real.append(pv_real)
            equity_real.append(eq_real)

    # Portfolio (real) from best median strategy
    _best_col = (
        f"{median_strat}_Total"
        if (median_strat and f"{median_strat}_Total" in proj_df.columns)
        else f"{selected[0]}_Total"
    )
    port_vals_real = [
        float(proj_df[_best_col].iloc[min(yr, len(proj_df) - 1)])
        if _best_col in proj_df.columns else 0.0
        for yr in horizon_yrs_list
    ]
    total_nw_real = [p + e for p, e in zip(port_vals_real, equity_real)]

    # ── Metrics row ──────────────────────────────────────────────────────────
    nm1, nm2, nm3, nm4 = st.columns(4)
    nm1.metric(
        "Purchase Year",
        f"Year {purchase_yr}",
        f"Age {current_age + purchase_yr}",
    )
    nm2.metric(
        "Mortgage Paid Off",
        f"Age {payoff_age}" if payoff_yr <= horizon_years else "Beyond horizon",
        f"Year {payoff_yr}" if payoff_yr <= horizon_years
        else f"({payoff_yr - horizon_years} yrs past horizon)",
    )
    nm3.metric(
        "DCA Boost at Payoff",
        f"${mort_monthly:,.0f}/mo",
        f"+${_ann_mortgage:,.0f}/yr freed up",
        help="Once the mortgage is gone, this repayment amount is available to redirect into investments.",
    )
    _payoff_equity = equity_real[min(payoff_yr, horizon_years)] if payoff_yr <= horizon_years else equity_real[-1]
    nm4.metric(
        "Home Equity at Payoff (Real)",
        f"${_payoff_equity:,.0f}",
        help="Property value minus zero remaining balance, in today's purchasing power.",
    )

    # ── FIRE spending note ────────────────────────────────────────────────────
    if median_age is not None:
        if payoff_age <= median_age:
            st.success(
                f"✅ **Mortgage fully paid at age {payoff_age}** — {median_age - payoff_age} year(s) "
                f"**before** your FIRE target (age {median_age}). Your spending target of "
                f"**${median_spending:,}/yr** does not need to include the ${_ann_mortgage:,.0f}/yr "
                f"repayment. At payoff, you gain **${mort_monthly:,.0f}/mo** extra to invest."
            )
        else:
            st.warning(
                f"⚠️ **At your FIRE date (age {median_age}), your mortgage has "
                f"{payoff_age - median_age} years remaining** (${mort_monthly:,.0f}/mo = "
                f"${_ann_mortgage:,.0f}/yr). Your FIRE spending target should include this "
                f"repayment until age {payoff_age}, then drops by ${_ann_mortgage:,.0f}/yr "
                f"when the mortgage is fully paid off."
            )

    # ── Chart ─────────────────────────────────────────────────────────────────
    fig_prop = go.Figure()

    # Home equity fill
    _eq_ages = [ages_hw[i] for i, e in enumerate(equity_real) if e > 0]
    _eq_vals = [e for e in equity_real if e > 0]
    if _eq_ages:
        fig_prop.add_trace(go.Scatter(
            x=_eq_ages, y=_eq_vals,
            name="Home Equity (Real AUD)", fill="tozeroy",
            line=dict(color=COLORS["mint"], width=2),
            fillcolor="rgba(78,154,114,0.15)",
            hovertemplate="Age %{x}<br>Home Equity: $%{y:,.0f}<extra></extra>",
        ))

    # Remaining mortgage balance (real)
    _mb_ages = [ages_hw[i] for i, b in enumerate(mort_bal_real) if b is not None]
    _mb_vals = [b for b in mort_bal_real if b is not None]
    if _mb_ages:
        fig_prop.add_trace(go.Scatter(
            x=_mb_ages, y=_mb_vals,
            name="Remaining Mortgage (Real AUD)", fill="tozeroy",
            line=dict(color=COLORS["red"], width=2, dash="dot"),
            fillcolor="rgba(168,72,72,0.10)",
            hovertemplate="Age %{x}<br>Mortgage Balance: $%{y:,.0f}<extra></extra>",
        ))

    # Investment portfolio
    fig_prop.add_trace(go.Scatter(
        x=ages_hw, y=port_vals_real,
        name=f"Investment Portfolio ({median_strat or selected[0]}, Real)",
        line=dict(color=COLORS["blue"], width=2),
        hovertemplate="Age %{x}<br>Portfolio: $%{y:,.0f}<extra></extra>",
    ))

    # Total net worth
    fig_prop.add_trace(go.Scatter(
        x=ages_hw, y=total_nw_real,
        name="Total Net Worth (Portfolio + Equity, Real)",
        line=dict(color=COLORS["purple"], width=3),
        hovertemplate="Age %{x}<br>Total NW: $%{y:,.0f}<extra></extra>",
    ))

    # Vertical lines
    _buy_age = current_age + purchase_yr
    if purchase_yr <= horizon_years:
        fig_prop.add_vline(
            x=_buy_age, line_color=COLORS["yellow"], line_dash="dash", line_width=2,
            annotation_text=f"🏠 Purchase (age {_buy_age})",
            annotation_font_color=COLORS["yellow"], annotation_position="top left",
        )
    if payoff_yr <= horizon_years:
        fig_prop.add_vline(
            x=payoff_age, line_color=COLORS["green"], line_dash="dash", line_width=2,
            annotation_text=f"✅ Mortgage paid off (age {payoff_age})",
            annotation_font_color=COLORS["green"], annotation_position="top right",
        )
    if median_age and current_age <= median_age <= current_age + horizon_years:
        fig_prop.add_vline(
            x=median_age, line_color=COLORS["orange"], line_dash="dot", line_width=2,
            annotation_text=f"🎯 FIRE (age {median_age})",
            annotation_font_color=COLORS["orange"], annotation_position="top right",
        )

    fig_prop.update_layout(
        **CHART_LAYOUT,
        xaxis=dict(title="Age", dtick=5),
        yaxis=dict(tickformat="$.3s", title="Value (Real AUD — today's purchasing power)"),
        hovermode="x unified", height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_prop, width="stretch")

    # ── Year-by-year schedule table ───────────────────────────────────────────
    with st.expander("📋 Year-by-Year Mortgage & Net Worth Schedule"):
        _sched_rows = []
        for yr in horizon_yrs_list:
            if yr < purchase_yr:
                continue
            _sched_rows.append({
                "Year": yr,
                "Age":  current_age + yr,
                "Mortgage Balance (Nominal $)": f"${mort_bal_nom[yr]:,.0f}" if mort_bal_nom[yr] is not None else "—",
                "Mortgage Balance (Real $)":    f"${mort_bal_real[yr]:,.0f}" if mort_bal_real[yr] is not None else "—",
                "Property Value (Real $)":      f"${prop_val_real[yr]:,.0f}",
                "Home Equity (Real $)":         f"${equity_real[yr]:,.0f}",
                "Investment Portfolio (Real $)": f"${port_vals_real[yr]:,.0f}",
                "Total Net Worth (Real $)":     f"${total_nw_real[yr]:,.0f}",
            })
        if _sched_rows:
            st.dataframe(pd.DataFrame(_sched_rows).set_index("Year"), use_container_width=True)

_pct_label = {10: "10th (very conservative)", 25: "25th (conservative)", 50: "50th (median)", 75: "75th (optimistic)", 90: "90th (very optimistic)"}.get(return_percentile, f"{return_percentile}th")
st.warning(
    f"⚠️ Projections use the **{_pct_label} percentile** of historical rolling-window CAGRs from backtest data. "
    f"~{return_percentile}% of historical windows produced returns at or below this level. "
    f"Not a guarantee of future performance."
)
