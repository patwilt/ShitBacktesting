"""Home Deposit Planner — how much to save each month to buy a house.

All dollar projections are available in nominal and real (inflation-adjusted) terms.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from engines.tax_engine import effective_tax_rate, CGTLaw
from utils.colors import COLORS, CHART_LAYOUT
from utils import shared_profile as profile

st.set_page_config(page_title="Home Deposit Planner", page_icon="🏡", layout="wide")
profile.init()
st.title("🏡 Home Deposit Planner")
st.caption(
    "Step 4 of your journey: calculate exactly how long it takes to save a deposit, "
    "accounting for property price growth and inflation in real-dollar terms."
)

_partnered = profile.is_partnered()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    profile.sidebar_summary()

    st.header("💼 Income & Tax")
    if _partnered:
        st.caption("👥 Couple mode. Both partners' incomes are pooled to save the deposit.")
    else:
        st.caption("Pre-filled from your profile. Override locally here.")

    st.markdown("**🧑 You**")
    gross_income  = st.number_input("Gross Annual Income (AUD)", min_value=0, step=5_000, value=profile.get("pf_gross_income"))
    hecs_balance  = st.number_input("HECS-HELP Balance (AUD)",   min_value=0, step=1_000, value=profile.get("pf_hecs_balance"))
    private_cover = st.checkbox("Private Hospital Cover", value=profile.get("pf_private_cover"))

    if _partnered:
        st.markdown("**🧑‍🤝‍🧑 Your Partner**")
        p_gross_income  = st.number_input("Partner Gross Income (AUD)", min_value=0, step=5_000, value=profile.get("pf_partner_gross_income"))
        p_hecs_balance  = st.number_input("Partner HECS-HELP (AUD)",   min_value=0, step=1_000, value=profile.get("pf_partner_hecs_balance"))
        p_private_cover = st.checkbox("Partner Private Hospital Cover", value=profile.get("pf_partner_private_cover"))
    else:
        p_gross_income = p_hecs_balance = 0
        p_private_cover = False

    st.divider()
    st.header("🏠 Property Target")

    city_presets = {
        "Sydney":    (1_550_000, 6.5),
        "Melbourne": (980_000,   5.5),
        "Brisbane":  (900_000,   7.0),
        "Perth":     (750_000,   7.5),
        "Adelaide":  (720_000,   6.5),
        "Custom":    (800_000,   4.0),
    }
    city = st.selectbox("City / Market Preset", list(city_presets.keys()), index=5)
    default_price, default_growth = city_presets[city]

    property_price_today = st.number_input(
        "Property Price (Today's Dollars, AUD)",
        min_value=100_000,
        value=default_price,
        step=25_000,
        key=f"prop_price_{city}",
    )
    deposit_pct = st.select_slider(
        "Target Deposit %",
        options=[5, 10, 15, 20, 25, 30, 35, 40, 50],
        value=20,
        help="20% avoids LMI. Higher deposits reduce the loan size and monthly repayments.",
    )
    stamp_duty_pct = st.slider(
        "Stamp Duty + Costs (%)", 0.0, 6.0, 3.5, 0.25,
        help="Stamp duty varies by state and first-home buyer status. Typical 3–5%."
    )

    st.divider()
    st.header("📈 Growth & Returns")
    property_growth_rate = st.slider(
        "Property Price Growth (%/yr)", 0.0, 12.0, float(default_growth), 0.25,
        key=f"prop_growth_{city}",
    ) / 100.0
    savings_return = st.slider(
        "Savings Return (%/yr)",
        0.0, 10.0, 4.5, 0.25,
        help="Return on your deposit savings. HISA rate, bonds, or conservative ETFs."
    ) / 100.0
    inflation_rate = st.slider(
        "Inflation Rate (%/yr)", 0.0, 8.0,
        min(8.0, max(0.0, float(profile.get("pf_inflation")))), 0.25
    ) / 100.0

    st.divider()
    st.header("📈 Salary Growth")
    st.caption("Pre-filled from your profile. Set it once on the Home page and it flows everywhere.")
    _sg_default = float(profile.get("pf_salary_growth") or 3.0)
    salary_growth_rate = st.slider(
        "Annual Salary Growth (%/yr)", 0.0, 8.0,
        min(8.0, max(0.0, _sg_default)), 0.25,
        help="How fast your gross income grows each year (nominal). "
             "Set once on the Home page; overridable locally here.",
    ) / 100.0
    _pf_ceiling = profile.get("pf_salary_ceiling")
    _show_ceiling = st.toggle(
        "Advanced: Set Salary Ceiling", value=_pf_ceiling is not None,
        help="Define a maximum salary in today's purchasing power. "
             "Pre-filled from the Home page ceiling if set.",
    )
    salary_ceiling_today: float | None = None
    if _show_ceiling:
        _ceil_default = int(_pf_ceiling) if _pf_ceiling is not None else int(max(gross_income * 2, gross_income + 50_000))
        salary_ceiling_today = float(st.number_input(
            "Salary Ceiling (Today's Dollars, AUD)",
            min_value=int(gross_income) if gross_income > 0 else 0,
            value=_ceil_default,
            step=10_000,
            help="Maximum salary in today's purchasing power. "
                 "Automatically indexed to inflation each year.",
        ))

    st.divider()
    st.header("🏦 Mortgage")
    mortgage_rate = st.slider(
        "Mortgage Interest Rate (%/yr)", 3.0, 12.0, 6.0, 0.25,
        help="Expected variable or fixed rate when you take out the loan. "
             "Australian average has been 5.5–7% in recent years.",
    ) / 100.0
    loan_term_years = st.select_slider(
        "Loan Term (Years)", options=[10, 15, 20, 25, 30], value=30,
        help="Standard Australian home loan term. 30 years gives the lowest monthly payment.",
    )

    st.divider()
    st.header("💰 Your Savings")
    current_savings = st.number_input(
        "Deposit Savings Already Set Aside (AUD)", min_value=0, value=30_000, step=5_000,
        help="Cash or low-risk savings already earmarked for the deposit.",
    )
    _budget_monthly = profile.get("pf_monthly_savings")
    _monthly_default = int(max(_budget_monthly, 0)) if _budget_monthly is not None else 2_000
    monthly_savings_available = st.number_input(
        "Monthly Savings Available for Deposit ($)", min_value=0,
        value=_monthly_default, step=100,
        help="How much you can put toward the deposit each month. "
             "Pre-filled from your Budget & Savings page — run that page first for the most accurate number.",
    )
    if _budget_monthly is not None:
        st.caption(f"💡 Pre-filled from Budget: **${int(_budget_monthly):,}/mo** surplus.")
    target_years = st.slider("Goal: Save Deposit Within (Years)", 1, 20, 5)

# ── Tax calculations ──────────────────────────────────────────────────────────
# Tax is individual in Australia; for couples, run effective_tax_rate per partner.
# Keep ``your_gross_income`` separate from the household sum so we can export
# each partner's salary back to the profile cleanly.
your_gross_income = gross_income
tax_result = effective_tax_rate(
    gross_income, 0, hecs_balance, 0, 0, CGTLaw.CURRENT,
    has_private_hospital_cover=private_cover,
)

if _partnered:
    tax_partner_result = effective_tax_rate(
        p_gross_income, 0, p_hecs_balance, 0, 0, CGTLaw.CURRENT,
        has_private_hospital_cover=p_private_cover,
    )
    net_annual = tax_result["net_income"] + tax_partner_result["net_income"]
    # Sum tax/medicare/hecs for the chart breakdown later
    tax_result = {
        "income_tax":              tax_result["income_tax"]              + tax_partner_result["income_tax"],
        "medicare_levy":           tax_result["medicare_levy"]           + tax_partner_result["medicare_levy"],
        "medicare_levy_surcharge": tax_result["medicare_levy_surcharge"] + tax_partner_result["medicare_levy_surcharge"],
        "hecs_repayment":          tax_result["hecs_repayment"]          + tax_partner_result["hecs_repayment"],
        "net_income":              net_annual,
    }
    household_gross = gross_income + p_gross_income
else:
    net_annual = tax_result["net_income"]
    household_gross = gross_income

# Used for chart y-axis scaling.
gross_income_for_chart = household_gross
net_monthly = net_annual / 12.0

# ── Core deposit math ─────────────────────────────────────────────────────────
# Property price inflates at property_growth_rate; savings grow at savings_return
# We want: FV_savings >= FV_property * (deposit_pct/100 + stamp_duty_pct/100)

total_upfront_pct = deposit_pct / 100.0 + stamp_duty_pct / 100.0


def future_property_price(yrs: float) -> float:
    return property_price_today * (1 + property_growth_rate) ** yrs


def target_deposit_future(yrs: float) -> float:
    return future_property_price(yrs) * total_upfront_pct


def lmi_cost(price: float, dep_pct: float) -> float:
    """Rough LMI estimate: ~1.5-3% of loan amount for <20% deposits."""
    if dep_pct >= 20:
        return 0.0
    loan = price * (1 - dep_pct / 100)
    lmi_rate = 0.025 if dep_pct >= 15 else 0.030 if dep_pct >= 10 else 0.040
    return loan * lmi_rate


# ── Salary projection helpers ─────────────────────────────────────────────────

def _proj_gross_single(base_gross: float, yrs: float) -> float:
    """Nominal gross income at `yrs` years, capped by ceiling if set."""
    grown = base_gross * (1 + salary_growth_rate) ** yrs
    if salary_ceiling_today is not None and salary_ceiling_today > 0:
        nominal_ceiling = salary_ceiling_today * (1 + inflation_rate) ** yrs
        grown = min(grown, nominal_ceiling)
    return grown


def proj_household_gross(yrs: float) -> float:
    """Combined household gross income at `yrs` years from now."""
    total = _proj_gross_single(gross_income, yrs)
    if _partnered:
        total += _proj_gross_single(p_gross_income, yrs)
    return total


# Projected income at exact purchase date (target_years out).
# Run the actual tax engine so net income is accurate, not just proportionally scaled.
_proj_gross_you_at_purchase     = _proj_gross_single(gross_income, target_years)
_proj_gross_partner_at_purchase = _proj_gross_single(p_gross_income, target_years) if _partnered else 0.0

_proj_tax_you = effective_tax_rate(
    _proj_gross_you_at_purchase, 0, 0, 0, 0, CGTLaw.CURRENT,
    has_private_hospital_cover=private_cover,
)
if _partnered and _proj_gross_partner_at_purchase > 0:
    _proj_tax_partner = effective_tax_rate(
        _proj_gross_partner_at_purchase, 0, 0, 0, 0, CGTLaw.CURRENT,
        has_private_hospital_cover=p_private_cover,
    )
    proj_net_annual = _proj_tax_you["net_income"] + _proj_tax_partner["net_income"]
else:
    proj_net_annual = _proj_tax_you["net_income"]

proj_net_monthly = proj_net_annual / 12.0
# Salary growth factor vs today (for labelling)
_salary_growth_factor = proj_household_gross(target_years) / household_gross if household_gross > 0 else 1.0


def months_to_goal(monthly_saving: float) -> int | None:
    """Time to deposit with flat monthly contributions (no salary growth)."""
    for m in range(1, 300):
        yrs = m / 12.0
        fv_existing = current_savings * (1 + savings_return) ** yrs
        if savings_return > 0:
            monthly_r = (1 + savings_return) ** (1 / 12) - 1
            fv_contribs = monthly_saving * (((1 + monthly_r) ** m - 1) / monthly_r)
        else:
            fv_contribs = monthly_saving * m
        if fv_existing + fv_contribs >= target_deposit_future(yrs):
            return m
    return None


def months_to_goal_growing(base_monthly_saving: float) -> int | None:
    """Time to deposit where savings grow proportionally with salary each month.

    Uses an iterative balance simulation rather than the closed-form annuity
    formula, because contributions are not constant.
    """
    if base_monthly_saving <= 0 or net_monthly <= 0:
        return months_to_goal(base_monthly_saving)
    savings_ratio = base_monthly_saving / net_monthly
    _base_hh_gross = household_gross if household_gross > 0 else 1.0
    monthly_r = (1 + savings_return) ** (1 / 12) - 1 if savings_return > 0 else 0.0
    balance = float(current_savings)
    for m in range(1, 360):
        yrs = m / 12.0
        # Scale net income by how much household gross has grown (proxy for net growth)
        gross_scale = proj_household_gross(yrs) / _base_hh_gross
        this_month_saving = savings_ratio * net_monthly * gross_scale
        balance = balance * (1 + monthly_r) + this_month_saving
        if balance >= target_deposit_future(yrs):
            return m
    return None


def required_monthly_saving(yrs: float) -> float:
    """Monthly saving needed to hit the deposit target in exactly yrs years."""
    months = yrs * 12
    fv_target = target_deposit_future(yrs)
    fv_existing = current_savings * (1 + savings_return) ** yrs
    shortfall = max(fv_target - fv_existing, 0.0)
    if shortfall <= 0:
        return 0.0
    if savings_return > 0:
        monthly_r = (1 + savings_return) ** (1 / 12) - 1
        return shortfall / (((1 + monthly_r) ** months - 1) / monthly_r)
    return shortfall / months


# ── Key metrics for target_years goal ────────────────────────────────────────
req_monthly = required_monthly_saving(target_years)
req_pct_of_income = req_monthly / net_monthly * 100 if net_monthly > 0 else 0
future_price = future_property_price(target_years)
future_deposit = target_deposit_future(target_years)
lmi = lmi_cost(future_price, deposit_pct)
real_future_price = future_price / (1 + inflation_rate) ** target_years
real_future_deposit = future_deposit / (1 + inflation_rate) ** target_years

# ── Metrics row ───────────────────────────────────────────────────────────────
st.subheader(f"Goal: {deposit_pct}% deposit + costs in {target_years} years")

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Monthly Saving Required",
    f"${req_monthly:,.0f}",
    help="How much to save each month to hit your deposit target.",
)
c2.metric(
    "% of Net Income",
    f"{req_pct_of_income:.1f}%",
    delta=f"${net_monthly - req_monthly:,.0f}/mo left",
    delta_color="normal",
    help="Required saving as a share of your monthly take-home pay.",
)
c3.metric(
    "Future Property Price",
    f"${future_price:,.0f}",
    delta=f"${real_future_price:,.0f} in today's $",
    delta_color="off",
    help="Nominal future price assuming property price growth each year.",
)
c4.metric(
    "Total Deposit + Costs",
    f"${future_deposit:,.0f}",
    delta=f"${real_future_deposit:,.0f} in today's $",
    delta_color="off",
    help=f"{deposit_pct}% deposit + {stamp_duty_pct}% stamp duty/costs on the future property price.",
)

# ── At-your-savings-rate row ──────────────────────────────────────────────────
# Use growing-contributions model if salary growth is set, else flat model.
if salary_growth_rate > 0:
    budget_months = months_to_goal_growing(monthly_savings_available)
else:
    budget_months = months_to_goal(monthly_savings_available)

if budget_months is not None:
    budget_years = budget_months / 12
    gap_months   = budget_months - target_years * 12
    gap_label    = (f"{abs(gap_months / 12):.1f} yrs faster" if gap_months < 0
                    else f"{gap_months / 12:.1f} yrs slower" if gap_months > 0
                    else "exactly on target")
    gap_colour   = "normal" if gap_months <= 0 else "inverse"
    _growth_flag = " (with salary growth)" if salary_growth_rate > 0 else ""
    b1, b2, b3 = st.columns(3)
    b1.metric(
        "⏱ Time at Your Savings Rate",
        f"{budget_years:.1f} yrs  ({2026 + budget_years:.0f})",
        delta=gap_label, delta_color=gap_colour,
        help=f"Saving ${monthly_savings_available:,}/mo starting today{_growth_flag}. "
             "Savings grow with your salary each year.",
    )
    b2.metric(
        "Monthly Savings vs Required",
        f"${monthly_savings_available:,.0f}",
        delta=f"${monthly_savings_available - req_monthly:+,.0f} vs required",
        delta_color="normal",
        help=f"Required: ${req_monthly:,.0f}/mo (flat) to hit goal in {target_years} years.",
    )
    _savings_rate_pct = monthly_savings_available / net_monthly * 100 if net_monthly > 0 else 0
    b3.metric(
        "Savings Rate Applied",
        f"{_savings_rate_pct:.1f}% of take-home",
        help="Starting savings rate (% of today's net income). "
             "With salary growth this percentage rises in dollar terms but stays proportionally constant.",
    )
elif monthly_savings_available == 0:
    st.info("💡 Enter your monthly savings above (or run the Budget page) to see your personalised deposit timeline.")
else:
    st.warning(
        f"⚠️ Saving ${monthly_savings_available:,}/mo (growing with salary), the deposit target cannot be "
        f"reached within 30 years at the current property growth and savings return assumptions. "
        f"Consider a higher savings rate, a cheaper property, or a lower deposit percentage."
    )

if lmi > 0:
    st.warning(
        f"⚠️ **LMI Alert:** A {deposit_pct}% deposit on a ${future_price:,.0f} property incurs "
        f"~${lmi:,.0f} in Lenders Mortgage Insurance. This adds to your upfront cost. "
        f"Consider saving to 20% to avoid LMI."
    )

if req_pct_of_income > 50:
    st.error(
        f"🚨 **Stretch goal:** {req_pct_of_income:.0f}% of take-home pay is very aggressive. "
        f"Consider extending your timeline, targeting a cheaper property, or growing your income."
    )
elif req_pct_of_income > 30:
    st.warning(
        f"⚠️ **Ambitious target:** Saving {req_pct_of_income:.0f}% of take-home is achievable but tight. "
        f"Reduce discretionary spending and automate contributions."
    )
else:
    st.success(
        f"✅ Saving {req_pct_of_income:.1f}% of take-home pay is realistic. Set up a "
        f"dedicated savings account and automate ${req_monthly:,.0f}/month."
    )

st.divider()

# ── Mortgage serviceability ───────────────────────────────────────────────────
st.subheader("🏦 Mortgage Serviceability")
st.caption(
    f"Assumes you buy at the projected future price of **${future_price:,.0f}** "
    f"in {target_years} years with a **{deposit_pct}%** deposit, "
    f"financed over **{loan_term_years} years** at **{mortgage_rate*100:.2f}%/yr**."
)

loan_amount       = future_price * (1 - deposit_pct / 100.0)
monthly_rate      = mortgage_rate / 12
n_payments        = loan_term_years * 12
if monthly_rate > 0:
    monthly_repayment = loan_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / (
        (1 + monthly_rate) ** n_payments - 1
    )
else:
    monthly_repayment = loan_amount / n_payments

total_repaid      = monthly_repayment * n_payments
total_interest    = total_repaid - loan_amount
# Two serviceability ratios: today's income (pessimistic) and projected at purchase (realistic)
repay_pct_today   = monthly_repayment / net_monthly * 100 if net_monthly > 0 else 0
repay_pct_proj    = monthly_repayment / proj_net_monthly * 100 if proj_net_monthly > 0 else 0
real_monthly_rep  = monthly_repayment / (1 + inflation_rate) ** target_years  # today's dollars

_salary_ceiling_note = (
    f"  Ceiling: ${salary_ceiling_today:,.0f}/yr (today's $)." if salary_ceiling_today else ""
)
_growth_note = (
    f"Salary grows at **{salary_growth_rate*100:.1f}%/yr** → "
    f"projected household income at purchase: **${proj_household_gross(target_years):,.0f}/yr** "
    f"(net **${proj_net_monthly:,.0f}/mo**).{_salary_ceiling_note}"
    if salary_growth_rate > 0
    else f"Salary growth is **0%** — income stays at **${net_monthly:,.0f}/mo** net."
)
st.caption(_growth_note)

m1, m2, m3, m4 = st.columns(4)
m1.metric(
    "Loan Amount",
    f"${loan_amount:,.0f}",
    delta=f"${loan_amount / (1 + inflation_rate) ** target_years:,.0f} in today's $",
    delta_color="off",
    help=f"{100 - deposit_pct}% of projected future property price ${future_price:,.0f}.",
)
m2.metric(
    "Monthly Repayment",
    f"${monthly_repayment:,.0f}",
    delta=f"${real_monthly_rep:,.0f} in today's $",
    delta_color="off",
    help="Principal & interest repayment at the mortgage rate above.",
)
m3.metric(
    "% of Income at Purchase",
    f"{repay_pct_proj:.1f}%",
    delta=f"${proj_net_monthly - monthly_repayment:,.0f}/mo remaining",
    delta_color="normal",
    help=f"Repayment as a share of projected take-home pay in {target_years} years "
         f"(${proj_net_monthly:,.0f}/mo). "
         "Below 28% is comfortable; above 35% is the APRA stress threshold.",
)
m4.metric(
    "Total Interest Paid",
    f"${total_interest:,.0f}",
    help=f"Total interest over {loan_term_years} years at {mortgage_rate*100:.2f}%/yr.",
)

# Show current-income ratio as a reference line
if salary_growth_rate > 0:
    st.caption(
        f"📊 On **today's** income (${net_monthly:,.0f}/mo net): **{repay_pct_today:.1f}%** of take-home. "
        f"With salary growth this improves to **{repay_pct_proj:.1f}%** by the time you buy."
    )

# Serviceability verdict based on projected income (the realistic scenario)
if repay_pct_proj > 35:
    st.error(
        f"🔴 **Mortgage stress zone: {repay_pct_proj:.1f}% of projected take-home.** "
        f"Even accounting for salary growth to ${proj_net_monthly:,.0f}/mo, repayments exceed the "
        f"35% threshold. Consider a larger deposit, cheaper property, longer loan term, or "
        f"increasing your savings rate to reach 20%+ deposit sooner."
    )
elif repay_pct_proj > 28:
    st.warning(
        f"🟡 **Manageable but stretched: {repay_pct_proj:.1f}% of projected take-home.** "
        f"Repayments at ${monthly_repayment:,.0f}/mo leave ${proj_net_monthly - monthly_repayment:,.0f}/mo "
        f"after the mortgage. A rate rise of 1–2% could push into stress territory."
    )
else:
    st.success(
        f"🟢 **Repayments look serviceable: {repay_pct_proj:.1f}% of projected take-home.** "
        f"Below the 28% comfort threshold — you'd have ${proj_net_monthly - monthly_repayment:,.0f}/mo "
        f"left after the mortgage for living costs and other savings."
    )

st.divider()

# ── Savings trajectory chart ──────────────────────────────────────────────────
st.subheader("Savings vs Property Target Over Time")

# Chart horizon: whichever is longer — target_years or actual time at budget savings rate
chart_horizon = target_years
if budget_months is not None:
    chart_horizon = max(target_years, int(budget_months / 12) + 1)

months_range = range(1, chart_horizon * 12 + 1)
monthly_r = (1 + savings_return) ** (1 / 12) - 1 if savings_return > 0 else 0.0

savings_traj, deposit_traj, real_savings_traj, real_deposit_traj = [], [], [], []
budget_traj  = []  # flat Budget savings (no growth)
growing_traj = []  # Budget savings growing with salary
_base_hh_gross_chart = household_gross if household_gross > 0 else 1.0
_savings_ratio_chart  = (monthly_savings_available / net_monthly
                         if net_monthly > 0 and monthly_savings_available > 0 else 0)
_growing_balance = float(current_savings)

for m in months_range:
    yrs = m / 12.0
    if savings_return > 0:
        fv_req    = req_monthly * (((1 + monthly_r) ** m - 1) / monthly_r)
        fv_budget = monthly_savings_available * (((1 + monthly_r) ** m - 1) / monthly_r)
    else:
        fv_req    = req_monthly * m
        fv_budget = monthly_savings_available * m
    fv_existing   = current_savings * (1 + savings_return) ** yrs
    fv_savings    = fv_existing + fv_req
    fv_bud_saving = fv_existing + fv_budget
    fv_deposit    = target_deposit_future(yrs)
    cpi_factor    = (1 + inflation_rate) ** yrs

    # Growing trajectory: iterative balance (salary-scaled contributions)
    gross_scale_m = proj_household_gross(yrs) / _base_hh_gross_chart
    month_saving_growing = _savings_ratio_chart * net_monthly * gross_scale_m
    _growing_balance = _growing_balance * (1 + monthly_r) + month_saving_growing

    savings_traj.append(fv_savings)
    deposit_traj.append(fv_deposit)
    real_savings_traj.append(fv_savings / cpi_factor)
    real_deposit_traj.append(fv_deposit / cpi_factor)
    budget_traj.append(fv_bud_saving)
    growing_traj.append(_growing_balance)

years_axis = [m / 12 for m in months_range]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=years_axis, y=savings_traj,
    name=f"Required savings (${req_monthly:,.0f}/mo flat)",
    line=dict(color=COLORS["mint"], width=2),
))
# Growing-salary trajectory (only when salary growth > 0 and savings are entered)
if salary_growth_rate > 0 and monthly_savings_available > 0:
    fig.add_trace(go.Scatter(
        x=years_axis, y=growing_traj,
        name=f"Your savings + {salary_growth_rate*100:.1f}%/yr salary growth",
        line=dict(color=COLORS["blue"], width=2.5),
        fill="none",
    ))
# Flat Budget-rate trajectory (only if different from required and salary growth is 0)
if monthly_savings_available != req_monthly and monthly_savings_available > 0 and salary_growth_rate == 0:
    fig.add_trace(go.Scatter(
        x=years_axis, y=budget_traj,
        name=f"Your Budget savings (${monthly_savings_available:,.0f}/mo flat)",
        line=dict(color=COLORS["purple"], width=2.5, dash="dashdot"),
        fill="none",
    ))
fig.add_trace(go.Scatter(
    x=years_axis, y=deposit_traj,
    name="Deposit Target (Nominal)",
    line=dict(color=COLORS["orange"], width=2, dash="dash"),
))
fig.add_trace(go.Scatter(
    x=years_axis, y=real_savings_traj,
    name="Required savings (Real $)",
    line=dict(color=COLORS["teal"], width=1.5, dash="dot"),
))
fig.add_trace(go.Scatter(
    x=years_axis, y=real_deposit_traj,
    name="Deposit Target (Real $)",
    line=dict(color=COLORS["yellow"], width=1.5, dash="dot"),
))
fig.update_layout(
    **CHART_LAYOUT,
    xaxis_title="Years", yaxis_title="AUD",
    height=400,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width="stretch")

st.divider()

# ── Required savings rate vs goal timeline ────────────────────────────────────
st.subheader("How Savings Rate Changes With Your Timeline")

year_range = list(range(1, 21))
req_monthly_vals = [required_monthly_saving(y) for y in year_range]
req_pct_vals     = [v / net_monthly * 100 if net_monthly > 0 else 0 for v in req_monthly_vals]

# Anything above 100% is mathematically impossible (you can't save more than you earn).
# We clamp the visual bar height so the chart stays readable, but label the bar
# clearly as "not feasible" rather than printing a misleading number.
Y_CEILING = 100
clamped_vals = [min(p, Y_CEILING) for p in req_pct_vals]
bar_text = [
    "Not feasible" if p > Y_CEILING else f"{p:.0f}%"
    for p in req_pct_vals
]
bar_colors = [
    COLORS["dark"]   if p > Y_CEILING        # impossible: charcoal block
    else COLORS["red"]    if p > 50          # extreme
    else COLORS["orange"] if p > 30          # ambitious
    else COLORS["mint"]                       # healthy
    for p in req_pct_vals
]

fig2 = go.Figure()
fig2.add_trace(go.Bar(
    x=year_range, y=clamped_vals,
    marker_color=bar_colors,
    name="Required % of Net Income",
    text=bar_text,
    textposition="outside",
    hovertext=[f"{p:.1f}% required" for p in req_pct_vals],
    hoverinfo="x+text",
))
fig2.add_hline(y=20, line_dash="dash", line_color=COLORS["teal"],
               annotation_text="20% (healthy)", annotation_font_color=COLORS["teal"])
fig2.add_hline(y=30, line_dash="dash", line_color=COLORS["yellow"],
               annotation_text="30% (ambitious)", annotation_font_color=COLORS["yellow"])
fig2.add_hline(y=50, line_dash="dash", line_color=COLORS["red"],
               annotation_text="50% (extreme)", annotation_font_color=COLORS["red"])
fig2.add_hline(y=100, line_dash="solid", line_color=COLORS["dark"], line_width=2,
               annotation_text="100% ceiling (impossible above)",
               annotation_font_color=COLORS["dark"])
fig2.add_vline(x=target_years, line_dash="solid", line_color=COLORS["purple"],
               annotation_text=f"Your goal ({target_years}yr)",
               annotation_font_color=COLORS["purple"])
fig2.update_layout(
    **CHART_LAYOUT,
    xaxis_title="Years to Goal",
    yaxis_title="Required Savings Rate (% of Net Income)",
    yaxis=dict(range=[0, 115]),
    height=380, showlegend=False,
)
st.plotly_chart(fig2, width="stretch")

# Inline reality check when the user's chosen timeline isn't achievable.
_user_pct = req_pct_vals[target_years - 1] if 1 <= target_years <= len(req_pct_vals) else None
if _user_pct is not None and _user_pct > 100:
    st.error(
        f"🚨 **Goal not feasible at {target_years} years.** You would need to save "
        f"**{_user_pct:.0f}%** of your net income, which is mathematically impossible. "
        f"Extend the timeline, lower the property target, or look for ways to increase income."
    )
elif _user_pct is not None and _user_pct > 50:
    st.warning(
        f"⚠️ **Extreme savings rate required ({_user_pct:.0f}%).** "
        f"Few households sustain this. Consider a longer timeline."
    )

st.divider()

# ── After-tax income waterfall ────────────────────────────────────────────────
st.subheader("Your Monthly Income Breakdown")
income_tax_amt  = tax_result["income_tax"] / 12
medicare_amt    = (tax_result["medicare_levy"] + tax_result["medicare_levy_surcharge"]) / 12
hecs_amt        = tax_result["hecs_repayment"] / 12
saving_amt      = req_monthly
remaining_amt   = max(net_monthly - req_monthly, 0)

fig3 = go.Figure(go.Bar(
    x=["Income Tax", "Medicare", "HECS", "Deposit Savings", "Future Mortgage", "Remaining Income"],
    y=[income_tax_amt, medicare_amt, hecs_amt, saving_amt, monthly_repayment, remaining_amt],
    marker_color=[
        COLORS["red"], COLORS["orange"], COLORS["yellow"],
        COLORS["mint"],
        COLORS["red"] if repay_pct_proj > 35 else COLORS["orange"] if repay_pct_proj > 28 else COLORS["teal"],
        COLORS["blue"],
    ],
    text=[f"${v:,.0f}" for v in [income_tax_amt, medicare_amt, hecs_amt, saving_amt, monthly_repayment, remaining_amt]],
    textposition="outside",
))
fig3.update_layout(
    **CHART_LAYOUT,
    xaxis_title="", yaxis_title="Monthly (AUD)",
    height=380, showlegend=False,
    yaxis=dict(range=[0, gross_income_for_chart / 12 * 1.15]),
)
st.plotly_chart(fig3, width="stretch")

# ── Export to Profile ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Send to Profile")
st.caption(
    "Push every income/HECS/cover field above back to the shared profile so the "
    "home page, Budget, and FIRE pages stay in sync. Property targets and "
    "growth assumptions are page-local and stay here."
)
exp_l, exp_r = st.columns([3, 1])
with exp_l:
    if _partnered:
        st.info(
            f"**Household:** ${household_gross:,.0f}/yr gross  ·  "
            f"You ${your_gross_income:,.0f}  ·  Partner ${p_gross_income:,.0f}"
        )
    else:
        st.info(f"**Gross income to push back:** ${your_gross_income:,.0f}/yr")
with exp_r:
    deposit_export: dict[str, object] = {
        "pf_gross_income":   your_gross_income,
        "pf_hecs_balance":   hecs_balance,
        "pf_private_cover":  private_cover,
        "pf_inflation":      inflation_rate * 100,
    }
    if _partnered:
        deposit_export.update({
            "pf_partner_gross_income":  p_gross_income,
            "pf_partner_hecs_balance":  p_hecs_balance,
            "pf_partner_private_cover": p_private_cover,
        })
    profile.export_button(
        "Export Income & HECS to Profile",
        deposit_export,
        help="Sends income, HECS and inflation back to your shared profile.",
    )

# ── Key assumptions ───────────────────────────────────────────────────────────
with st.expander("📋 Assumptions & Methodology"):
    st.markdown(f"""
| Assumption | Value |
|---|---|
| Property price today | ${property_price_today:,.0f} |
| Property price growth | {property_growth_rate*100:.2f}%/yr |
| Savings investment return | {savings_return*100:.2f}%/yr |
| Inflation rate | {inflation_rate*100:.2f}%/yr |
| Deposit required | {deposit_pct}% of future purchase price |
| Stamp duty + costs | {stamp_duty_pct}% of future purchase price |
| Tax year | 2024-25 AUS (Stage 3 cuts applied) |
| After-tax monthly income | ${net_monthly:,.0f} |

**Real $ figures** deflate nominal amounts by CPI at `{inflation_rate*100:.2f}%/yr` to show
today's purchasing power equivalent.

**LMI** estimate uses: 2.5% of loan for 15–19%, 3.0% for 10–14%, 4.0% for 5–9%.
Actual LMI varies by lender and insurer.

**Mortgage serviceability** uses a standard P&I repayment formula.
The 35% threshold matches APRA's mortgage stress guidance; 28% is the typical lender comfort band.
Repayment vs income is calculated on today's net income — if incomes rise before purchase, serviceability improves.

⚠️ This is a modelling tool, not financial advice. Verify current tax rates and 
LMI schedules before making decisions.
""")
