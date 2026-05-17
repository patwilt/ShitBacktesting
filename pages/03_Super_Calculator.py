"""Super Growth Calculator — project your superannuation to retirement.

Includes employer SG, salary sacrifice, non-concessional contributions, and inflation-indexed projections.
Division 293 tax and concessional cap are factored in.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from engines.tax_engine import (
    division_293_tax, super_concessional_tax, net_income_tax, medicare_levy,
)
from utils.colors import COLORS, CHART_LAYOUT
from utils import shared_profile as profile

st.set_page_config(page_title="Super Calculator", page_icon="🦘", layout="wide")
profile.init()
st.title("🦘 Superannuation Growth Calculator")
st.caption(
    "Steps 2 & 5 of your journey: confirm your employer SG match, then model salary sacrifice "
    "and the tax advantages of super to optimise your retirement balance."
)

CONCESSIONAL_CAP = 30_000     # 2024-25 cap (employer SG + salary sacrifice)
NON_CONC_CAP     = 110_000    # 2024-25 non-concessional cap

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    profile.sidebar_summary()
    st.header("👤 Personal Details")
    st.caption("Pre-filled from your profile.")
    current_age        = st.slider("Current Age",    18, 65, min(max(profile.get("pf_age"), 18), 65))
    retirement_age     = st.slider("Retirement Age", 50, 75, min(max(profile.get("pf_retirement_age"), 50), 75))
    years_to_retire    = max(retirement_age - current_age, 1)

    st.divider()
    st.header("💰 Current Super")
    current_super      = st.number_input("Current Balance ($)", min_value=0,
                                         value=profile.get("pf_super_balance"), step=5_000)

    st.divider()
    st.header("💼 Income & Contributions")
    gross_income       = st.number_input("Gross Income ($)", min_value=0,
                                         value=profile.get("pf_gross_income"), step=5_000)
    sg_rate            = st.slider("Employer SG Rate (%)", 9.0, 12.0, 11.5, 0.25) / 100.0
    salary_sacrifice   = st.number_input(
        "Salary Sacrifice ($)", min_value=0, value=5_000, step=500,
        help="Annual additional super via pre-tax salary sacrifice, on top of employer SG."
    )
    non_concessional   = st.number_input(
        "Non-Concessional Contributions ($)", min_value=0, value=0, step=1_000,
        help=f"After-tax contributions. Capped at ${NON_CONC_CAP:,}/yr (2024-25)."
    )
    income_growth_rate = st.slider("Annual Income Growth (%)", 0.0, 10.0, 3.0, 0.25) / 100.0

    st.divider()
    st.header("📈 Investment Returns")
    super_return       = st.slider("Super Fund Return (%/yr)", 0.0, 14.0, 7.5, 0.25) / 100.0
    inflation_rate     = st.slider("Inflation (%/yr)",         0.0, 8.0, profile.get("pf_inflation"), 0.25) / 100.0

    st.divider()
    st.header("💸 Drawdown (Post-Retirement)")
    annual_drawdown    = st.number_input(
        "Annual Drawdown in Retirement ($)", min_value=0, value=80_000, step=5_000,
        help="How much you plan to withdraw per year from super in retirement (today's dollars)."
    )
    drawdown_return    = st.slider("Return in Drawdown Phase (%/yr)", 0.0, 10.0, 5.0, 0.25) / 100.0

# ── Concessional cap check ─────────────────────────────────────────────────────
employer_sg     = gross_income * sg_rate
total_conc      = employer_sg + salary_sacrifice
excess_conc     = max(total_conc - CONCESSIONAL_CAP, 0.0)
capped_conc     = min(total_conc, CONCESSIONAL_CAP)
non_conc_capped = min(non_concessional, NON_CONC_CAP)

# Tax on super contributions
super_tax_15    = super_concessional_tax(capped_conc)
div_293         = division_293_tax(gross_income, capped_conc)
net_conc_into_super = capped_conc - super_tax_15 - div_293

# ── Metrics row ───────────────────────────────────────────────────────────────
st.subheader("Contribution Summary")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Employer SG", f"${employer_sg:,.0f}",   help=f"{sg_rate*100:.2f}% of gross income.")
c2.metric("Salary Sacrifice", f"${salary_sacrifice:,.0f}")
c3.metric("Total Concessional", f"${total_conc:,.0f}",
          delta=f"Cap: ${CONCESSIONAL_CAP:,}", delta_color="off")
c4.metric("Super Tax (15%)", f"${super_tax_15:,.0f}")
c5.metric("Division 293 Tax", f"${div_293:,.0f}",
          help="Extra 15% for earners where income+contributions > $250,000.")

if excess_conc > 0:
    st.warning(
        f"⚠️ **Concessional cap exceeded** by ${excess_conc:,.0f}. The excess is included in "
        f"your assessable income and taxed at your marginal rate (plus 15% offset). "
        f"Reduce salary sacrifice to stay within the ${CONCESSIONAL_CAP:,} cap."
    )
else:
    remaining_cap = CONCESSIONAL_CAP - total_conc
    st.success(
        f"✅ Within concessional cap. You have **${remaining_cap:,.0f}** of remaining concessional "
        f"cap available for additional salary sacrifice."
    )

st.divider()

# ── Projection: three scenarios ───────────────────────────────────────────────
st.subheader(f"Super Balance Projection to Age {retirement_age} ({years_to_retire} years)")

def project_super(
    current_bal: float,
    annual_gross: float,
    sg_r: float,
    sal_sac: float,
    non_conc: float,
    fund_return: float,
    inc_growth: float,
    years: int,
    inflation: float,
) -> tuple[list[float], list[float], list[float]]:
    """Returns (nominal balances, real balances, ages) for each year."""
    balances_nom, balances_real, ages = [current_bal], [current_bal], [current_age]
    bal = float(current_bal)
    inc = float(annual_gross)

    for yr in range(1, years + 1):
        emp_sg      = inc * sg_r
        conc        = min(emp_sg + sal_sac, CONCESSIONAL_CAP)
        s_tax       = super_concessional_tax(conc)
        d293        = division_293_tax(inc, conc)
        net_contrib = conc - s_tax - d293 + min(non_conc, NON_CONC_CAP)
        bal         = bal * (1 + fund_return) + net_contrib
        cpi         = (1 + inflation) ** yr
        balances_nom.append(bal)
        balances_real.append(bal / cpi)
        ages.append(current_age + yr)
        inc *= (1 + inc_growth)

    return balances_nom, balances_real, ages

# Scenario 1: Base (current settings)
nom_base, real_base, age_base = project_super(
    current_super, gross_income, sg_rate, salary_sacrifice, non_conc_capped,
    super_return, income_growth_rate, years_to_retire, inflation_rate,
)

# Scenario 2: Maximise concessional cap (no salary sacrifice beyond cap)
max_ss = max(CONCESSIONAL_CAP - gross_income * sg_rate, 0)
nom_max, real_max, _ = project_super(
    current_super, gross_income, sg_rate, max_ss, non_conc_capped,
    super_return, income_growth_rate, years_to_retire, inflation_rate,
)

# Scenario 3: No extra contributions (employer SG only)
nom_sg, real_sg, _ = project_super(
    current_super, gross_income, sg_rate, 0, 0,
    super_return, income_growth_rate, years_to_retire, inflation_rate,
)

final_base = real_base[-1]
final_max  = real_max[-1]
final_sg   = real_sg[-1]

# ── Export current super to profile ──────────────────────────────────────────
exp_l, exp_r = st.columns([3, 1])
with exp_l:
    st.info(
        f"**Current super:** ${current_super:,.0f}  ·  "
        f"**Projected at {retirement_age} (real $):** ${final_base:,.0f} (current plan)"
    )
with exp_r:
    profile.export_button(
        "Export Super Balance to Profile",
        {"pf_super_balance": current_super},
        help="Updates the shared profile super balance so Dashboard and FIRE pages use it.",
    )

m1, m2, m3 = st.columns(3)
m1.metric("SG Only (Real $)", f"${final_sg:,.0f}",
          help="Employer SG contributions only, no salary sacrifice.")
m2.metric(f"Current Plan (Real $)", f"${final_base:,.0f}",
          delta=f"+${final_base - final_sg:,.0f} vs SG only",
          help="Your current contribution settings.")
m3.metric(f"Max Concessional (Real $)", f"${final_max:,.0f}",
          delta=f"+${final_max - final_sg:,.0f} vs SG only",
          help=f"Maximise salary sacrifice to hit the ${CONCESSIONAL_CAP:,} concessional cap.")

fig = go.Figure()
for (label, real_vals, color) in [
    ("Employer SG Only", real_sg, COLORS["muted"]),
    ("Current Plan", real_base, COLORS["mint"]),
    (f"Max Concessional Cap", real_max, COLORS["purple"]),
]:
    fig.add_trace(go.Scatter(
        x=age_base, y=real_vals,
        name=label,
        line=dict(color=color, width=2),
        fill="tonexty" if label == "Current Plan" else None,
        fillcolor="rgba(78,154,114,0.1)" if label == "Current Plan" else None,
    ))

fig.update_layout(
    **CHART_LAYOUT,
    xaxis_title="Age",
    yaxis_title="Super Balance (Real, Inflation-Adjusted AUD)",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width="stretch")

st.divider()

# ── Tax saving from salary sacrifice ──────────────────────────────────────────
st.subheader("Tax Saving from Salary Sacrifice")

if salary_sacrifice > 0 and salary_sacrifice <= max_ss:
    marginal_saved = (
        net_income_tax(gross_income) + medicare_levy(gross_income)
        - net_income_tax(gross_income - salary_sacrifice) - medicare_levy(gross_income - salary_sacrifice)
        - super_concessional_tax(salary_sacrifice)
    )
    st.markdown(f"""
**Salary Sacrifice of ${salary_sacrifice:,.0f}/yr:**

| Tax Metric | Amount |
|---|---|
| Income tax + Medicare levy saved | ${max(marginal_saved, 0):,.0f}/yr |
| Super contributions tax paid (15%) | ${super_concessional_tax(salary_sacrifice):,.0f}/yr |
| **Net tax saving** | **${max(marginal_saved - super_concessional_tax(salary_sacrifice), 0):,.0f}/yr** |
| Over {years_to_retire} years (uninvested) | ${max(marginal_saved - super_concessional_tax(salary_sacrifice), 0) * years_to_retire:,.0f} |

*Salary sacrifice is most effective when your marginal income tax rate exceeds 15% (i.e., income > $18,200).*
""")

st.divider()

# ── Retirement drawdown projection ────────────────────────────────────────────
st.subheader("Post-Retirement Super Drawdown")

ret_balance_nom = nom_base[-1]
ret_balance_real = real_base[-1]
annual_draw_future = annual_drawdown * (1 + inflation_rate) ** years_to_retire  # inflate to future $

drawdown_years = 35  # to age 102
bal = ret_balance_nom
draw_nominal = annual_draw_future  # year-1 withdrawal = nominal amount at retirement
drawdown_traj_real = [ret_balance_real]
drawdown_ages = [retirement_age]

for yr in range(1, drawdown_years + 1):
    bal = bal * (1 + drawdown_return) - draw_nominal
    cpi = (1 + inflation_rate) ** (years_to_retire + yr)
    drawdown_traj_real.append(max(bal / cpi, 0))
    drawdown_ages.append(retirement_age + yr)
    draw_nominal *= (1 + inflation_rate)  # grow withdrawal for next year (constant real spending)
    if bal <= 0:
        break

depletion_age = None
for i, b in enumerate(drawdown_traj_real):
    if b <= 0:
        depletion_age = drawdown_ages[i]
        break

if depletion_age:
    dep_str = f"🚨 Super depletes at age **{depletion_age}**"
    dep_color = COLORS["red"]
else:
    dep_str = f"✅ Super outlasts {retirement_age + drawdown_years}. Safe zone!"
    dep_color = COLORS["mint"]

st.markdown(f"### {dep_str}")

fig_draw = go.Figure()
fig_draw.add_trace(go.Scatter(
    x=drawdown_ages, y=drawdown_traj_real,
    fill="tozeroy",
    fillcolor="rgba(66,117,160,0.15)",
    line=dict(color=COLORS["blue"], width=2),
    name=f"Super Balance (Real $)",
))
fig_draw.add_hline(y=0, line_color=COLORS["red"], line_dash="dash")
fig_draw.update_layout(
    **CHART_LAYOUT,
    xaxis_title="Age",
    yaxis_title="Super Balance (Real, Inflation-Adjusted AUD)",
    height=380,
)
st.plotly_chart(fig_draw, width="stretch")

st.caption(
    f"Drawdown: ${annual_drawdown:,.0f}/yr in today's dollars "
    f"(${annual_draw_future:,.0f}/yr nominal at retirement), "
    f"return in retirement: {drawdown_return*100:.1f}%/yr."
)

st.divider()

# ── Year-by-year table ────────────────────────────────────────────────────────
with st.expander("📋 Year-by-Year Projection Table (Current Plan)"):
    rows = []
    inc = gross_income
    bal = current_super
    for yr in range(1, years_to_retire + 1):
        emp_sg  = inc * sg_rate
        conc    = min(emp_sg + salary_sacrifice, CONCESSIONAL_CAP)
        s_tax   = super_concessional_tax(conc)
        d293    = division_293_tax(inc, conc)
        net_c   = conc - s_tax - d293 + non_conc_capped
        bal     = bal * (1 + super_return) + net_c
        cpi     = (1 + inflation_rate) ** yr
        rows.append(
            f"| {current_age + yr} | ${conc:,.0f} | ${s_tax + d293:,.0f} | "
            f"${net_c:,.0f} | ${bal:,.0f} | ${bal/cpi:,.0f} |"
        )
        inc *= (1 + income_growth_rate)

    st.markdown(
        "| Age | Total Concessional | Tax on Contrib | Net Added | Balance (Nominal) | Balance (Real $) |\n"
        "|---|---|---|---|---|---|\n" + "\n".join(rows)
    )

with st.expander("📋 Key Assumptions"):
    st.markdown(f"""
| Parameter | Value |
|---|---|
| 2024-25 Concessional Cap | ${CONCESSIONAL_CAP:,}/yr |
| 2024-25 Non-Concessional Cap | ${NON_CONC_CAP:,}/yr |
| Super Tax Rate | 15% on concessional contributions |
| Division 293 Threshold | $250,000 (income + contributions) |
| Inflation | {inflation_rate*100:.2f}%/yr |
| Fund Return | {super_return*100:.2f}%/yr |
| Income Growth | {income_growth_rate*100:.2f}%/yr |

Real $ figures deflate balances by CPI compounded at {inflation_rate*100:.2f}%/yr.

⚠️ Caps and tax rates may change. Verify with the ATO before making decisions.
""")
