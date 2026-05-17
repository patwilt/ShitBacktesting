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
    gross_income = st.number_input(
        "Gross Annual Income (AUD)", min_value=0,
        value=profile.get("pf_gross_income"), step=5_000
    )
    hecs_balance = st.number_input(
        "HECS-HELP Balance (AUD)", min_value=0,
        value=profile.get("pf_hecs_balance"), step=1_000
    )
    private_cover = st.checkbox("Private Hospital Cover",
                                value=profile.get("pf_private_cover"))

    if _partnered:
        st.markdown("**🧑‍🤝‍🧑 Your Partner**")
        p_gross_income  = st.number_input(
            "Partner Gross Income (AUD)", min_value=0,
            value=profile.get("pf_partner_gross_income"), step=5_000,
        )
        p_hecs_balance  = st.number_input(
            "Partner HECS-HELP (AUD)", min_value=0,
            value=profile.get("pf_partner_hecs_balance"), step=1_000,
        )
        p_private_cover = st.checkbox("Partner Private Hospital Cover",
                                       value=profile.get("pf_partner_private_cover"))
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
        options=[5, 10, 15, 20],
        value=20,
        help="20% avoids Lenders Mortgage Insurance (LMI). Lower deposits add LMI cost.",
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
        "Inflation Rate (%/yr)", 0.0, 8.0, profile.get("pf_inflation"), 0.25
    ) / 100.0

    st.divider()
    st.header("💰 Current Savings")
    current_savings = st.number_input(
        "Current Savings Already Set Aside (AUD)", min_value=0, value=30_000, step=5_000
    )
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


def months_to_goal(monthly_saving: float) -> int | None:
    """Binary search months; returns None if goal unreachable in 25 years."""
    for m in range(1, 300):
        yrs = m / 12.0
        # FV of current savings
        fv_existing = current_savings * (1 + savings_return) ** yrs
        # FV of monthly contributions (end-of-period annuity)
        if savings_return > 0:
            monthly_r = (1 + savings_return) ** (1 / 12) - 1
            fv_contribs = monthly_saving * (((1 + monthly_r) ** m - 1) / monthly_r)
        else:
            fv_contribs = monthly_saving * m
        total_fv = fv_existing + fv_contribs
        if total_fv >= target_deposit_future(yrs):
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

# ── Savings trajectory chart ──────────────────────────────────────────────────
st.subheader("Savings vs Property Target Over Time")

months_range = range(1, target_years * 12 + 1)
monthly_r = (1 + savings_return) ** (1 / 12) - 1 if savings_return > 0 else 0.0

savings_traj, deposit_traj, real_savings_traj, real_deposit_traj = [], [], [], []
for m in months_range:
    yrs = m / 12.0
    if savings_return > 0:
        fv_contribs = req_monthly * (((1 + monthly_r) ** m - 1) / monthly_r)
    else:
        fv_contribs = req_monthly * m
    fv_savings = current_savings * (1 + savings_return) ** yrs + fv_contribs
    fv_deposit = target_deposit_future(yrs)
    cpi_factor = (1 + inflation_rate) ** yrs

    savings_traj.append(fv_savings)
    deposit_traj.append(fv_deposit)
    real_savings_traj.append(fv_savings / cpi_factor)
    real_deposit_traj.append(fv_deposit / cpi_factor)

years_axis = [m / 12 for m in months_range]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=years_axis, y=savings_traj,
    name="Your Savings (Nominal)",
    line=dict(color=COLORS["mint"], width=2),
))
fig.add_trace(go.Scatter(
    x=years_axis, y=deposit_traj,
    name="Deposit Target (Nominal)",
    line=dict(color=COLORS["orange"], width=2, dash="dash"),
))
fig.add_trace(go.Scatter(
    x=years_axis, y=real_savings_traj,
    name="Your Savings (Real $)",
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
    x=["Income Tax", "Medicare", "HECS", "Deposit Savings", "Remaining Income"],
    y=[income_tax_amt, medicare_amt, hecs_amt, saving_amt, remaining_amt],
    marker_color=[
        COLORS["red"], COLORS["orange"], COLORS["yellow"],
        COLORS["mint"], COLORS["blue"],
    ],
    text=[f"${v:,.0f}" for v in [income_tax_amt, medicare_amt, hecs_amt, saving_amt, remaining_amt]],
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

⚠️ This is a modelling tool, not financial advice. Verify current tax rates and 
LMI schedules before making decisions.
""")
