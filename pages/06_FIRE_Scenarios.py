"""FIRE Scenarios — Coast/Lean/Fat/Barista crossover analysis."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.colors import COLORS, STRATEGY_COLORS, CHART_LAYOUT
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import run_yearly_projection, dca_crossover_year, salary_crossover_year
from engines.calculation_engine import (
    fire_target, lean_fire_target, fat_fire_target, barista_fire_target,
    coast_fire_target, fire_age, preservation_age,
)
from engines.tax_engine import gross_withdrawal_for_net_spend, effective_tax_rate, CGTLaw
from utils import shared_profile as profile
from utils.kids_engine import compute_kids_costs, kids_cost_label

st.set_page_config(page_title="FIRE Scenarios", page_icon="🎯", layout="wide")
profile.init()
st.title("🎯 FIRE Scenarios")
st.caption("Step 6 of your journey: model different paths to financial independence. Compare strategies, DCA rates, and FIRE timelines side by side.")

_pf_monthly_savings          = profile.get("pf_monthly_savings")
_pf_annual_spending          = profile.get("pf_annual_spending")
_pf_investable_surplus       = profile.get("pf_monthly_investable_surplus")
_pf_deposit_monthly_savings  = profile.get("pf_deposit_monthly_savings")
_pf_wants_purchase           = bool(profile.get("pf_wants_to_purchase"))

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
        # Use raw profile values here — the derived _m_purchase_yr / _m_monthly_nominal
        # variables are computed after the sidebar block.
        _sb_purch_yr  = int(_pf_purchase_yrs)    if _pf_purchase_yrs    is not None else 0
        _sb_mort_mo   = float(_pf_mortgage_monthly) if _pf_mortgage_monthly is not None else 0.0
        _sb_term_yrs  = int(_pf_loan_term_years or 0)
        _mort_window_note = (
            f" During years {_sb_purch_yr}–{_sb_purch_yr + _sb_term_yrs} the engine deducts "
            f"**\\${int(_sb_mort_mo):,}/mo** (constant nominal — declines in real over the loan)."
            if (_has_mortgage_data and _sb_term_yrs > 0 and _sb_mort_mo > 0) else ""
        )
        st.caption(
            f"💡 From Home Deposit plan: **\\${max(int(_pf_investable_surplus), 0):,}/mo** "
            f"today's pre-mortgage investable surplus (net income − living expenses)."
            f"{_mort_window_note} "
            f"DCA grows with salary each year."
        )
    elif _pf_monthly_savings is not None:
        st.caption(f"💡 From Budget: **\\${int(_pf_monthly_savings):,}/mo** surplus → used as DCA.")
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

# ── Kids cost overrides (if kids plan is active in profile) ──────────────────
_kids_enabled = bool(profile.get("pf_kids_enabled"))
_kids_annual_costs: dict[int, float] = {}

if _kids_enabled:
    _num_kids     = int(profile.get("pf_num_kids") or 2)
    _k_births     = [
        int(profile.get("pf_kid1_birth_yr_from_now") or 3),
        int(profile.get("pf_kid2_birth_yr_from_now") or 6),
        int(profile.get("pf_kid3_birth_yr_from_now") or 9),
    ]
    _kids_costs_series = compute_kids_costs(
        num_kids=_num_kids,
        birth_yrs_from_now=_k_births,
        schooling=str(profile.get("pf_kids_schooling") or "public"),
        private_school_annual=float(profile.get("pf_kids_private_school_annual") or 20_000),
        private_highschool_annual=float(profile.get("pf_kids_private_highschool_annual") or 30_000),
        childcare_annual_per_child=float(profile.get("pf_kids_childcare_annual") or 12_000),
        setup_cost_per_child=float(profile.get("pf_kids_setup_cost") or 7_500),
        gross_income=float(profile.get("pf_gross_income") or 110_000),
        partner_gross_income=float(profile.get("pf_partner_gross_income") or 0),
        leave_weeks=int(profile.get("pf_parental_leave_weeks") or 18),
        partner_leave_weeks=int(profile.get("pf_parental_leave_partner_weeks") or 4),
        leave_income_pct=float(profile.get("pf_parental_leave_income_pct") or 50),
        bigger_house_monthly_extra=float(profile.get("pf_kids_bigger_house_extra_monthly") or 0),
        partner_career_break_years=int(profile.get("pf_partner_career_break_years") or 0),
        horizon=horizon_years + 1,
    )
    _kids_annual_costs = _kids_costs_series.as_dict()

# ── Mortgage drag override (mortgage-active years only) ──────────────────────
# Mortgage P&I repayments are FIXED IN NOMINAL terms for the life of the loan.
# In real (today's) AUD they DECLINE over time as inflation erodes the payment.
# The DCA base (`pf_monthly_investable_surplus`) is today's net income minus
# living expenses, with NO mortgage subtracted — the mortgage is applied here
# as a per-year override that ramps down in real terms so the engine deducts a
# constant nominal amount each year. Pre-purchase years have no override (no
# mortgage yet) and post-payoff years have no override (mortgage finished).
#
# Engine semantics reminder:
#   year_extra_cost_nominal = override_real * (1 + inflation)^year
# So passing `M_annual_nominal / (1 + inflation)^year` as the real override
# makes the engine deduct exactly `M_annual_nominal` each year (constant nominal).
_mort_drag_overrides: dict[int, float] = {}
_m_purchase_yr     = int(_pf_purchase_yrs) if _pf_purchase_yrs is not None else 0
_m_payoff_yr       = _m_purchase_yr + int(_pf_loan_term_years or 0)
_m_monthly_nominal = float(_pf_mortgage_monthly) if _pf_mortgage_monthly is not None else 0.0
# Backwards-compatible alias (used by chart labels that still read this name).
_m_monthly_real    = _m_monthly_nominal
_m_annual_nominal  = _m_monthly_nominal * 12.0
_inf_decimal_eng   = float(inflation_rate) / 100.0

if _has_mortgage_data and _m_monthly_nominal > 0:
    for yr in range(_m_purchase_yr, min(_m_payoff_yr, horizon_years + 1)):
        # Deflate nominal mortgage to today's AUD for year yr; engine re-inflates.
        _mort_drag_overrides[yr] = _m_annual_nominal / ((1.0 + _inf_decimal_eng) ** yr) if yr > 0 else _m_annual_nominal

# ── Deposit savings DCA drag (pre-purchase years) ────────────────────────────
# During years 0 → purchase_yr the user is locking money away as deposit savings.
# That amount cannot also be invested in the portfolio, so it reduces the DCA
# for those years — mirroring how mortgage repayments reduce it post-purchase.
_deposit_overrides: dict[int, float] = {}
_annual_deposit_savings = 0.0
if (_pf_wants_purchase
        and _pf_deposit_monthly_savings is not None
        and float(_pf_deposit_monthly_savings) > 0
        and _m_purchase_yr > 0):
    _annual_deposit_savings = float(_pf_deposit_monthly_savings) * 12.0
    for yr in range(0, _m_purchase_yr):
        _deposit_overrides[yr] = _annual_deposit_savings  # positive = reduces DCA

# Defined early so the feasibility check below can use it before the DCA-impact chart
_has_deposit_drag = _annual_deposit_savings > 0

# Merge kids costs + mortgage drag (mortgage years) + deposit savings drag.
# All three are positive values = drag on DCA. There is no longer a pre-purchase
# or post-payoff "boost" — the DCA base now excludes mortgage entirely, so
# adding mortgage back outside the loan window would be double-counting.
_combined_overrides: dict[int, float] = {}
_all_override_yrs = (
    set(_kids_annual_costs.keys())
    | set(_mort_drag_overrides.keys())
    | set(_deposit_overrides.keys())
)
for _ov_yr in _all_override_yrs:
    _net = (
        _kids_annual_costs.get(_ov_yr, 0.0)
        + _mort_drag_overrides.get(_ov_yr, 0.0)
        + _deposit_overrides.get(_ov_yr, 0.0)
    )
    if _net != 0.0:
        _combined_overrides[_ov_yr] = _net

# ── DCA feasibility check — clamp if DCA exceeds pre-mortgage surplus ────────
# The DCA base now represents the PRE-MORTGAGE investable amount:
#   Net household income − living expenses
#
# Mortgage, deposit savings, and kids costs are all handled by the override
# system (deducted per-year by the engine). Including them in the DCA ceiling
# would double-count them and produce a falsely low cap.
#
# Net income is computed by splitting the sidebar salary across partners using
# their profile income ratio, then passing each slice through the tax engine.
_feas_you_raw   = float(profile.get("pf_gross_income") or salary)
_feas_p_raw     = float(profile.get("pf_partner_gross_income") or 0) if _partnered else 0.0
_feas_total_raw = max(_feas_you_raw + _feas_p_raw, 1.0)
_feas_you_share = _feas_you_raw / _feas_total_raw

_feas_you_gross = float(salary) * _feas_you_share
_feas_you_hecs  = float(profile.get("pf_hecs_balance") or 0)
_feas_you_priv  = bool(profile.get("pf_private_cover"))
_feas_tax_you   = effective_tax_rate(
    _feas_you_gross, 0, _feas_you_hecs, 0, 0, CGTLaw.CURRENT,
    has_private_hospital_cover=_feas_you_priv,
)
_feas_net_yr0 = _feas_tax_you["net_income"]

if _partnered and profile.get("pf_partner_gross_income"):
    _feas_p_gross = float(salary) * (1.0 - _feas_you_share)
    _feas_p_hecs  = float(profile.get("pf_partner_hecs_balance") or 0)
    _feas_p_priv  = bool(profile.get("pf_partner_private_cover"))
    _feas_tax_p   = effective_tax_rate(
        _feas_p_gross, 0, _feas_p_hecs, 0, 0, CGTLaw.CURRENT,
        has_private_hospital_cover=_feas_p_priv,
    )
    _feas_net_yr0 += _feas_tax_p["net_income"]

_feas_net_mo      = _feas_net_yr0 / 12.0
_feas_living_mo   = float(_pf_annual_spending or 0) / 12.0
_feas_obligatn_mo = _feas_living_mo  # mortgage handled by override, not the ceiling
_feas_surplus_mo  = _feas_net_mo - _feas_obligatn_mo  # negative = living alone exceeds income

# Only applies to Fixed Monthly Amount — percentage method self-adjusts with salary
_dca_over_budget = (
    dca_method == "Fixed Monthly Amount"
    and float(dca_value) > max(0.0, _feas_surplus_mo) + 1.0
)
_effective_dca = int(max(0.0, _feas_surplus_mo)) if _dca_over_budget else dca_value

proj_df = run_yearly_projection(
    data.cagr_df, selected, portfolio, dca_method, _effective_dca, dca_grows, stop_at_coast,
    salary_growth, salary, horizon_years, "Decimal (0.05 = 5%)", inflation_rate, True,
    return_percentile=return_percentile,
    annual_cost_overrides=_combined_overrides or None,
)

# ── Engine-drag summary (always built so it can be used by warnings below) ───
# Lists every per-year drag the engine will apply ON TOP of the DCA ceiling so
# the user can see at a glance what mortgage / deposit / kids will subtract.
# NB: `$` chars in Streamlit markdown trigger LaTeX math; we escape as `\$`.
_engine_drags: list[str] = []
if _has_mortgage_data and _m_monthly_nominal > 0:
    _engine_drags.append(
        f"🏠 **Mortgage:** **\\${_m_monthly_nominal:,.0f}/mo** for "
        f"{int(_pf_loan_term_years or 0)} yrs starting year {_m_purchase_yr} "
        f"(constant nominal — declines in real)"
    )
if _has_deposit_drag:
    _engine_drags.append(
        f"💰 **Deposit savings:** **\\${float(_pf_deposit_monthly_savings):,.0f}/mo** "
        f"for years 0–{_m_purchase_yr} (constant real)"
    )
if _kids_enabled and _kids_annual_costs:
    _peak_yr_w   = max(_kids_annual_costs, key=_kids_annual_costs.get)
    _peak_cost_w = _kids_annual_costs[_peak_yr_w]
    _kids_last_w = max(_kids_annual_costs.keys())
    _engine_drags.append(
        f"👶 **Kids costs:** up to **\\${_peak_cost_w / 12:,.0f}/mo** at peak "
        f"(year {_peak_yr_w}, age {current_age + _peak_yr_w}); "
        f"all kids independent by year {_kids_last_w}"
    )

# ── Worst-year obligations preview ────────────────────────────────────────────
# Compute the maximum combined drag across all projection years so the user
# can see the peak load BEFORE scrolling to the audit chart. This is the most
# honest single-number summary of how tight the plan is.
_peak_drag_yr     = 0
_peak_drag_annual = 0.0
for _yr_chk in range(0, horizon_years + 1):
    _mo = _mort_drag_overrides.get(_yr_chk, 0.0)
    _de = _deposit_overrides.get(_yr_chk, 0.0)
    _ki = _kids_annual_costs.get(_yr_chk, 0.0) if _kids_enabled else 0.0
    _tot = _mo + _de + _ki
    if _tot > _peak_drag_annual:
        _peak_drag_annual = _tot
        _peak_drag_yr     = _yr_chk
_peak_drag_monthly = _peak_drag_annual / 12.0

# Show over-budget warning prominently before any charts
# NB: `$` triggers LaTeX math in Streamlit markdown — escape currency as `\$`.
if _dca_over_budget:
    _feas_breakdown = (
        f"Living **\\${_feas_living_mo:,.0f}/mo** · "
        f"Take-home: **\\${_feas_net_mo:,.0f}/mo**"
    )
    _drag_lines = ("  \n• " + "  \n• ".join(_engine_drags)) if _engine_drags else ""
    if _feas_surplus_mo <= 0:
        st.error(
            f"🚨 **Take-home income doesn't cover living expenses — nothing left to invest.**  \n"
            f"{_feas_breakdown} · Deficit: **\\${abs(_feas_surplus_mo):,.0f}/mo**.  \n"
            f"DCA set to **\\$0/mo**. The engine still applies on top of that:{_drag_lines}"
        )
    else:
        _peak_note = (
            f"  \n📉 **Worst-year combined drag:** **\\${_peak_drag_monthly:,.0f}/mo** "
            f"(year {_peak_drag_yr}, age {current_age + _peak_drag_yr}). "
            + ("**This exceeds the ceiling — DCA will floor at \\$0 that year.** See red banner below the audit chart."
               if _peak_drag_monthly > _feas_surplus_mo + 1.0
               else f"Effective DCA in that year ≈ **\\${max(_feas_surplus_mo - _peak_drag_monthly, 0):,.0f}/mo**.")
            if _peak_drag_annual > 0 else ""
        )
        st.warning(
            f"⚠️ **DCA clamped: \\${dca_value:,}/mo → \\${_effective_dca:,}/mo** (pre-mortgage ceiling).  \n"
            f"{_feas_breakdown} · Available to invest before further drags: **\\${_feas_surplus_mo:,.0f}/mo**.  \n"
            f"The engine then deducts, per year, on top of your DCA:{_drag_lines}"
            f"{_peak_note}"
        )
elif _engine_drags:
    # User isn't clamped, but kids / mortgage / deposit still reduce effective
    # DCA — show an info banner so it's not invisible. Critical when peak drag
    # exceeds the user's DCA (engine silently floors at $0 in that year).
    _drag_lines2 = "  \n• " + "  \n• ".join(_engine_drags)
    # Approximate the year-0 DCA in $/mo so we can compare to peak drag.
    # Percentage-of-salary method: dca_value is a %, convert to $/mo at today's salary.
    if dca_method == "Fixed Monthly Amount":
        _dca_yr0_mo = float(dca_value)
    else:
        _dca_yr0_mo = float(salary) * float(dca_value) / 100.0 / 12.0
    _will_floor = (
        _peak_drag_annual > 0
        and _peak_drag_monthly > _dca_yr0_mo + 1.0
    )
    if _will_floor:
        st.warning(
            f"⚠️ **Peak engine drag of \\${_peak_drag_monthly:,.0f}/mo at year {_peak_drag_yr} "
            f"(age {current_age + _peak_drag_yr}) exceeds your starting DCA of "
            f"\\${_dca_yr0_mo:,.0f}/mo.**  \n"
            f"The engine floors the contribution at \\$0 in any year where drags exceed your DCA, "
            f"so the actual portfolio path will under-perform what your input DCA suggests "
            f"(salary growth may partly close this gap by then). Per-year drags:{_drag_lines2}  \n"
            f"📉 See the red warning banner below the audit chart for the full deficit accounting."
        )
    else:
        st.info(
            f"ℹ️ **The engine deducts the following from your DCA per year "
            f"(already modelled in the charts below):**{_drag_lines2}"
        )

if _kids_enabled and _kids_annual_costs:
    _num_kids_str = {1: "1 child", 2: "2 children", 3: "3 children"}.get(
        int(profile.get("pf_num_kids") or 2), "children"
    )
    st.caption(
        f"👶 Kids plan: **{_num_kids_str}** · "
        f"**{kids_cost_label(str(profile.get('pf_kids_schooling') or 'public'))}** schooling · "
        f"Configure on the **Kids & Family** page. "
        f"(Per-year cost shown in the engine-drag banner above and the charts below.)"
    )

# ── Combined DCA Impact chart (mortgage + deposit savings + kids) ─────────────
# Shown whenever at least one of mortgage, deposit savings, or kids is active.
# The main Double Crossover chart's scale ($0–$3M+) makes DCA changes invisible.
# This chart zooms into the contribution story: what's the ceiling, what eats into
# it, and what actually reaches the portfolio each year.
_show_dca_impact = _kids_enabled or _has_mortgage_data or _has_deposit_drag

if _show_dca_impact:
    _dca_years = list(proj_df["Year"])
    _dca_ages  = [current_age + y for y in _dca_years]

    # Effective DCA at each year in real AUD (post all adjustments, from engine).
    _eff_dca = list(proj_df["Yearly_DCA"])

    # Kids cost per year in real AUD (positive → reduces DCA).
    _kids_yr_costs_real = [_kids_annual_costs.get(yr, 0.0) for yr in _dca_years]

    # Mortgage cost per year for the chart: P&I repayments are FIXED IN NOMINAL,
    # so in real (today's) AUD they DECLINE over the life of the loan.
    # Real repayment at year yr = nominal / (1 + inflation)^yr.
    _inf_decimal = inflation_rate / 100.0
    _mort_yr_costs_real = [
        (_m_monthly_nominal * 12.0) / ((1.0 + _inf_decimal) ** yr)
        if (_has_mortgage_data and _m_purchase_yr <= yr < _m_payoff_yr)
        else 0.0
        for yr in _dca_years
    ]

    # Deposit savings locked out during pre-purchase years.
    # `pf_deposit_monthly_savings` is the required FLAT monthly saving in today's
    # dollars to hit the deposit goal — kept CONSTANT REAL in the engine, so
    # the chart bar is constant real too (no deflation).
    _deposit_yr_costs_real = [
        _annual_deposit_savings
        if (_has_deposit_drag and 0 <= yr < _m_purchase_yr)
        else 0.0
        for yr in _dca_years
    ]

    # Full potential ceiling: effective DCA plus every locked-out amount.
    _ceiling_dca = [
        eff + kids + mort + dep
        for eff, kids, mort, dep
        in zip(_eff_dca, _kids_yr_costs_real, _mort_yr_costs_real, _deposit_yr_costs_real)
    ]

    _total_kids_dca_lost  = sum(_kids_yr_costs_real)
    _total_mort_dca_cost  = sum(_mort_yr_costs_real)
    _total_deposit_locked = sum(_deposit_yr_costs_real)
    _kids_last_yr = max(_kids_annual_costs.keys()) if _kids_annual_costs else 0

    # ── Labels depending on which drags are active ──
    _drags = []
    if _has_mortgage_data: _drags.append("Mortgage")
    if _has_deposit_drag:  _drags.append("Deposit Savings")
    if _kids_enabled:      _drags.append("Kids")
    _drag_label   = " & ".join(_drags)
    _drag_lower   = " + ".join(d.lower() for d in _drags)
    _chart_title  = f"📉 Investment Contributions: {_drag_label} Impact"
    _eff_dca_name = f"Effective DCA (after {_drag_lower})"
    _ceiling_name = f"Ceiling DCA (no {_drag_lower})"

    with st.expander(_chart_title, expanded=True):
        # ── Summary metrics ──────────────────────────────────────────────────
        _met_cols = st.columns(3)

        if _has_mortgage_data and _m_monthly_nominal > 0:
            _mort_payoff_age = current_age + _m_payoff_yr
            _met_cols[0].metric(
                "Mortgage Repayment (Annual)",
                f"${_m_monthly_nominal * 12:,.0f}/yr",
                f"Ends at age {_mort_payoff_age} (constant nominal)",
                delta_color="inverse",
                help=(
                    f"${_m_monthly_nominal:,.0f}/mo P&I is fixed in nominal AUD for the whole loan. "
                    f"In real terms (today's purchasing power) the burden DECLINES each year as CPI "
                    f"erodes the payment. After payoff at age {_mort_payoff_age} the drag ends and "
                    f"the DCA jumps back to net-of-living capacity."
                ),
            )
        else:
            _met_cols[0].metric("Mortgage Impact", "Not active", "No mortgage data exported")

        if _has_deposit_drag:
            _met_cols[1].metric(
                "Deposit Savings (Annual)",
                f"${_annual_deposit_savings:,.0f}/yr",
                f"Locked for {_m_purchase_yr} yr(s) pre-purchase",
                delta_color="inverse",
                help=(
                    f"${float(_pf_deposit_monthly_savings):,.0f}/mo going to the deposit fund "
                    f"reduces investable DCA during years 0–{_m_purchase_yr}. "
                    "Once the house is purchased this drag disappears."
                ),
            )
        else:
            _met_cols[1].metric("Kids Impact", "Not active", "No kids plan configured")

        if _kids_enabled and _kids_annual_costs:
            _peak_kids_yr   = max(_kids_annual_costs, key=_kids_annual_costs.get)
            _peak_kids_cost = _kids_annual_costs[_peak_kids_yr]
            _met_cols[2].metric(
                "Total Foregone (Real)",
                f"${_total_kids_dca_lost + _total_mort_dca_cost + _total_deposit_locked:,.0f}",
                (f"Kids free by age {current_age + _kids_last_yr}"
                 if _kids_last_yr else "Ongoing"),
                delta_color="off",
                help=(
                    "Combined real-dollar investment opportunity cost: "
                    f"${_total_mort_dca_cost:,.0f} from mortgage · "
                    f"${_total_deposit_locked:,.0f} from deposit savings · "
                    f"${_total_kids_dca_lost:,.0f} from kids costs. "
                    "Compounding magnifies the actual portfolio impact beyond this number."
                ),
            )
        else:
            _met_cols[2].metric(
                "Total Foregone (Real)",
                f"${_total_mort_dca_cost + _total_deposit_locked:,.0f}",
                "Mortgage + deposit saving period (real AUD)",
                delta_color="off",
                help=(
                    f"${_total_mort_dca_cost:,.0f} from mortgage repayments + "
                    f"${_total_deposit_locked:,.0f} from deposit savings locked pre-purchase."
                ),
            )

        # ── Chart ────────────────────────────────────────────────────────────
        fig_dca = go.Figure()

        # Ceiling — maximum potential if no obligations
        fig_dca.add_trace(go.Scatter(
            x=_dca_ages, y=_ceiling_dca,
            name=_ceiling_name,
            line=dict(color=COLORS["soft_yellow"], width=2, dash="dot"),
            hovertemplate="Age %{x}<br>Ceiling DCA: $%{y:,.0f}/yr<extra></extra>",
        ))

        # Deposit savings layer — teal bars for the pre-purchase saving period
        if _has_deposit_drag and any(v > 0 for v in _deposit_yr_costs_real):
            fig_dca.add_trace(go.Bar(
                x=_dca_ages, y=_deposit_yr_costs_real,
                name="Deposit Savings (locked pre-purchase)",
                marker_color="rgba(78,154,114,0.55)",
                hovertemplate="Age %{x}<br>Deposit savings: $%{y:,.0f}/yr<extra></extra>",
            ))

        # Mortgage layer — orange bars for the portion locked in repayments
        if _has_mortgage_data and any(v > 0 for v in _mort_yr_costs_real):
            fig_dca.add_trace(go.Bar(
                x=_dca_ages, y=_mort_yr_costs_real,
                name="Mortgage Repayments (locked)",
                marker_color="rgba(210,120,40,0.5)",
                hovertemplate="Age %{x}<br>Mortgage: $%{y:,.0f}/yr<extra></extra>",
            ))

        # Kids layer — red bars for the portion consumed by kids
        if _kids_enabled and any(v > 0 for v in _kids_yr_costs_real):
            fig_dca.add_trace(go.Bar(
                x=_dca_ages, y=_kids_yr_costs_real,
                name="Kids Costs (DCA reduction)",
                marker_color="rgba(168,72,72,0.45)",
                hovertemplate="Age %{x}<br>Kids cost: $%{y:,.0f}/yr<extra></extra>",
            ))

        # Effective DCA — what actually reaches the portfolio
        fig_dca.add_trace(go.Scatter(
            x=_dca_ages, y=_eff_dca,
            name=_eff_dca_name,
            line=dict(color=COLORS["blue"], width=3),
            fill="tozeroy",
            fillcolor="rgba(66,117,160,0.12)",
            hovertemplate="Age %{x}<br>Effective DCA: $%{y:,.0f}/yr<extra></extra>",
        ))

        # Vertical: mortgage purchase and payoff
        if _has_mortgage_data:
            if 0 <= _m_purchase_yr <= horizon_years:
                fig_dca.add_vline(
                    x=current_age + _m_purchase_yr,
                    line_color="rgba(210,120,40,0.7)", line_dash="dash", line_width=1,
                    annotation_text="House purchased",
                    annotation_font_color="rgba(210,120,40,0.9)",
                    annotation_position="top left",
                )
            if 0 <= _m_payoff_yr <= horizon_years:
                fig_dca.add_vline(
                    x=current_age + _m_payoff_yr,
                    line_color="rgba(210,120,40,0.7)", line_dash="dot", line_width=1,
                    annotation_text="Mortgage paid off → DCA jumps",
                    annotation_font_color="rgba(210,120,40,0.9)",
                    annotation_position="top right",
                )

        # Vertical: kids' birth years
        if _kids_enabled:
            for _k_idx, _k_pf_key in enumerate(
                ["pf_kid1_birth_yr_from_now", "pf_kid2_birth_yr_from_now", "pf_kid3_birth_yr_from_now"],
                start=1,
            ):
                if _k_idx > int(profile.get("pf_num_kids") or 2):
                    break
                _k_birth_yr = int(profile.get(_k_pf_key) or (_k_idx * 3))
                if 0 <= _k_birth_yr <= horizon_years:
                    fig_dca.add_vline(
                        x=current_age + _k_birth_yr,
                        line_color=COLORS["pink"], line_dash="dash", line_width=1,
                        annotation_text=f"Child {_k_idx} born",
                        annotation_font_color=COLORS["pink"],
                        annotation_position="top left" if _k_idx == 1 else "top right",
                    )

        fig_dca.update_layout(
            **CHART_LAYOUT,
            barmode="stack",
            xaxis=dict(title="Age", dtick=5),
            yaxis=dict(tickformat="$,.0f", title="Annual Investment (Real AUD)"),
            hovermode="x unified", height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_dca, width="stretch")

        _cap_parts = [
            "**Blue area** = what actually reaches your portfolio each year (real AUD).",
        ]
        if _has_deposit_drag:
            _cap_parts.append(
                f"**Teal bars** = deposit savings locked out of investing during the "
                f"{_m_purchase_yr}-year saving period (\\${float(_pf_deposit_monthly_savings):,.0f}/mo, "
                f"constant real). Disappears once the house is purchased."
            )
        if _has_mortgage_data:
            _cap_parts.append(
                f"**Orange bars** = mortgage repayments. P&I is fixed in nominal AUD "
                f"(**\\${_m_monthly_nominal:,.0f}/mo** for the whole loan), so the real bar "
                f"DECLINES each year as CPI erodes the payment. Bar disappears at "
                f"payoff (age {current_age + _m_payoff_yr})."
            )
        if _kids_enabled:
            _cap_parts.append(
                "**Red bars** = portion of your surplus consumed by kids costs each year (constant real)."
            )
        _cap_parts.append(
            "**Dotted line** = ceiling DCA with no obligations (what you'd invest if none of the above applied). "
            "The portfolio simulation uses the blue line, so all drags are already modelled."
        )
        st.caption("  \n".join(_cap_parts))

# ── Annual Cashflow Audit ─────────────────────────────────────────────────────
# Two-panel view: top panel stacks every known use of income year-by-year so the
# bars should reach the net-salary line; bottom panel isolates the gap so
# surpluses and deficits are immediately obvious at a glance.
with st.expander("🔍 Annual Cashflow Audit — spending vs salary", expanded=False):
    st.caption(
        "**Top:** where every dollar of gross salary goes each year (real, today's AUD). "
        "Tax computed via Australian tax engine each year. "
        "**Bottom:** gap = net income minus all known outflows. "
        "Green = unallocated surplus; red = model deficit (DCA set above investable surplus)."
    )

    # ── Per-year tax via Australian tax engine ───────────────────────────────
    # Each year's real salary is split proportionally across household members and
    # passed through the full tax engine (income tax, Medicare, LITO, HECS).
    # Treating the real salary against the nominal brackets is equivalent to assuming
    # brackets are inflation-indexed — a reasonable planning assumption.
    _a_you_gross       = float(profile.get("pf_gross_income") or salary)
    _a_you_hecs        = float(profile.get("pf_hecs_balance") or 0)
    _a_you_priv        = bool(profile.get("pf_private_cover"))
    _a_hh_gross        = _a_you_gross
    _a_p_gross_loop    = 0.0
    _a_p_hecs_loop     = 0.0
    _a_p_priv_loop     = False

    if _partnered and profile.get("pf_partner_gross_income"):
        _a_p_gross_loop = float(profile.get("pf_partner_gross_income"))
        _a_p_hecs_loop  = float(profile.get("pf_partner_hecs_balance") or 0)
        _a_p_priv_loop  = bool(profile.get("pf_partner_private_cover"))
        _a_hh_gross    += _a_p_gross_loop

    _you_income_share   = _a_you_gross / max(_a_hh_gross, 1.0)
    _has_partner_income = _a_p_gross_loop > 0

    _inf_a  = inflation_rate / 100.0
    _sg_a   = salary_growth / 100.0
    _living = float(_pf_annual_spending) if _pf_annual_spending is not None else 0.0

    _au_ages     : list[int]   = []
    _au_tax      : list[float] = []
    _au_living   : list[float] = []
    _au_kids_au  : list[float] = []
    _au_deposit  : list[float] = []
    _au_mort     : list[float] = []
    _au_dca      : list[float] = []
    _au_gap      : list[float] = []
    _au_gross    : list[float] = []
    _au_net      : list[float] = []

    for _au_yr, _au_dca_val in zip(list(proj_df["Year"]), list(proj_df["Yearly_DCA"])):
        _real_sal = float(salary) * ((1 + _sg_a) / (1 + _inf_a)) ** _au_yr if _au_yr > 0 else float(salary)
        # Compute tax at this year's real income using the full Australian tax engine
        _you_inc_yr = _real_sal * _you_income_share
        _yr_tax_you = effective_tax_rate(
            _you_inc_yr, 0, _a_you_hecs, 0, 0, CGTLaw.CURRENT,
            has_private_hospital_cover=_a_you_priv,
        )
        _real_tax = _yr_tax_you["total_tax"]
        if _has_partner_income:
            _p_inc_yr  = _real_sal * (1.0 - _you_income_share)
            _yr_tax_p  = effective_tax_rate(
                _p_inc_yr, 0, _a_p_hecs_loop, 0, 0, CGTLaw.CURRENT,
                has_private_hospital_cover=_a_p_priv_loop,
            )
            _real_tax += _yr_tax_p["total_tax"]
        _real_net = _real_sal - _real_tax

        # Mortgage P&I is FIXED IN NOMINAL — in real (today's) AUD the bar
        # DECLINES over the loan. The engine deducts a constant nominal amount
        # via the per-year-deflated override, so the visualisation matches the
        # actual real-AUD impact on the user's investable cashflow.
        _au_mort_val = 0.0
        if _has_mortgage_data and _m_purchase_yr <= _au_yr < _m_payoff_yr:
            _au_mort_val = (_m_monthly_nominal * 12.0) / ((1.0 + _inf_a) ** _au_yr) if _au_yr > 0 else (_m_monthly_nominal * 12.0)

        # Deposit savings: `pf_deposit_monthly_savings` is the required FLAT
        # monthly saving in today's dollars to hit the deposit goal, so it's
        # held constant real (no deflation).
        _au_dep_val = 0.0
        if _has_deposit_drag and 0 <= _au_yr < _m_purchase_yr:
            _au_dep_val = _annual_deposit_savings

        # Kids costs already in real AUD (same basis as the DCA engine overrides).
        # Yearly_DCA has these subtracted, so we surface them here as a named bar.
        _au_kids_val = float(_kids_annual_costs.get(_au_yr, 0.0)) if _kids_enabled else 0.0

        _au_dca_real = float(_au_dca_val)

        # Gap = net income − all known outflows
        _au_gap_val = _real_net - _living - _au_kids_val - _au_mort_val - _au_dep_val - _au_dca_real

        _au_ages.append(current_age + _au_yr)
        _au_gross.append(_real_sal)
        _au_net.append(_real_net)
        _au_tax.append(_real_tax)
        _au_living.append(_living)
        _au_kids_au.append(_au_kids_val)
        _au_deposit.append(_au_dep_val)
        _au_mort.append(_au_mort_val)
        _au_dca.append(_au_dca_real)
        _au_gap.append(_au_gap_val)

    # ── Two-panel figure ─────────────────────────────────────────────────────
    _has_kids_bars = _kids_enabled and any(v > 0 for v in _au_kids_au)

    fig_audit = make_subplots(
        rows=2, cols=1,
        row_heights=[0.70, 0.30],
        shared_xaxes=True,
        vertical_spacing=0.07,
        subplot_titles=["Income Allocation", "Surplus / Deficit Gap"],
    )

    # ── Top panel: stacked income bars ───────────────────────────────────────
    fig_audit.add_trace(go.Bar(
        x=_au_ages, y=_au_tax,
        name="Tax + Medicare + HECS (approx)",
        marker_color="rgba(185,72,72,0.88)",
        hovertemplate="Age %{x}<br>Tax: $%{y:,.0f}/yr<extra></extra>",
    ), row=1, col=1)

    fig_audit.add_trace(go.Bar(
        x=_au_ages, y=_au_living,
        name="Living Expenses" + (" (from Budget)" if _pf_annual_spending else " — not set"),
        marker_color="rgba(224,123,44,0.88)",
        hovertemplate="Age %{x}<br>Living: $%{y:,.0f}/yr<extra></extra>",
    ), row=1, col=1)

    if _has_kids_bars:
        fig_audit.add_trace(go.Bar(
            x=_au_ages, y=_au_kids_au,
            name="Kids Costs",
            marker_color="rgba(210,80,130,0.85)",
            hovertemplate="Age %{x}<br>Kids: $%{y:,.0f}/yr<extra></extra>",
        ), row=1, col=1)

    if _has_deposit_drag and any(v > 0 for v in _au_deposit):
        fig_audit.add_trace(go.Bar(
            x=_au_ages, y=_au_deposit,
            name="Deposit Savings (pre-purchase)",
            marker_color="rgba(78,154,114,0.78)",
            hovertemplate="Age %{x}<br>Deposit: $%{y:,.0f}/yr<extra></extra>",
        ), row=1, col=1)

    if _has_mortgage_data and any(v > 0 for v in _au_mort):
        fig_audit.add_trace(go.Bar(
            x=_au_ages, y=_au_mort,
            name="Mortgage Repayments",
            marker_color="rgba(210,155,40,0.85)",
            hovertemplate="Age %{x}<br>Mortgage: $%{y:,.0f}/yr<extra></extra>",
        ), row=1, col=1)

    fig_audit.add_trace(go.Bar(
        x=_au_ages, y=_au_dca,
        name="DCA — Invested",
        marker_color="rgba(66,117,160,0.90)",
        hovertemplate="Age %{x}<br>DCA invested: $%{y:,.0f}/yr<extra></extra>",
    ), row=1, col=1)

    # Reference lines
    fig_audit.add_trace(go.Scatter(
        x=_au_ages, y=_au_gross,
        name="Gross Salary (Real)",
        mode="lines",
        line=dict(color=COLORS["yellow"], width=2),
        hovertemplate="Age %{x}<br>Gross: $%{y:,.0f}/yr<extra></extra>",
    ), row=1, col=1)

    fig_audit.add_trace(go.Scatter(
        x=_au_ages, y=_au_net,
        name="Net After-Tax (approx, Real)",
        mode="lines",
        line=dict(color=COLORS["mint"], width=2, dash="dot"),
        hovertemplate="Age %{x}<br>Net: $%{y:,.0f}/yr<extra></extra>",
    ), row=1, col=1)

    # ── Bottom panel: gap bars ────────────────────────────────────────────────
    _gap_colors = [
        "rgba(61,153,112,0.82)" if g >= 0 else "rgba(185,72,72,0.82)"
        for g in _au_gap
    ]
    fig_audit.add_trace(go.Bar(
        x=_au_ages, y=_au_gap,
        name="Gap / Unallocated",
        marker_color=_gap_colors,
        hovertemplate="Age %{x}<br>Gap: $%{y:,.0f}/yr<extra></extra>",
        showlegend=True,
    ), row=2, col=1)

    # Zero reference in gap panel
    fig_audit.add_hline(y=0, line_color="rgba(255,255,255,0.25)", line_width=1, row=2, col=1)

    # ── Event vertical lines (span both panels) ───────────────────────────────
    if _has_mortgage_data:
        if 0 <= _m_purchase_yr <= horizon_years:
            fig_audit.add_vline(
                x=current_age + _m_purchase_yr,
                line_color="rgba(210,155,40,0.65)", line_dash="dash", line_width=1,
                annotation_text="House purchased",
                annotation_font_color="rgba(210,155,40,0.95)",
                annotation_position="top left",
            )
        if 0 <= _m_payoff_yr <= horizon_years:
            fig_audit.add_vline(
                x=current_age + _m_payoff_yr,
                line_color="rgba(210,155,40,0.65)", line_dash="dot", line_width=1,
                annotation_text="Mortgage paid off",
                annotation_font_color="rgba(210,155,40,0.95)",
                annotation_position="top right",
            )

    if _kids_enabled:
        for _k_idx_au, _k_pf_key_au in enumerate(
            ["pf_kid1_birth_yr_from_now", "pf_kid2_birth_yr_from_now", "pf_kid3_birth_yr_from_now"],
            start=1,
        ):
            if _k_idx_au > int(profile.get("pf_num_kids") or 2):
                break
            _k_birth_yr_au = int(profile.get(_k_pf_key_au) or (_k_idx_au * 3))
            if 0 <= _k_birth_yr_au <= horizon_years:
                fig_audit.add_vline(
                    x=current_age + _k_birth_yr_au,
                    line_color=COLORS["pink"], line_dash="dash", line_width=1,
                    annotation_text=f"Child {_k_idx_au} born",
                    annotation_font_color=COLORS["pink"],
                    annotation_position="top left" if _k_idx_au == 1 else "top right",
                )

    # ── Layout ───────────────────────────────────────────────────────────────
    fig_audit.update_layout(
        **CHART_LAYOUT,
        barmode="stack",
        hovermode="x unified",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_audit.update_xaxes(title_text="Age", dtick=5, row=2, col=1)
    fig_audit.update_yaxes(tickformat="$,.0f", title_text="Annual Amount (Real AUD)", row=1, col=1)
    fig_audit.update_yaxes(tickformat="$,.0f", title_text="Gap (Real AUD)", row=2, col=1)

    st.plotly_chart(fig_audit, width="stretch")

    if _pf_annual_spending is None:
        st.warning("💡 Export your **Budget & Savings** to include living expenses in the audit.")

    _cap_parts_au = [
        "📏 **All values are in today's AUD (real).** A flat bar across years means the underlying "
        "cost is rising with CPI in nominal terms — its purchasing power stays the same. "
        "A **declining** bar means the underlying cost is fixed in nominal terms (so it erodes in real).",
        "**Tax** is computed each year via the Australian tax engine (income tax + Medicare + LITO + HECS) "
        "on each partner's proportional real income. Brackets are **treated as inflation-indexed** — a standard "
        "planning simplification. Current Australian brackets are NOT statutorily indexed, so real bracket creep "
        "may make actual tax slightly higher than shown if wages outpace inflation.",
        "**Living expenses** are held constant in real terms — i.e. they rise with CPI in nominal terms "
        "but their purchasing power is preserved each year. No lifestyle inflation above CPI is modelled.",
    ]
    if _has_kids_bars:
        _cap_parts_au.append(
            "**Pink bars** = kids costs each year (already deducted from the DCA line, shown explicitly here). "
            "Constant real."
        )
    if _has_deposit_drag:
        _cap_parts_au.append(
            "**Teal bars** = deposit savings locked out of investing pre-purchase (constant real — the "
            "required flat monthly saving to hit the deposit goal in today's dollars)."
        )
    if _has_mortgage_data:
        _cap_parts_au.append(
            f"**Amber bars** = mortgage repayments. P&I is fixed in nominal AUD "
            f"(**\\${_m_monthly_nominal:,.0f}/mo** for the whole loan), so the real bar declines each year "
            f"as CPI erodes the payment — the burden of the mortgage shrinks over time in real terms."
        )
    _cap_parts_au.append(
        "**Green cap** = unallocated surplus (income not routed anywhere — raise DCA to capture it). "
        "**Red notch** = model over-allocated — DCA + expenses exceed net income. "
        "The bottom panel shows the same gap in isolation. "
        "If you see persistent red, reduce DCA or check that living expenses are correctly set."
    )
    st.caption("  \n".join(_cap_parts_au))

    # ── Negative-gap warning banner ──────────────────────────────────────────
    # Surface deficits prominently — the chart can hide them at a glance when
    # only a few years go red. Aggregate the years and the magnitude so the
    # user knows the financial plan currently over-commits in some years.
    _deficit_pairs = [(age, gap) for age, gap in zip(_au_ages, _au_gap) if gap < 0]
    if _deficit_pairs:
        _n_def       = len(_deficit_pairs)
        _ages_def    = [a for a, _ in _deficit_pairs]
        _peak_def    = min(_deficit_pairs, key=lambda p: p[1])  # most negative
        _total_def   = sum(-g for _, g in _deficit_pairs)
        _age_min_def = min(_ages_def)
        _age_max_def = max(_ages_def)
        _years_label = (
            f"age **{_age_min_def}**"
            if _age_min_def == _age_max_def
            else f"ages **{_age_min_def}–{_age_max_def}** ({_n_def} year{'s' if _n_def != 1 else ''})"
        )
        st.error(
            f"🚨 **Plan over-commits income in {_n_def} year{'s' if _n_def != 1 else ''} "
            f"({_years_label}).**  \n"
            f"• Worst year: age **{_peak_def[0]}** with a deficit of "
            f"**\\${abs(_peak_def[1]):,.0f}** (real AUD).  \n"
            f"• Cumulative real-AUD shortfall across all deficit years: "
            f"**\\${_total_def:,.0f}**.  \n"
            f"This means DCA + living + mortgage + deposit + kids costs collectively exceed "
            f"net income in those years. In the engine the DCA floors at \\$0, so the deficit "
            f"is silently absorbed by skipping contributions — your projected portfolio is "
            f"lower than the input DCA suggests. **Recommended actions:** reduce the Monthly DCA, "
            f"increase the household salary input, extend the loan term, lower the deposit %, "
            f"or revisit the kids/budget assumptions."
        )

# ── Cumulative Cash Balance ───────────────────────────────────────────────────
# Integrates the per-year gap from the audit chart so the user can see the
# running cash position outside the investment portfolio — i.e. how much money
# accumulates from unallocated surpluses, and how deep a cash buffer they'd
# need to weather any deficit years.
with st.expander("💰 Cumulative Cash Balance — running savings/deficit from surpluses", expanded=False):
    st.caption(
        "If every year's surplus from the audit chart above accumulates "
        "(and every deficit is drawn down from cash), this is the cash you'd "
        "have kicking around in **today's AUD** — separate from the investment portfolio. "
        "Default assumes 0% real interest (a typical HISA roughly keeps pace with CPI). "
        "Adjust the slider for a higher-yield cash account or a deliberately under-CPI assumption."
    )

    _cash_real_yield_pct = st.slider(
        "Cash account real return (% above CPI)",
        min_value=-2.0, max_value=5.0, value=0.0, step=0.25,
        help=(
            "0% = cash roughly keeps pace with inflation (real-AUD constant). "
            "Positive = real growth (e.g. money-market fund); "
            "negative = cash erodes faster than inflation (typical low-interest account)."
        ),
        key="cash_real_yield_slider",
    )
    _r_cash = _cash_real_yield_pct / 100.0

    # Compound the per-year real gap at the chosen real cash yield.
    # All gaps are already in real (today's) AUD from the audit chart.
    _cum_cash: list[float] = []
    _bal_cash = 0.0
    for _g_yr in _au_gap:
        _bal_cash = _bal_cash * (1.0 + _r_cash) + float(_g_yr)
        _cum_cash.append(_bal_cash)

    if _cum_cash:
        _peak_cash    = max(_cum_cash)
        _peak_age     = _au_ages[_cum_cash.index(_peak_cash)]
        _trough_cash  = min(_cum_cash)
        _trough_age   = _au_ages[_cum_cash.index(_trough_cash)]
        _end_cash     = _cum_cash[-1]
        _end_age      = _au_ages[-1]
        _first_neg_i  = next((i for i, v in enumerate(_cum_cash) if v < 0), None)
        _first_neg_age = _au_ages[_first_neg_i] if _first_neg_i is not None else None
    else:
        _peak_cash = _trough_cash = _end_cash = 0.0
        _peak_age = _trough_age = _end_age = current_age
        _first_neg_age = None

    # ── Summary metrics ──────────────────────────────────────────────────────
    cm1, cm2, cm3, cm4 = st.columns(4)
    cm1.metric(
        "Peak Cash",
        f"${_peak_cash:,.0f}",
        f"at age {_peak_age}",
        delta_color="off",
        help="Maximum cash balance accumulated outside the investment portfolio over the horizon.",
    )
    cm2.metric(
        "Lowest Cash",
        f"${_trough_cash:,.0f}",
        f"at age {_trough_age}",
        delta_color="off" if _trough_cash >= 0 else "inverse",
        help=("Minimum cash balance. If negative, you'd need a cash buffer of at least "
              "this magnitude to weather the plan without going into debt."),
    )
    cm3.metric(
        "End-of-Horizon Cash",
        f"${_end_cash:,.0f}",
        f"at age {_end_age}",
        delta_color="off",
        help="Cash left over at the end of the projection horizon (real AUD).",
    )
    cm4.metric(
        "First Year Cash < $0",
        f"Age {_first_neg_age}" if _first_neg_age is not None else "Never",
        delta_color="inverse" if _first_neg_age is not None else "off",
        help=("The first age at which cumulative surpluses no longer cover cumulative deficits. "
              "After this age you would need to borrow or draw from the investment portfolio."),
    )

    # ── Cumulative cash chart ────────────────────────────────────────────────
    # Two stacked-tozeroy areas (green for positive, red for negative) plus the
    # main line drawn on top so the running balance is unambiguous.
    _pos_cash = [c if c >= 0 else 0.0 for c in _cum_cash]
    _neg_cash = [c if c < 0 else 0.0 for c in _cum_cash]

    fig_cash = go.Figure()

    fig_cash.add_trace(go.Scatter(
        x=_au_ages, y=_neg_cash,
        mode="lines",
        line=dict(color="rgba(185,72,72,0)", width=0),
        fill="tozeroy",
        fillcolor="rgba(185,72,72,0.30)",
        name="Cash deficit",
        showlegend=False,
        hoverinfo="skip",
    ))
    fig_cash.add_trace(go.Scatter(
        x=_au_ages, y=_pos_cash,
        mode="lines",
        line=dict(color="rgba(61,153,112,0)", width=0),
        fill="tozeroy",
        fillcolor="rgba(61,153,112,0.28)",
        name="Cash surplus",
        showlegend=False,
        hoverinfo="skip",
    ))
    fig_cash.add_trace(go.Scatter(
        x=_au_ages, y=_cum_cash,
        mode="lines+markers",
        line=dict(color=COLORS["dark"], width=2.5),
        marker=dict(size=4),
        name="Cumulative Cash",
        hovertemplate="Age %{x}<br>Cumulative cash: \\$%{y:,.0f}<extra></extra>",
    ))

    fig_cash.add_hline(y=0, line_color="rgba(255,255,255,0.45)", line_width=1)

    if _has_mortgage_data:
        if 0 <= _m_purchase_yr <= horizon_years:
            fig_cash.add_vline(
                x=current_age + _m_purchase_yr,
                line_color="rgba(210,155,40,0.55)", line_dash="dash", line_width=1,
                annotation_text="House purchased",
                annotation_font_color="rgba(210,155,40,0.9)",
                annotation_position="top left",
            )
        if 0 <= _m_payoff_yr <= horizon_years:
            fig_cash.add_vline(
                x=current_age + _m_payoff_yr,
                line_color="rgba(210,155,40,0.55)", line_dash="dot", line_width=1,
                annotation_text="Mortgage paid off",
                annotation_font_color="rgba(210,155,40,0.9)",
                annotation_position="top right",
            )

    if _kids_enabled:
        for _k_idx_c, _k_pf_key_c in enumerate(
            ["pf_kid1_birth_yr_from_now", "pf_kid2_birth_yr_from_now", "pf_kid3_birth_yr_from_now"],
            start=1,
        ):
            if _k_idx_c > int(profile.get("pf_num_kids") or 2):
                break
            _k_birth_c = int(profile.get(_k_pf_key_c) or (_k_idx_c * 3))
            if 0 <= _k_birth_c <= horizon_years:
                fig_cash.add_vline(
                    x=current_age + _k_birth_c,
                    line_color=COLORS["pink"], line_dash="dash", line_width=1,
                    annotation_text=f"Child {_k_idx_c} born",
                    annotation_font_color=COLORS["pink"],
                    annotation_position="top left" if _k_idx_c == 1 else "top right",
                )

    fig_cash.update_layout(
        **CHART_LAYOUT,
        hovermode="x unified",
        xaxis=dict(title="Age", dtick=5),
        yaxis=dict(tickformat="$,.0f", title="Cumulative Cash (Real AUD)"),
        height=380,
        showlegend=False,
    )
    st.plotly_chart(fig_cash, width="stretch")

    # ── Caption (narrates what the chart means + suggested action) ───────────
    _cap_cash_parts = [
        "**Dark line** = running cash balance, starting at \\$0 today, "
        "compounded yearly at the real return above.",
        "**Green shading** = positive cash (you've accumulated unallocated surplus outside the portfolio).",
        "**Red shading** = negative balance — cumulative deficits exceed cumulative surpluses, so the "
        "plan would require borrowing or a starting cash buffer.",
    ]
    if _first_neg_age is not None:
        _cap_cash_parts.append(
            f"⚠️ **Plan first goes cash-negative at age {_first_neg_age}.** You'd need at least "
            f"**\\${abs(_trough_cash):,.0f}** of starting cash (today's AUD) to weather the deficit "
            "years without taking on debt, *or* you'd need to reduce DCA / increase income to remove "
            "the deficit years entirely (see the audit chart's red warning above)."
        )
    elif _peak_cash > 0:
        _cap_cash_parts.append(
            f"✅ Cash balance stays positive throughout the horizon "
            f"(peak **\\${_peak_cash:,.0f}** at age {_peak_age}). "
            "Excess cash sitting in a HISA earns near-CPI — consider redirecting some into the "
            "investment portfolio (raise DCA) to compound at the higher equity return instead."
        )
    if _r_cash != 0.0:
        _cap_cash_parts.append(
            f"📊 Compounding at **{_cash_real_yield_pct:+.2f}% real**/yr "
            "(adjustable above)."
        )
    st.caption("  \n".join(_cap_cash_parts))

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

# Mortgage-active gross withdrawals: spending + full P&I repayment must come from the portfolio.
# The gross amount is higher because mortgage repayments are a post-tax cashflow obligation.
if _has_mortgage_data and _pf_mortgage_monthly is not None:
    _mortgage_annual_repayment = float(_pf_mortgage_monthly) * 12.0
    lean_gross_mort   = gross_withdrawal_for_net_spend(lean_spending   + _mortgage_annual_repayment)
    median_gross_mort = gross_withdrawal_for_net_spend(median_spending + _mortgage_annual_repayment)
    fat_gross_mort    = gross_withdrawal_for_net_spend(fat_spending    + _mortgage_annual_repayment)
else:
    _mortgage_annual_repayment = 0.0
    lean_gross_mort = lean_gross
    median_gross_mort = median_gross
    fat_gross_mort = fat_gross

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

# Real portfolio return at the selected percentile — used for PV discounting in the
# cashflow-based mortgage-adjusted threshold.
if median_strat and median_strat in data.cagr_df.columns:
    _pv_arr = pd.to_numeric(data.cagr_df[median_strat], errors="coerce").dropna().to_numpy(dtype=float)
    _pv_nom_r = float(np.percentile(_pv_arr, return_percentile)) if len(_pv_arr) else 0.07
else:
    _pv_nom_r = 0.07
_real_r_for_pv = max((1.0 + _pv_nom_r) / (1.0 + float(inflation_rate) / 100.0) - 1.0, 0.01)


def _cashflow_mort_threshold(yr: int, base_target: float, high_gross: float) -> float:
    """
    Cashflow-based FIRE threshold at projection year yr.

    The portfolio must sustain:
      - Phase 1 (n remaining mortgage years): withdraw high_gross/yr
        (living expenses + mortgage P&I repayments, after-tax gross-up)
      - Phase 2 (post payoff, in perpetuity): withdraw base_target * swr /yr
        (standard SWR on base_target portfolio)

    Required portfolio = PV(annuity of high_gross for n years at real r)
                       + PV(base_target lump sum at year n, discounted at real r)

    When n = 0 (mortgage paid off or not yet started), reduces to base_target.

    Conservative clamp: the result is floored at `base_target` so the adjusted
    threshold can never drop below the perpetual-SWR portfolio number. Without
    this clamp, when the real return `r` exceeds the effective drawdown rate
    during the mortgage years (i.e. high_gross < base_target * r), the PV
    formula produces a threshold *below* base_target — implying you could FIRE
    *earlier* with mortgage than without, which is mathematically valid but
    leans on optimistic sequence-of-returns assumptions and confuses the UI
    (the "Adjusted" age should always be ≥ the unadjusted SWR age).
    """
    if not _has_mortgage_data:
        return base_target
    _p_yr_l  = int(_pf_purchase_yrs) if _pf_purchase_yrs is not None else 0
    _po_yr_l = _p_yr_l + int(_pf_loan_term_years)
    n = max(_po_yr_l - yr, 0) if yr >= _p_yr_l else 0
    if n == 0:
        return base_target
    r = _real_r_for_pv
    if abs(r) < 1e-9:
        pv_threshold = high_gross * n + base_target
    else:
        pv_threshold = high_gross * (1.0 - (1.0 + r) ** (-n)) / r + base_target / (1.0 + r) ** n
    return max(base_target, pv_threshold)


def _kids_threshold_addition(yr: int) -> float:
    """Extra portfolio needed at year yr to fund remaining kids costs.

    Kids costs are finite (end when children turn 18), so we compute the
    present value of the remaining kids cost stream from year yr onward,
    discounted at the real portfolio return. This is more accurate than
    dividing by SWR (which implies costs last forever).
    """
    if not _kids_enabled or not _kids_annual_costs:
        return 0.0
    r = _real_r_for_pv
    pv = 0.0
    for future_yr, cost in _kids_annual_costs.items():
        offset = future_yr - yr
        if offset < 0:
            continue
        disc = (1.0 + r) ** offset if abs(r) > 1e-9 else 1.0
        pv += cost / disc
    return pv


def _full_adj_threshold(yr: int, base_target: float, high_gross: float) -> float:
    """Combined FIRE threshold: mortgage PV + kids cost PV + base SWR target.

    `_cashflow_mort_threshold` is already floored at `base_target`, and
    `_kids_threshold_addition` is non-negative, so the full adjusted threshold
    is guaranteed to be ≥ `base_target` — i.e. the Adjusted FIRE age can never
    come out earlier than the unadjusted SWR FIRE age. See the docstring on
    `_cashflow_mort_threshold` for the rationale.
    """
    return _cashflow_mort_threshold(yr, base_target, high_gross) + _kids_threshold_addition(yr)


def _best_mort_adj_fire_age(
    base_target: float,
    high_gross: float,
) -> tuple[int | None, str | None]:
    """
    Find the earliest FIRE age where the projected portfolio meets the cashflow-based
    mortgage-adjusted threshold. The threshold uses PV discounting to account for the
    elevated withdrawal (spending + mortgage repayments) during the remaining mortgage
    period, then the standard SWR portfolio requirement at payoff.
    """
    candidates = []
    for s in selected:
        col = f"{s}_Total"
        if col not in proj_df.columns:
            continue
        for yr, port in enumerate(proj_df[col]):
            if float(port) >= _cashflow_mort_threshold(yr, base_target, high_gross):
                candidates.append((current_age + yr, s))
                break
    if not candidates:
        return None, None
    return min(candidates, key=lambda x: x[0])


def _best_full_adj_fire_age(
    base_target: float,
    high_gross: float,
) -> tuple[int | None, str | None]:
    """Find earliest FIRE age meeting the combined mortgage + kids adjusted threshold."""
    candidates = []
    for s in selected:
        col = f"{s}_Total"
        if col not in proj_df.columns:
            continue
        for yr, port in enumerate(proj_df[col]):
            if float(port) >= _full_adj_threshold(yr, base_target, high_gross):
                candidates.append((current_age + yr, s))
                break
    if not candidates:
        return None, None
    return min(candidates, key=lambda x: x[0])


_show_adj_metrics = _has_mortgage_data or _kids_enabled
if _has_mortgage_data:
    median_age_adj, median_strat_adj = _best_mort_adj_fire_age(median_num_adj, median_gross_mort)
    lean_age_adj,   _                = _best_mort_adj_fire_age(lean_num_adj,   lean_gross_mort)
    fat_age_adj,    _                = _best_mort_adj_fire_age(fat_num_adj,    fat_gross_mort)
else:
    median_age_adj = median_strat_adj = lean_age_adj = fat_age_adj = None

# Full adjustment (mortgage + kids)
if _show_adj_metrics:
    median_age_full, median_strat_full = _best_full_adj_fire_age(median_num_adj, median_gross_mort)
    lean_age_full,   _                 = _best_full_adj_fire_age(lean_num_adj,   lean_gross_mort)
    fat_age_full,    _                 = _best_full_adj_fire_age(fat_num_adj,    fat_gross_mort)
else:
    median_age_full = median_strat_full = lean_age_full = fat_age_full = None

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
    f"Your FIRE number: **\\${median_num_adj:,.0f}** "
    f"(\\${median_spending:,}/yr after-tax · gross \\${median_gross:,.0f}/yr · "
    f"{'age ' + str(median_age) if median_age else 'not in horizon'})."
)

if _show_adj_metrics:
    _p_yr  = int(_pf_purchase_yrs) if (_has_mortgage_data and _pf_purchase_yrs is not None) else 0
    _po_yr = _p_yr + int(_pf_loan_term_years) if _has_mortgage_data else 0
    _payoff_age = current_age + _po_yr

    # Use fully-adjusted ages (mortgage + kids) for the displayed metrics
    _delay_med  = (median_age_full - median_age) if (median_age_full and median_age) else None
    _delay_lean = (lean_age_full   - lean_age)   if (lean_age_full   and lean_age)   else None
    _delay_fat  = (fat_age_full    - fat_age)    if (fat_age_full    and fat_age)    else None

    def _full_thresh_at_age(adj_age, base_target, high_gross):
        if adj_age is None:
            return None
        return _full_adj_threshold(adj_age - current_age, base_target, high_gross)

    _thresh_lean   = _full_thresh_at_age(lean_age_full,   lean_num_adj,   lean_gross_mort)
    _thresh_median = _full_thresh_at_age(median_age_full, median_num_adj, median_gross_mort)
    _thresh_fat    = _full_thresh_at_age(fat_age_full,    fat_num_adj,    fat_gross_mort)

    def _mort_yrs_remaining(adj_age):
        if adj_age is None or not _has_mortgage_data:
            return 0
        yr = adj_age - current_age
        return max(_po_yr - yr, 0) if yr >= _p_yr else 0

    def _kids_cost_at_age(adj_age):
        if adj_age is None or not _kids_enabled:
            return 0.0
        return _kids_annual_costs.get(adj_age - current_age, 0.0)

    _adj_label = "Mortgage + Kids Adjusted" if (_has_mortgage_data and _kids_enabled) \
                 else ("Mortgage-Adjusted" if _has_mortgage_data else "Kids-Adjusted")

    adj_a, adj_b, adj_c = st.columns(3)
    adj_a.metric(
        f"Lean FIRE ({_adj_label})",
        f"Age {lean_age_full}" if lean_age_full else "Not in horizon",
        delta=(f"+{_delay_lean} yr vs unadjusted" if (_delay_lean and _delay_lean > 0)
               else ("No delay" if _delay_lean == 0 else None)),
        delta_color="inverse" if (_delay_lean and _delay_lean > 0) else "normal",
        help=(f"Required portfolio: ~${_thresh_lean:,.0f}. "
              + (f"Mortgage: {_mort_yrs_remaining(lean_age_full)} yrs remaining. " if _has_mortgage_data else "")
              + (f"Kids cost at this age: ${_kids_cost_at_age(lean_age_full):,.0f}/yr (PV-discounted into threshold)." if _kids_enabled else "")
              ) if lean_age_full else "",
    )
    adj_b.metric(
        f"Your FIRE ({_adj_label})",
        f"Age {median_age_full}" if median_age_full else "Not in horizon",
        delta=(f"+{_delay_med} yr vs unadjusted" if (_delay_med and _delay_med > 0)
               else ("No delay" if _delay_med == 0 else None)),
        delta_color="inverse" if (_delay_med and _delay_med > 0) else "normal",
        help=(f"Required portfolio: ~${_thresh_median:,.0f}. "
              + (f"Mortgage: {_mort_yrs_remaining(median_age_full)} yrs remaining (${_mortgage_annual_repayment:,.0f}/yr). " if _has_mortgage_data else "")
              + (f"Kids cost at this age: ${_kids_cost_at_age(median_age_full):,.0f}/yr. " if _kids_enabled else "")
              + f"Drops to ${median_num_adj:,.0f} once mortgage + kids obligations end."
              ) if median_age_full else "",
    )
    adj_c.metric(
        f"Fat FIRE ({_adj_label})",
        f"Age {fat_age_full}" if fat_age_full else "Not in horizon",
        delta=(f"+{_delay_fat} yr vs unadjusted" if (_delay_fat and _delay_fat > 0)
               else ("No delay" if _delay_fat == 0 else None)),
        delta_color="inverse" if (_delay_fat and _delay_fat > 0) else "normal",
        help=(f"Required portfolio: ~${_thresh_fat:,.0f}. "
              + (f"Mortgage: {_mort_yrs_remaining(fat_age_full)} yrs remaining. " if _has_mortgage_data else "")
              + (f"Kids cost at this age: ${_kids_cost_at_age(fat_age_full):,.0f}/yr." if _kids_enabled else "")
              ) if fat_age_full else "",
    )

    _caption_parts = []
    if _has_mortgage_data:
        _caption_parts.append(
            f"🏠 **Mortgage:** portfolio must also fund \\${_mortgage_annual_repayment:,.0f}/yr "
            f"repayments until age {_payoff_age} (PV-discounted into threshold)."
        )
    if _kids_enabled:
        _peak_yr   = max(_kids_annual_costs, key=_kids_annual_costs.get) if _kids_annual_costs else 0
        _peak_cost = _kids_annual_costs.get(_peak_yr, 0)
        _kids_end  = max(_kids_annual_costs.keys()) if _kids_annual_costs else 0
        _caption_parts.append(
            f"👶 **Kids:** peak cost \\${_peak_cost:,.0f}/yr at year {_peak_yr} "
            f"(age {current_age + _peak_yr}). All kids independent by year {_kids_end} "
            f"(age {current_age + _kids_end}). PV of remaining kids costs added to FIRE threshold."
        )
    if _caption_parts:
        st.caption("  \n".join(_caption_parts))

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

# Fully-adjusted FIRE target: PV of mortgage repayments + PV of remaining kids costs
# + base SWR number.  Starts high, steps down as kids grow up and mortgage is paid off.
if _show_adj_metrics:
    _full_adj_targets = [
        _full_adj_threshold(yr, median_num_adj, median_gross_mort)
        for yr in range(len(proj_df))
    ]
    _adj_line_label = (
        "Mortgage + Kids Adjusted Target" if (_has_mortgage_data and _kids_enabled)
        else ("Mortgage-Adjusted Target" if _has_mortgage_data else "Kids-Adjusted Target")
    )
    fig.add_trace(go.Scatter(
        x=ages, y=_full_adj_targets,
        name=_adj_line_label,
        line=dict(color=COLORS["red"], width=2, dash="dot"),
        hovertemplate=f"{_adj_line_label}: $%{{y:,.0f}}<extra></extra>",
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
> ~\\${super_at_pres_C:,.0f} vs ~\\${super_at_pres_unlocked:,.0f} for A & B.

| | A ♻️ Sustainable | B 💥 Spend Everything | C 🏃 Non-Super First |
|---|---|---|---|
| **FIRE age** | {fire_age_target} | {fire_age_target} | **{fire_age_C_start}** |
| **Bridge spend** | \\${bridge_withdrawal:,.0f}/yr (your input) | \\${deplete_both_w:,.0f}/yr | \\${strat_C_bridge_w:,.0f}/yr |
| **Post-super** | \\${swr_post_w:,.0f}/yr SWR forever | Both to \\$0 by {sim_end_age} | \\${strat_C_post_w:,.0f}/yr to \\$0 by {sim_end_age} |
| **Super at {pres_age}** | ~\\${super_at_pres_unlocked:,.0f} | ~\\${super_at_pres_unlocked:,.0f} | ~\\${super_at_pres_C:,.0f} (fewer SGC yrs) |
| **Non-super at {pres_age}** | ~\\${_pres_ns_A:,.0f} (keeps compounding) | Depleted | ~\\$0 (intentionally) |
| **Residual wealth** | Large | \\$0 | \\$0 |

**Why Strategy C unlocks earlier FIRE:** You only need non-super to fund **\\${bridge_withdrawal:,.0f}/yr
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
                f"**\\${median_spending:,}/yr** does not need to include the \\${_ann_mortgage:,.0f}/yr "
                f"repayment. At payoff, you gain **\\${mort_monthly:,.0f}/mo** extra to invest."
            )
        else:
            st.warning(
                f"⚠️ **At your FIRE date (age {median_age}), your mortgage has "
                f"{payoff_age - median_age} years remaining** (\\${mort_monthly:,.0f}/mo = "
                f"\\${_ann_mortgage:,.0f}/yr). Your FIRE spending target should include this "
                f"repayment until age {payoff_age}, then drops by \\${_ann_mortgage:,.0f}/yr "
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
