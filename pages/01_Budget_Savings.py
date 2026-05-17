"""Budget & Savings Rate — cashflow breakdown and FIRE horizon calculator.

Uses the Australian tax engine for precise after-tax income.
All projection figures can be shown in real (inflation-adjusted) dollars.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from engines.tax_engine import effective_tax_rate, CGTLaw
from utils.colors import COLORS, CHART_LAYOUT, CHART_BG
from utils import shared_profile as profile

st.set_page_config(page_title="Budget & Savings Rate", page_icon="💰", layout="wide")
profile.init()
st.title("💰 Budget & Savings Rate")
st.caption(
    "Step 0 of your journey: map where your money goes after tax, find your monthly surplus, "
    "and see how quickly you can reach financial independence."
)

_partnered = profile.is_partnered()

# ── Sidebar: income ───────────────────────────────────────────────────────────
with st.sidebar:
    profile.sidebar_summary()
    st.header("💼 Income")
    if _partnered:
        st.caption("👥 Couple mode. Tax is calculated individually for each partner.")
    else:
        st.caption("Pre-filled from your profile.")

    st.markdown("**🧑 You**")
    gross_income      = st.number_input("Gross Annual Salary (AUD)",   min_value=0, value=profile.get("pf_gross_income"), step=5_000)
    bonus_income      = st.number_input("Annual Bonus / Side Income",  min_value=0, value=5_000,   step=1_000)
    super_contribs    = st.number_input("Super Contributions/yr",      min_value=0, value=15_000,  step=1_000,
                                        help="Employer SG + any salary sacrifice")
    hecs_balance      = st.number_input("HECS-HELP Balance",           min_value=0, value=profile.get("pf_hecs_balance"), step=1_000)
    private_cover     = st.checkbox("Private Hospital Cover", value=profile.get("pf_private_cover"))

    if _partnered:
        st.divider()
        st.markdown("**🧑‍🤝‍🧑 Your Partner**")
        p_gross_income   = st.number_input("Partner Gross Salary (AUD)",  min_value=0, value=profile.get("pf_partner_gross_income"), step=5_000)
        p_bonus_income   = st.number_input("Partner Bonus / Side",        min_value=0, value=0, step=1_000)
        p_super_contribs = st.number_input("Partner Super Contributions/yr", min_value=0, value=int(p_gross_income * 0.115), step=1_000,
                                            help="Defaults to 11.5% SG of partner salary. Add salary sacrifice if applicable.")
        p_hecs_balance   = st.number_input("Partner HECS-HELP Balance",   min_value=0, value=profile.get("pf_partner_hecs_balance"), step=1_000)
        p_private_cover  = st.checkbox("Partner Private Hospital Cover",  value=profile.get("pf_partner_private_cover"))
    else:
        p_gross_income = p_bonus_income = p_super_contribs = p_hecs_balance = 0
        p_private_cover = False

    st.divider()
    st.header("📈 Growth & Returns")
    inflation_rate    = st.slider("Inflation (%/yr)",          0.0, 8.0,  profile.get("pf_inflation"),        0.25) / 100.0
    portfolio_return  = st.slider("Portfolio Return (%/yr)",   0.0, 15.0, profile.get("pf_portfolio_return"), 0.25) / 100.0
    income_growth     = st.slider("Annual Income Growth (%)",  0.0, 10.0, 3.0, 0.25) / 100.0
    swr               = st.slider("Safe Withdrawal Rate (%)",  2.0, 6.0,  profile.get("pf_swr"),              0.25) / 100.0

    st.divider()
    st.header("🏦 Existing Wealth")
    existing_portfolio   = st.number_input("Existing Investment Portfolio ($)", min_value=0, value=profile.get("pf_portfolio"),     step=5_000)
    existing_super       = st.number_input("Existing Super Balance ($)",        min_value=0, value=profile.get("pf_super_balance"), step=5_000)
    annual_super_addition = st.number_input(
        "Total Super Contributions/yr ($)", min_value=0, value=super_contribs, step=1_000,
        help="Employer SG + salary sacrifice. Used in FIRE timeline to project super balance alongside portfolio.",
    )

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
    rent_mortgage   = st.number_input("Rent / Mortgage ($)",    min_value=0, value=2_200, step=100)
    utilities       = st.number_input("Utilities (elec/gas/internet)", min_value=0, value=250, step=25)
    insurance       = st.number_input("Insurance (all policies)", min_value=0, value=200, step=25)
    phone           = st.number_input("Phone / Subscriptions",  min_value=0, value=100, step=10)
    transport_fixed = st.number_input("Transport (loan/rego/fuel)", min_value=0, value=400, step=50)
    other_fixed     = st.number_input("Other Fixed ($)",         min_value=0, value=150, step=25)

with col2:
    st.markdown("**Variable / Discretionary**")
    groceries       = st.number_input("Groceries ($)",           min_value=0, value=600, step=50)
    dining_out      = st.number_input("Dining Out / Takeaway ($)", min_value=0, value=400, step=50)
    entertainment   = st.number_input("Entertainment / Hobbies ($)", min_value=0, value=300, step=50)
    clothing        = st.number_input("Clothing / Personal ($)", min_value=0, value=150, step=25)
    health          = st.number_input("Health / Fitness ($)",    min_value=0, value=100, step=25)
    travel          = st.number_input("Travel / Holidays ($)",   min_value=0, value=300, step=50)
    gifts_misc      = st.number_input("Gifts / Misc ($)",        min_value=0, value=100, step=25)

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
m4.metric(
    f"FIRE Number ({swr*100:.1f}% SWR)",
    f"${fire_number:,.0f}",
    help=f"Portfolio needed so {swr*100:.1f}% annual withdrawal covers your ${annual_spending:,.0f}/yr expenses.",
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
        f"**Calculated:** Monthly Savings = **${monthly_savings:,.0f}**  ·  "
        f"Annual Spending = **${annual_spending:,.0f}**  ·  "
        f"FIRE Number = **${fire_number:,.0f}**"
    )
with exp_right:
    export_values: dict[str, object] = {
        "pf_monthly_savings": max(monthly_savings, 0),
        "pf_annual_spending": annual_spending,
        "pf_gross_income":    gross_income,
        "pf_hecs_balance":    hecs_balance,
        "pf_private_cover":   private_cover,
        "pf_inflation":       inflation_rate * 100,
        "pf_portfolio_return": portfolio_return * 100,
        "pf_swr":             swr * 100,
        "pf_portfolio":       existing_portfolio,
        "pf_super_balance":   existing_super,
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

def years_to_fire(save_rate: float) -> float | None:
    """Years to reach FIRE number given a savings rate, accounting for income growth."""
    if save_rate <= 0:
        return None
    portfolio = float(existing_portfolio)
    super_bal_val = float(existing_super)
    annual_inc = net_annual
    for yr in range(1, 81):
        annual_inc *= (1 + income_growth)
        annual_save = annual_inc * save_rate
        portfolio   = portfolio * (1 + portfolio_return) + annual_save
        super_bal_val = super_bal_val * (1 + portfolio_return) + annual_super_addition
        # FIRE number based on current spending (real)
        fire_target = (annual_inc / swr)
        combined = portfolio + super_bal_val  # includes super (accessible after ~60)
        if combined >= fire_target:
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

**FIRE calculation** includes both investment portfolio and super balance combined.
super is assumed accessible at ~age 60 (preservation age).

**Tax** uses 2024-25 Australian brackets with Stage 3 cuts, LITO, Medicare levy, MLS, and HECS.

⚠️ This is a planning tool. Future returns are not guaranteed.
""")
