"""Budget & Savings Rate — cashflow breakdown and FIRE horizon calculator.

Uses the Australian tax engine for precise after-tax income.
All projection figures can be shown in real (inflation-adjusted) dollars.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from engines.tax_engine import effective_tax_rate, CGTLaw, gross_withdrawal_for_net_spend
from engines.calculation_engine import preservation_age
from utils.colors import COLORS, CHART_LAYOUT, CHART_BG
from utils import shared_profile as profile
from utils.kids_engine import compute_kids_costs, kids_cost_label

st.set_page_config(page_title="Budget & Savings Rate", page_icon="💰", layout="wide")
profile.init()
st.title("💰 Budget & Savings Rate")
st.caption(
    "Step 0 of your journey: map where your money goes after tax, find your monthly surplus, "
    "and see how quickly you can reach financial independence."
)

_partnered = profile.is_partnered()

# ── Persistent local state (survives page navigation) ─────────────────────────
# Streamlit purges widget-bound `key=` values when you navigate away from a page.
# We store mutable page-local values in plain non-widget session-state dicts that
# Streamlit never cleans up.  Profile-backed fields (income, HECS, etc.) are NOT
# stored here — they re-read from the profile on every visit so cross-page edits
# always flow in.
_pf_mortgage_monthly = profile.get("pf_mortgage_monthly")
_pf_wants_purchase   = bool(profile.get("pf_wants_to_purchase"))
_mortgage_default    = int(_pf_mortgage_monthly) if (_pf_wants_purchase and _pf_mortgage_monthly is not None) else 2_200

if "bs_expenses" not in st.session_state:
    st.session_state["bs_expenses"] = {
        "rent_mortgage":  _mortgage_default,
        "utilities":      250,
        "insurance":      200,
        "phone":          100,
        "transport_fixed": 400,
        "other_fixed":    150,
        "groceries":      600,
        "dining_out":     400,
        "entertainment":  300,
        "clothing":       150,
        "health":         100,
        "travel":         300,
        "gifts_misc":     100,
    }

if "bs_sidebar" not in st.session_state:
    st.session_state["bs_sidebar"] = {
        "bonus_income":       5_000,
        "super_contribs":     15_000,
        "p_bonus_income":     0,
        "p_super_contribs":   int(profile.get("pf_partner_gross_income") * 0.12),
        "income_growth":      3.0,
        "annual_super_addition": 15_000,
    }

_e = st.session_state["bs_expenses"]
_s = st.session_state["bs_sidebar"]

# Sync rent/mortgage when the profile mortgage changes (e.g. after a Home Deposit export)
_last_seen_mortgage = st.session_state.get("_last_pf_mortgage_seen")
if _pf_wants_purchase and _pf_mortgage_monthly is not None:
    if _last_seen_mortgage != _pf_mortgage_monthly:
        _e["rent_mortgage"] = int(_pf_mortgage_monthly)
        st.session_state["_last_pf_mortgage_seen"] = _pf_mortgage_monthly

# ── Sidebar: income ───────────────────────────────────────────────────────────
with st.sidebar:
    profile.sidebar_summary()
    st.header("💼 Income")
    if _partnered:
        st.caption("👥 Couple mode. Tax is calculated individually for each partner.")
    else:
        st.caption("Pre-filled from your profile.")

    st.markdown("**🧑 You**")
    gross_income   = st.number_input("Gross Annual Salary (AUD)", min_value=0, step=5_000, value=profile.get("pf_gross_income"))
    bonus_income   = st.number_input("Annual Bonus / Side Income", min_value=0, value=_s["bonus_income"], step=1_000)
    _s["bonus_income"] = bonus_income
    super_contribs = st.number_input("Super Contributions/yr", min_value=0, value=_s["super_contribs"], step=1_000,
                                     help="Employer SG + any salary sacrifice")
    _s["super_contribs"] = super_contribs
    hecs_balance   = st.number_input("HECS-HELP Balance", min_value=0, value=profile.get("pf_hecs_balance"), step=1_000)
    private_cover  = st.checkbox("Private Hospital Cover", value=profile.get("pf_private_cover"))

    if _partnered:
        st.divider()
        st.markdown("**🧑‍🤝‍🧑 Your Partner**")
        p_gross_income   = st.number_input("Partner Gross Salary (AUD)", min_value=0, step=5_000, value=profile.get("pf_partner_gross_income"))
        p_bonus_income   = st.number_input("Partner Bonus / Side", min_value=0, value=_s["p_bonus_income"], step=1_000)
        _s["p_bonus_income"] = p_bonus_income
        p_super_contribs = st.number_input("Partner Super Contributions/yr", min_value=0,
                                           value=_s["p_super_contribs"],
                                           step=1_000,
                                           help="Defaults to 11.5% SG of partner salary. Add salary sacrifice if applicable.")
        _s["p_super_contribs"] = p_super_contribs
        p_hecs_balance   = st.number_input("Partner HECS-HELP Balance", min_value=0, value=profile.get("pf_partner_hecs_balance"), step=1_000)
        p_private_cover  = st.checkbox("Partner Private Hospital Cover", value=profile.get("pf_partner_private_cover"))
    else:
        p_gross_income = p_bonus_income = p_super_contribs = p_hecs_balance = 0
        p_private_cover = False

    st.divider()
    st.header("📈 Growth & Returns")
    # Clamp profile values to slider ranges to avoid out-of-range errors
    inflation_rate   = st.slider("Inflation (%/yr)",         0.0, 8.0,  min(8.0,  max(0.0,  float(profile.get("pf_inflation")))),        0.25) / 100.0
    portfolio_return = st.slider("Portfolio Return (%/yr)",  0.0, 15.0, min(15.0, max(0.0,  float(profile.get("pf_portfolio_return")))), 0.25) / 100.0
    income_growth    = st.slider("Annual Income Growth (%)", 0.0, 10.0, _s["income_growth"], 0.25) / 100.0
    _s["income_growth"] = income_growth * 100
    swr              = st.slider("Safe Withdrawal Rate (%)", 2.0, 6.0,  min(6.0,  max(2.0,  float(profile.get("pf_swr")))),              0.25) / 100.0

    st.divider()
    st.header("🏦 Existing Wealth")
    existing_portfolio = st.number_input("Existing Investment Portfolio ($)", min_value=0, value=profile.get("pf_portfolio"), step=5_000)
    _super_label       = "Household Super Balance ($)" if _partnered else "Your Super Balance ($)"
    _super_default     = profile.household_super_balance() if _partnered else profile.get("pf_super_balance")
    existing_super     = st.number_input(_super_label, min_value=0, value=int(_super_default), step=5_000,
                                         help="Combined super across both partners." if _partnered else None)
    if _partnered:
        st.caption(
            f"🧑 You: ${profile.get('pf_super_balance'):,.0f}  ·  "
            f"🧑‍🤝‍🧑 Partner: ${profile.get('pf_partner_super_balance'):,.0f}  ·  "
            f"Combined: ${profile.household_super_balance():,.0f}"
        )
    annual_super_addition = st.number_input(
        "Total Super Contributions/yr ($)", min_value=0, value=_s["annual_super_addition"], step=1_000,
        help="Employer SG + salary sacrifice for the household. Used in FIRE timeline to project super balance alongside portfolio.",
    )
    _s["annual_super_addition"] = annual_super_addition

# ── Tax calculation ───────────────────────────────────────────────────────────
# Australian income tax is individual. For couples we run effective_tax_rate
# once per partner and sum the results.
tax_you = effective_tax_rate(
    gross_income + bonus_income, super_contribs, hecs_balance, 0, 0, CGTLaw.CURRENT,
    has_private_hospital_cover=private_cover,
)

if _partnered:
    tax_partner = effective_tax_rate(
        p_gross_income + p_bonus_income, p_super_contribs, p_hecs_balance, 0, 0, CGTLaw.CURRENT,
        has_private_hospital_cover=p_private_cover,
    )
else:
    tax_partner = {"net_income": 0, "income_tax": 0,
                   "medicare_levy": 0, "medicare_levy_surcharge": 0, "hecs_repayment": 0}

net_annual  = tax_you["net_income"] + tax_partner["net_income"]
net_monthly = net_annual / 12.0

income_tax_annual  = tax_you["income_tax"]      + tax_partner["income_tax"]
medicare_annual    = (tax_you["medicare_levy"]  + tax_you["medicare_levy_surcharge"]
                      + tax_partner["medicare_levy"] + tax_partner["medicare_levy_surcharge"])
hecs_annual        = tax_you["hecs_repayment"]  + tax_partner["hecs_repayment"]

# ── Expense inputs in main area ───────────────────────────────────────────────
st.subheader("Monthly Expenses")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Fixed Expenses**")
    rent_mortgage = st.number_input("Rent / Mortgage ($)", min_value=0, value=_e["rent_mortgage"], step=100)
    _e["rent_mortgage"] = rent_mortgage
    if _pf_wants_purchase and _pf_mortgage_monthly is not None:
        _purchase_yrs = profile.get("pf_purchase_years_from_now")
        _yr_note = f" (planned in ~{int(_purchase_yrs)} yr(s))" if _purchase_yrs else ""
        st.caption(f"💡 Pre-filled from your Home Deposit plan — planned mortgage of ${int(_pf_mortgage_monthly):,}/mo{_yr_note}.")
    utilities       = st.number_input("Utilities (elec/gas/internet)", min_value=0, value=_e["utilities"],      step=25)
    _e["utilities"] = utilities
    insurance       = st.number_input("Insurance (all policies)",       min_value=0, value=_e["insurance"],     step=25)
    _e["insurance"] = insurance
    phone           = st.number_input("Phone / Subscriptions",          min_value=0, value=_e["phone"],         step=10)
    _e["phone"] = phone
    transport_fixed = st.number_input("Transport (loan/rego/fuel)",     min_value=0, value=_e["transport_fixed"], step=50)
    _e["transport_fixed"] = transport_fixed
    other_fixed     = st.number_input("Other Fixed ($)",                min_value=0, value=_e["other_fixed"],   step=25)
    _e["other_fixed"] = other_fixed

with col2:
    st.markdown("**Variable / Discretionary**")
    groceries       = st.number_input("Groceries ($)",                  min_value=0, value=_e["groceries"],    step=50)
    _e["groceries"] = groceries
    dining_out      = st.number_input("Dining Out / Takeaway ($)",      min_value=0, value=_e["dining_out"],   step=50)
    _e["dining_out"] = dining_out
    entertainment   = st.number_input("Entertainment / Hobbies ($)",   min_value=0, value=_e["entertainment"], step=50)
    _e["entertainment"] = entertainment
    clothing        = st.number_input("Clothing / Personal ($)",        min_value=0, value=_e["clothing"],     step=25)
    _e["clothing"] = clothing
    health          = st.number_input("Health / Fitness ($)",           min_value=0, value=_e["health"],       step=25)
    _e["health"] = health
    travel          = st.number_input("Travel / Holidays ($)",          min_value=0, value=_e["travel"],       step=50)
    _e["travel"] = travel
    gifts_misc      = st.number_input("Gifts / Misc ($)",               min_value=0, value=_e["gifts_misc"],   step=25)
    _e["gifts_misc"] = gifts_misc

# ── Core calculations ─────────────────────────────────────────────────────────
monthly_fixed    = rent_mortgage + utilities + insurance + phone + transport_fixed + other_fixed
monthly_variable = groceries + dining_out + entertainment + clothing + health + travel + gifts_misc
monthly_expenses = monthly_fixed + monthly_variable
monthly_savings  = net_monthly - monthly_expenses
savings_rate     = monthly_savings / net_monthly if net_monthly > 0 else 0.0

annual_savings   = monthly_savings * 12
# FIRE number = annual spending ÷ SWR (spending-based, not income-based)
annual_spending  = monthly_expenses * 12
fire_number      = (annual_spending / swr) if swr > 0 else 0

st.divider()

# ── Key metrics ───────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric(
    "Household Take-Home" if _partnered else "Monthly Take-Home",
    f"${net_monthly:,.0f}",
    delta=f"${net_annual:,.0f}/yr",
    delta_color="off",
)
m2.metric(
    "Monthly Expenses",
    f"${monthly_expenses:,.0f}",
    delta=f"${monthly_expenses * 12:,.0f}/yr",
    delta_color="off",
)
m3.metric(
    "Monthly Savings",
    f"${monthly_savings:,.0f}",
    delta=f"{savings_rate * 100:.1f}% savings rate",
    delta_color="normal" if monthly_savings > 0 else "inverse",
)
# Mortgage timing — defined here so the FIRE number help text and later the
# FIRE timeline both have access.  _pf_wants_purchase and _pf_mortgage_monthly
# are read from the profile at the top of this file.
_mort_p_yr   = int(profile.get("pf_purchase_years_from_now") or 0)
_mort_term   = int(profile.get("pf_loan_term_years") or 0)
_mort_po_yr  = _mort_p_yr + _mort_term
_has_mort_data = (
    _pf_wants_purchase
    and _pf_mortgage_monthly is not None
    and _mort_term > 0
    and _mort_po_yr > 0
)
_mortgage_annual         = float(_pf_mortgage_monthly) * 12.0 if _has_mort_data else 0.0
_spending_post_payoff    = max(annual_spending - _mortgage_annual, annual_spending * 0.5)
_fire_number_post_payoff = _spending_post_payoff / swr if swr > 0 else 0.0

_fire_num_help = (
    f"Portfolio needed so {swr*100:.1f}% annual withdrawal covers your ${annual_spending:,.0f}/yr expenses. "
    + (
        f"Because your budget includes a ${_mortgage_annual:,.0f}/yr mortgage, the FIRE timeline uses a "
        f"cashflow model: higher threshold (spending+mortgage) during the loan term, "
        f"dropping to ${_fire_number_post_payoff:,.0f} once paid off at year {_mort_po_yr}."
        if _has_mort_data else ""
    )
)
m4.metric(
    f"FIRE Number ({swr*100:.1f}% SWR)",
    f"${fire_number:,.0f}",
    help=_fire_num_help,
)

# Per-partner breakdown (visible in couple mode only)
if _partnered:
    you_net      = tax_you["net_income"]
    partner_net  = tax_partner["net_income"]
    you_tax      = tax_you["income_tax"] + tax_you["medicare_levy"] + tax_you["medicare_levy_surcharge"] + tax_you["hecs_repayment"]
    partner_tax  = tax_partner["income_tax"] + tax_partner["medicare_levy"] + tax_partner["medicare_levy_surcharge"] + tax_partner["hecs_repayment"]

    st.caption("**Per-Partner Income Breakdown**")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown(
            f"🧑 **You**  \n"
            f"Gross: ${gross_income + bonus_income:,.0f}/yr  \n"
            f"Total Tax + HECS: ${you_tax:,.0f}/yr  \n"
            f"After-Tax: **${you_net:,.0f}/yr**  ·  ${you_net / 12:,.0f}/mo"
        )
    with pc2:
        st.markdown(
            f"🧑‍🤝‍🧑 **Partner**  \n"
            f"Gross: ${p_gross_income + p_bonus_income:,.0f}/yr  \n"
            f"Total Tax + HECS: ${partner_tax:,.0f}/yr  \n"
            f"After-Tax: **${partner_net:,.0f}/yr**  ·  ${partner_net / 12:,.0f}/mo"
        )

# ── Export to Profile ─────────────────────────────────────────────────────────
# Push back EVERY profile-backed input the user can edit on this page so cross-
# page edits round-trip cleanly. Bonus income is page-local and intentionally
# NOT folded into ``pf_gross_income`` — that would corrupt the profile salary
# every time the user revisited this page.
exp_left, exp_right = st.columns([3, 1])
with exp_left:
    st.info(
        f"**Monthly Savings = ${monthly_savings:,.0f}**  ·  "
        f"Annual Spending = ${annual_spending:,.0f}  ·  "
        f"FIRE Number = ${fire_number:,.0f}  \n"
        "📤 **Export** to push these to: **Home Deposit** (deposit timeline), "
        "**FIRE Scenarios** (DCA + spending target), and **Retirement Drawdown** (withdrawal amount)."
    )
with exp_right:
    export_values: dict[str, object] = {
        "pf_monthly_savings":      max(monthly_savings, 0),
        "pf_annual_spending":      annual_spending,
        "pf_current_housing_cost": rent_mortgage,
        "pf_gross_income":         gross_income,
        "pf_hecs_balance":         hecs_balance,
        "pf_private_cover":        private_cover,
        "pf_inflation":            inflation_rate * 100,
        "pf_portfolio_return":     portfolio_return * 100,
        "pf_swr":                  swr * 100,
        "pf_portfolio":            existing_portfolio,
        "pf_super_balance":        existing_super,
    }
    if _partnered:
        export_values.update({
            "pf_partner_gross_income":  p_gross_income,
            "pf_partner_hecs_balance":  p_hecs_balance,
            "pf_partner_private_cover": p_private_cover,
        })

    profile.export_button(
        "Export Savings & Spending to Profile",
        export_values,
        help="Sends every income, savings, and assumption value above to the "
             "shared profile so other pages stay in sync. Page-local overrides "
             "(bonus income, super contribution split) stay on this page.",
    )

if monthly_savings < 0:
    st.error(
        f"🚨 **Spending exceeds income** by ${-monthly_savings:,.0f}/month. "
        f"Reduce expenses or increase income before investing."
    )
elif savings_rate < 0.10:
    st.warning(
        f"⚠️ **Low savings rate ({savings_rate*100:.1f}%)** - aim for at least 20% to build "
        f"meaningful wealth. Small cuts to discretionary spending compound significantly."
    )
elif savings_rate < 0.20:
    st.info(
        f"ℹ️ **Savings rate: {savings_rate*100:.1f}%.** You're saving, but increasing this to 20%+ "
        f"will materially accelerate your timeline to FIRE."
    )
else:
    st.success(
        f"✅ **Strong savings rate: {savings_rate*100:.1f}%.** "
        f"You're on a solid path to wealth accumulation."
    )

st.divider()

# ── Budget waterfall / breakdown chart ───────────────────────────────────────
st.subheader("Monthly Income Breakdown")

all_labels = [
    "Income Tax", "Medicare + MLS", "HECS",
    "Rent / Mortgage", "Utilities", "Insurance", "Phone/Subs", "Transport", "Other Fixed",
    "Groceries", "Dining Out", "Entertainment", "Clothing", "Health", "Travel", "Gifts/Misc",
    "💰 Saved",
]
all_values = [
    income_tax_annual / 12, medicare_annual / 12, hecs_annual / 12,
    rent_mortgage, utilities, insurance, phone, transport_fixed, other_fixed,
    groceries, dining_out, entertainment, clothing, health, travel, gifts_misc,
    max(monthly_savings, 0),
]
bar_colors = (
    [COLORS["red"]] * 3 +
    [COLORS["orange"]] * 6 +
    [COLORS["yellow"]] * 7 +
    [COLORS["mint"] if monthly_savings >= 0 else COLORS["red"]]
)

fig_budget = go.Figure(go.Bar(
    x=all_labels, y=all_values,
    marker_color=bar_colors,
    text=[f"${v:,.0f}" for v in all_values],
    textposition="outside",
))
fig_budget.update_layout(
    **CHART_LAYOUT,
    xaxis_title="", yaxis_title="Monthly (AUD)",
    height=420, showlegend=False,
    xaxis=dict(tickangle=-35),
    yaxis=dict(range=[0, max(all_values) * 1.18 if all_values else 1]),
)
st.plotly_chart(fig_budget, width="stretch")

st.divider()

# ── 50/30/20 rule benchmarking ────────────────────────────────────────────────
st.subheader("50 / 30 / 20 Rule Benchmark")
needs_pct   = monthly_fixed / net_monthly * 100 if net_monthly > 0 else 0
wants_pct   = monthly_variable / net_monthly * 100 if net_monthly > 0 else 0
savings_pct = max(monthly_savings / net_monthly * 100, 0) if net_monthly > 0 else 0

b1, b2, b3 = st.columns(3)
b1.metric("Needs (Fixed)", f"{needs_pct:.1f}%",
          delta="Target ≤ 50%", delta_color="normal" if needs_pct <= 50 else "inverse")
b2.metric("Wants (Variable)", f"{wants_pct:.1f}%",
          delta="Target ≤ 30%", delta_color="normal" if wants_pct <= 30 else "inverse")
b3.metric("Savings / Invest", f"{savings_pct:.1f}%",
          delta="Target ≥ 20%", delta_color="normal" if savings_pct >= 20 else "inverse")

# Donut chart
fig_donut = go.Figure(go.Pie(
    labels=["Fixed Needs", "Variable Wants", "Saved / Invested"],
    values=[max(monthly_fixed, 0), max(monthly_variable, 0), max(monthly_savings, 0)],
    marker_colors=[COLORS["orange"], COLORS["yellow"], COLORS["mint"]],
    hole=0.5,
    textinfo="percent+label",
))
fig_donut.update_layout(
    template="plotly_white", paper_bgcolor=CHART_BG,
    height=320, showlegend=False,
)
st.plotly_chart(fig_donut, width="stretch")

st.divider()

# ── FIRE timeline ─────────────────────────────────────────────────────────────
st.subheader("Path to Financial Independence")

real_return = (1 + portfolio_return) / (1 + inflation_rate) - 1

if bool(profile.get("pf_kids_enabled")):
    _nk   = int(profile.get("pf_num_kids") or 2)
    _nkst = {1: "1 child", 2: "2 children", 3: "3 children"}.get(_nk, "children")
    st.info(
        f"👶 **Kids plan active** — {_nkst}, "
        f"{kids_cost_label(str(profile.get('pf_kids_schooling') or 'public'))} schooling. "
        "Kids costs reduce investable savings each year in the FIRE timeline below. "
        "Configure on the **Kids & Family** page."
    )

# Preservation age and current age — used to gate illiquid super in the FIRE timeline
_current_age = int(profile.get("pf_age") or 30)
_pres_age    = preservation_age(int(profile.get("pf_birth_year") or (2026 - _current_age)))

_real_r_pv = max(real_return, 0.01)   # keep positive so PV formula is well-defined

# Pre-compute the gross withdrawal needed during the mortgage phase (computed once, not per call)
_high_gross_budget = (
    gross_withdrawal_for_net_spend(annual_spending + _mortgage_annual)
    if _has_mort_data else 0.0
)

# Kids annual costs — read from profile if kids plan is active
_kids_enabled_budget = bool(profile.get("pf_kids_enabled"))
_kids_annual_budget: dict[int, float] = {}
if _kids_enabled_budget:
    _k_births_b = [
        int(profile.get("pf_kid1_birth_yr_from_now") or 3),
        int(profile.get("pf_kid2_birth_yr_from_now") or 6),
        int(profile.get("pf_kid3_birth_yr_from_now") or 9),
    ]
    _kcs = compute_kids_costs(
        num_kids=int(profile.get("pf_num_kids") or 2),
        birth_yrs_from_now=_k_births_b,
        schooling=str(profile.get("pf_kids_schooling") or "public"),
        private_school_annual=float(profile.get("pf_kids_private_school_annual") or 20_000),
        private_highschool_annual=float(profile.get("pf_kids_private_highschool_annual") or 30_000),
        childcare_annual_per_child=float(profile.get("pf_kids_childcare_annual") or 12_000),
        setup_cost_per_child=float(profile.get("pf_kids_setup_cost") or 7_500),
        gross_income=float(gross_income),
        partner_gross_income=float(p_gross_income if _partnered else 0),
        leave_weeks=int(profile.get("pf_parental_leave_weeks") or 18),
        partner_leave_weeks=int(profile.get("pf_parental_leave_partner_weeks") or 4),
        leave_income_pct=float(profile.get("pf_parental_leave_income_pct") or 50),
        bigger_house_monthly_extra=float(profile.get("pf_kids_bigger_house_extra_monthly") or 0),
        partner_career_break_years=int(profile.get("pf_partner_career_break_years") or 0),
        horizon=82,
    )
    _kids_annual_budget = _kcs.as_dict()


def _cashflow_target_at_yr(yr: int) -> float:
    """Cashflow-based FIRE target at projection year yr.

    Matches FIRE Scenarios logic: PV of elevated spending (living + mortgage) for n remaining
    mortgage years plus PV of the post-payoff SWR number, all in real dollars.
    When no mortgage (or already paid), returns the standard fire_number.
    """
    if not _has_mort_data:
        return fire_number
    n = max(_mort_po_yr - yr, 0) if yr >= _mort_p_yr else 0
    if n == 0:
        return _fire_number_post_payoff
    r = _real_r_pv
    return _high_gross_budget * (1.0 - (1.0 + r) ** (-n)) / r + _fire_number_post_payoff / (1.0 + r) ** n


def years_to_fire(save_rate: float) -> float | None:
    """Years to reach FIRE number given a savings rate.

    Fixes applied:
    - Target is fire_number (annual_spending / swr), not annual_income / swr (#3).
    - Super is only counted once the user reaches preservation age (#4).
    - Super contributions grow with income growth (approximating rising SG on rising salary) (#11).
    - Target is cashflow-based: accounts for remaining mortgage repayments at each projection year.
    """
    if save_rate <= 0:
        return None
    portfolio     = float(existing_portfolio)
    super_bal_val = float(existing_super)
    annual_inc    = net_annual
    current_sg    = float(annual_super_addition)   # grows each year with salary
    for yr in range(1, 81):
        annual_inc    *= (1 + income_growth)
        annual_save    = annual_inc * save_rate
        # Deduct kids costs from investable savings for this year
        kids_cost_yr   = _kids_annual_budget.get(yr, 0.0)
        annual_save    = max(annual_save - kids_cost_yr, 0.0)
        portfolio      = portfolio * (1 + portfolio_return) + annual_save
        super_bal_val  = super_bal_val * (1 + portfolio_return) + current_sg
        current_sg    *= (1 + income_growth)       # SG is % of salary — grows with income
        # Super only accessible at preservation age; exclude it before then
        accessible_super = super_bal_val if (_current_age + yr) >= _pres_age else 0.0
        combined = portfolio + accessible_super
        if combined >= _cashflow_target_at_yr(yr):
            return yr
    return None

# Range of savings rates to explore
rate_range = [r / 100 for r in range(5, 75, 5)]
ytf_vals = [years_to_fire(r) for r in rate_range]

current_ytf = years_to_fire(savings_rate)

# Plot only the savings rates where FIRE is actually reachable within the 80-year
# horizon. Unreachable rates render as a gap (using NaN) instead of being pinned
# to an arbitrary sentinel value that looks like real data.
_x_pct = [r * 100 for r in rate_range]
_y_yrs = [y if y is not None else float("nan") for y in ytf_vals]

fig_fire = go.Figure()
fig_fire.add_trace(go.Scatter(
    x=_x_pct, y=_y_yrs,
    mode="lines+markers",
    line=dict(color=COLORS["mint"], width=2),
    marker=dict(color=COLORS["mint"], size=6),
    name="Years to FIRE",
    connectgaps=False,
    hovertemplate="Save %{x:.0f}% → %{y:.0f} years<extra></extra>",
))

# Shade the "unreachable" zone for any savings rate where the model didn't converge
# within the planning horizon. This is much more honest than plotting 80.
_unreachable_rates = [r * 100 for r, y in zip(rate_range, ytf_vals) if y is None]
if _unreachable_rates:
    fig_fire.add_vrect(
        x0=0, x1=max(_unreachable_rates) + 2.5,
        fillcolor=COLORS["red"], opacity=0.08, line_width=0,
        annotation_text="FIRE not reached within 80 years",
        annotation_position="top left",
        annotation_font_color=COLORS["red"],
    )

if savings_rate > 0 and current_ytf is not None:
    fig_fire.add_vline(
        x=savings_rate * 100,
        line_dash="dash", line_color=COLORS["yellow"],
        annotation_text=f"You ({savings_rate*100:.0f}% → {current_ytf}yr)",
        annotation_font_color=COLORS["yellow"],
    )
fig_fire.add_hline(y=25, line_dash="dot", line_color=COLORS["muted"],
                   annotation_text="25yr horizon", annotation_font_color=COLORS["muted"])

fig_fire.update_layout(
    **CHART_LAYOUT,
    xaxis_title="Savings Rate (%)",
    yaxis_title="Years to Financial Independence",
    height=400,
    yaxis=dict(rangemode="tozero"),
)
st.plotly_chart(fig_fire, width="stretch")

if current_ytf:
    st.info(f"📅 At your current savings rate of **{savings_rate*100:.1f}%**, "
            f"you could reach FIRE in approximately **{current_ytf} years**.")
else:
    st.warning("⚠️ At your current savings rate, FIRE is not modelled within 80 years. "
               "Increase your savings rate or reduce desired spending.")

st.divider()

# ── Wealth accumulation scenarios ─────────────────────────────────────────────
st.subheader("Wealth Accumulation: Three Scenarios")

# Floor each scenario rate at 0 — a negative savings rate would imply drawing down
# the portfolio every year, which would otherwise plot a physically impossible
# negative portfolio balance.
scenario_rates = {
    f"Current Rate ({savings_rate*100:.0f}%)":  max(savings_rate, 0.0),
    "Stretch (+10%)":   min(max(savings_rate + 0.10, 0.0), 0.95),
    "Optimised (+20%)": min(max(savings_rate + 0.20, 0.0), 0.95),
}
scenario_colors = [COLORS["blue"], COLORS["mint"], COLORS["purple"]]

fig_wealth = go.Figure()
horizon_yrs = 30
_depletion_notes: list[str] = []
for (scenario_name, rate), color in zip(scenario_rates.items(), scenario_colors):
    portfolio_traj = [float(existing_portfolio)]
    annual_inc = net_annual
    bal = float(existing_portfolio)
    depleted_year: int | None = None
    for yr in range(1, horizon_yrs + 1):
        annual_inc *= (1 + income_growth)
        annual_save = annual_inc * rate
        bal = bal * (1 + portfolio_return) + annual_save
        if bal <= 0 and depleted_year is None:
            depleted_year = yr
            bal = 0.0
        bal = max(bal, 0.0)
        cpi = (1 + inflation_rate) ** yr
        portfolio_traj.append(bal / cpi)  # real terms

    fig_wealth.add_trace(go.Scatter(
        x=list(range(horizon_yrs + 1)),
        y=portfolio_traj,
        name=scenario_name,
        line=dict(color=color, width=2),
    ))
    if depleted_year is not None:
        _depletion_notes.append(f"{scenario_name} depletes at year {depleted_year}")

fire_real = fire_number
fig_wealth.add_hline(
    y=fire_real, line_dash="dash", line_color=COLORS["orange"],
    annotation_text=f"FIRE Target ${fire_real:,.0f} (real)",
    annotation_font_color=COLORS["orange"],
)
fig_wealth.update_layout(
    **CHART_LAYOUT,
    xaxis_title="Years from Now",
    yaxis_title="Portfolio Value (Real, Inflation-Adjusted AUD)",
    height=420,
    yaxis=dict(rangemode="tozero"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_wealth, width="stretch")

if _depletion_notes:
    st.warning(
        "⚠️ **Portfolio depletion detected.** "
        + " · ".join(_depletion_notes) + ". "
        "This happens when your savings rate is at or below zero. "
        "Restore a positive monthly surplus before projecting further."
    )

# ── Methodology ───────────────────────────────────────────────────────────────
with st.expander("📋 Methodology & Assumptions"):
    st.markdown(f"""
| Parameter | Value |
|---|---|
| Gross Income | ${gross_income + bonus_income:,.0f}/yr |
| After-Tax Income | ${net_annual:,.0f}/yr |
| Monthly Expenses | ${monthly_expenses:,.0f} |
| Annual Spending | ${annual_spending:,.0f} |
| Monthly Savings | ${monthly_savings:,.0f} |
| Savings Rate | {savings_rate*100:.1f}% |
| FIRE Number | ${fire_number:,.0f} (annual spending ÷ {swr*100:.1f}% SWR) |
| Portfolio Return | {portfolio_return*100:.2f}%/yr nominal |
| Inflation | {inflation_rate*100:.2f}%/yr |
| Real Return | {real_return*100:.2f}%/yr |
| Income Growth | {income_growth*100:.2f}%/yr |

**FIRE calculation** uses annual spending ÷ SWR as the target (not income ÷ SWR).
Super is gated behind your preservation age ({_pres_age}) — it is only counted once you reach
that age. Super contributions in the timeline grow annually with income growth, approximating
the rising SG on a growing salary.
{"**Mortgage adjustment:** the timeline uses a cashflow PV model — the required portfolio at each year accounts for the remaining mortgage repayments (${:,.0f}/yr) plus the lower post-payoff spending number (${:,.0f}) at payoff year {}.".format(_mortgage_annual, _fire_number_post_payoff, _mort_po_yr) if _has_mort_data else ""}

**Tax** uses 2024-25 Australian brackets with Stage 3 cuts, LITO, Medicare levy, MLS, and HECS.

⚠️ This is a planning tool. Future returns are not guaranteed.
""")
