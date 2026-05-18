"""Kids & Family Impact — model the financial cost of children on your FIRE journey.

Based on Australian averages for a middle-income household (child.md).
Costs are in real (today's) dollars and flow through to the FIRE Scenarios page
via the shared profile.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from utils.colors import COLORS, CHART_LAYOUT, CHART_BG, STRATEGY_COLORS
from utils import shared_profile as profile
from utils.kids_engine import (
    compute_kids_costs,
    kids_cost_label,
    KidsCostSeries,
)
from engines.tax_engine import gross_withdrawal_for_net_spend

st.set_page_config(page_title="Kids & Family Impact", page_icon="👶", layout="wide")
profile.init()
st.title("👶 Kids & Family Financial Impact")
st.caption(
    "Model the real cost of raising children and see how it affects your FIRE timeline. "
    "Costs flow through to the FIRE Scenarios page automatically once you export to profile."
)

_partnered = profile.is_partnered()
_current_age = int(profile.get("pf_age") or 30)
_gross_income = int(profile.get("pf_gross_income") or 110_000)
_partner_income = int(profile.get("pf_partner_gross_income") or 0) if _partnered else 0

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    profile.sidebar_summary()

    st.header("👶 Kids Plan")
    kids_enabled = st.toggle(
        "Planning for kids?",
        value=bool(profile.get("pf_kids_enabled")),
        help="Toggle on to include the financial impact of children in your FIRE projections.",
    )

    if kids_enabled:
        num_kids = st.selectbox(
            "Number of children",
            options=[1, 2, 3],
            index=min(int(profile.get("pf_num_kids") or 2) - 1, 2),
        )

        st.markdown("**🗓️ Birth timeline**")
        kid1_birth = st.number_input(
            "1st child — years from now",
            min_value=0, max_value=20,
            value=int(profile.get("pf_kid1_birth_yr_from_now") or 3),
            step=1,
            help="0 = born this year.",
        )
        kid2_birth = kid3_birth = None
        if num_kids >= 2:
            kid2_birth = st.number_input(
                "2nd child — years from now",
                min_value=kid1_birth + 1, max_value=25,
                value=max(int(profile.get("pf_kid2_birth_yr_from_now") or kid1_birth + 3), kid1_birth + 1),
                step=1,
            )
        if num_kids >= 3:
            kid3_birth = st.number_input(
                "3rd child — years from now",
                min_value=(kid2_birth or kid1_birth) + 1, max_value=30,
                value=max(int(profile.get("pf_kid3_birth_yr_from_now") or (kid2_birth or kid1_birth) + 3),
                          (kid2_birth or kid1_birth) + 1),
                step=1,
            )

        st.divider()
        st.markdown("**🎓 Education**")
        schooling = st.radio(
            "School type",
            options=["public", "catholic", "private"],
            format_func=kids_cost_label,
            index=["public", "catholic", "private"].index(
                profile.get("pf_kids_schooling") or "public"
            ),
            horizontal=True,
        )
        if schooling == "private":
            private_primary = st.number_input(
                "Private primary school ($/yr per child)",
                min_value=5_000, max_value=60_000,
                value=int(profile.get("pf_kids_private_school_annual") or 20_000),
                step=1_000,
                help="Annual fees for primary school years (ages 5–11).",
            )
            private_high = st.number_input(
                "Private high school ($/yr per child)",
                min_value=5_000, max_value=80_000,
                value=int(profile.get("pf_kids_private_highschool_annual") or 30_000),
                step=1_000,
                help="Annual fees for high school years (ages 12–17).",
            )
        else:
            private_primary = int(profile.get("pf_kids_private_school_annual") or 20_000)
            private_high = int(profile.get("pf_kids_private_highschool_annual") or 30_000)

        st.divider()
        st.markdown("**🍼 Childcare & Early Years**")
        childcare_annual = st.number_input(
            "Childcare cost after CCS subsidy ($/yr per child)",
            min_value=0, max_value=40_000,
            value=int(profile.get("pf_kids_childcare_annual") or 12_000),
            step=500,
            help=(
                "Annual childcare cost per child (ages 0–4) after the Child Care Subsidy (CCS). "
                "Typical range: $8k–$25k. Two kids in care: $15k–$40k+."
            ),
        )
        setup_cost = st.number_input(
            "Baby setup cost per child ($)",
            min_value=0, max_value=20_000,
            value=int(profile.get("pf_kids_setup_cost") or 7_500),
            step=500,
            help="One-off cost at birth: pram, cot, car seat, baby gear. Typically $5k–$10k.",
        )

        st.divider()
        st.markdown("**🏖️ Parental Leave**")
        leave_weeks = st.number_input(
            "Your parental leave (weeks)",
            min_value=0, max_value=52,
            value=int(profile.get("pf_parental_leave_weeks") or 18),
            step=1,
            help="Total weeks off work (paid + unpaid). Government PPL = 18 weeks.",
        )
        partner_leave_weeks = st.number_input(
            "Partner parental leave (weeks)",
            min_value=0, max_value=26,
            value=int(profile.get("pf_parental_leave_partner_weeks") or 4),
            step=1,
        )
        leave_income_pct = st.slider(
            "Income received during leave (%)",
            min_value=0, max_value=100,
            value=int(profile.get("pf_parental_leave_income_pct") or 50),
            step=5,
            help=(
                "What % of normal salary you receive during leave (employer paid + government PPL combined). "
                "Government PPL pays min wage (~$55k/yr equivalent), so this % depends on your salary."
            ),
        )
        partner_career_break_years = st.slider(
            "Years partner stays off work (after parental leave)",
            min_value=0, max_value=10,
            value=int(profile.get("pf_partner_career_break_years") or 0),
            step=1,
            help=(
                "Full years the partner does not return to work after parental leave ends. "
                "Each year adds their full annual income as a household income reduction. "
                "0 = partner returns after parental leave. "
                "This is typically the single largest financial impact of having children."
                + (f" At ${_partner_income:,}/yr, each year off = ${_partner_income:,} in lost income." if _partner_income > 0 else "")
            ),
        )
        if partner_career_break_years > 0 and _partner_income > 0:
            st.caption(
                f"💡 {partner_career_break_years} year{'s' if partner_career_break_years > 1 else ''} career break "
                f"= **${partner_career_break_years * _partner_income:,.0f}** in lost partner income "
                f"(${_partner_income:,}/yr × {partner_career_break_years} yr)."
            )

        st.divider()
        st.markdown("**🏠 Housing**")
        bigger_house = st.checkbox(
            "Need a bigger home for the family?",
            value=(int(profile.get("pf_kids_bigger_house_extra_monthly") or 0) > 0),
            help="Enable to model the ongoing cost of upgrading to a larger home.",
        )
        if bigger_house:
            bigger_house_monthly = st.number_input(
                "Extra monthly housing cost ($)",
                min_value=0, max_value=5_000,
                value=max(int(profile.get("pf_kids_bigger_house_extra_monthly") or 800), 100),
                step=100,
                help=(
                    "Additional rent/mortgage per month for a bigger property. "
                    "Applied from first child's birth until the last child turns 18."
                ),
            )
        else:
            bigger_house_monthly = 0

        st.divider()
        st.markdown("**📈 FIRE Projection**")
        portfolio_return = st.slider("Portfolio return (%/yr)", 4.0, 12.0, float(profile.get("pf_portfolio_return") or 7.0), 0.5) / 100.0
        inflation_rate   = st.slider("Inflation (%/yr)", 1.0, 5.0, float(profile.get("pf_inflation") or 2.5), 0.25) / 100.0
        swr              = st.slider("SWR (%)", 3.0, 6.0, float(profile.get("pf_swr") or 4.0), 0.25) / 100.0
        monthly_dca      = st.number_input(
            "Monthly DCA (base, $)",
            min_value=0, max_value=20_000,
            value=int((profile.get("pf_monthly_savings") or 3_000)),
            step=100,
            help="Your baseline monthly investment contribution before kids costs.",
        )
        initial_portfolio = st.number_input(
            "Current portfolio ($)",
            min_value=0,
            value=int(profile.get("pf_portfolio") or 40_000),
            step=5_000,
        )
        income_growth = st.slider("Income growth (%/yr)", 0.0, 8.0, float(profile.get("pf_salary_growth") or 3.0), 0.5) / 100.0
        annual_spending  = st.number_input(
            "Annual FIRE spending target ($)",
            min_value=10_000, max_value=500_000,
            value=int(profile.get("pf_annual_spending") or 72_000),
            step=1_000,
            help="The annual spending (after tax) you want to sustain in retirement.",
        )

    else:
        # Placeholders so the rest of the page doesn't break
        num_kids = schooling = kid1_birth = kid2_birth = kid3_birth = None
        childcare_annual = setup_cost = leave_weeks = partner_leave_weeks = leave_income_pct = 0
        bigger_house_monthly = private_primary = private_high = partner_career_break_years = 0
        portfolio_return = float(profile.get("pf_portfolio_return") or 7.0) / 100.0
        inflation_rate   = float(profile.get("pf_inflation") or 2.5) / 100.0
        swr              = float(profile.get("pf_swr") or 4.0) / 100.0
        monthly_dca      = int(profile.get("pf_monthly_savings") or 3_000)
        initial_portfolio = int(profile.get("pf_portfolio") or 40_000)
        income_growth    = float(profile.get("pf_salary_growth") or 3.0) / 100.0
        annual_spending  = int(profile.get("pf_annual_spending") or 72_000)


# ── Main content ──────────────────────────────────────────────────────────────
if not kids_enabled:
    st.info(
        "👈 Toggle **Planning for kids?** in the sidebar to model the financial impact of children "
        "on your FIRE journey. When enabled, costs flow automatically to FIRE Scenarios."
    )
    st.stop()

# Build birth years list
birth_yrs: list[int] = [kid1_birth]
if num_kids >= 2 and kid2_birth is not None:
    birth_yrs.append(kid2_birth)
if num_kids >= 3 and kid3_birth is not None:
    birth_yrs.append(kid3_birth)

HORIZON = 30

costs = compute_kids_costs(
    num_kids=num_kids,
    birth_yrs_from_now=birth_yrs,
    schooling=schooling,
    private_school_annual=private_primary,
    private_highschool_annual=private_high,
    childcare_annual_per_child=childcare_annual,
    setup_cost_per_child=setup_cost,
    gross_income=_gross_income,
    partner_gross_income=_partner_income,
    leave_weeks=leave_weeks,
    partner_leave_weeks=partner_leave_weeks,
    leave_income_pct=leave_income_pct,
    bigger_house_monthly_extra=bigger_house_monthly,
    partner_career_break_years=partner_career_break_years,
    horizon=HORIZON,
)

annual_kids_costs: dict[int, float] = costs.as_dict()

# ── Key metrics row ───────────────────────────────────────────────────────────
st.subheader("💰 Lifetime Cost Summary")

lifetime_total = costs.total_lifetime()
peak_yr        = costs.peak_year()
peak_cost      = costs.peak_annual()
peak_age       = _current_age + peak_yr

kids_label = {1: "1 child", 2: "2 children", 3: "3 children"}[num_kids]
school_label = kids_cost_label(schooling)

m1, m2, m3, m4 = st.columns(4)
m1.metric(
    f"Lifetime Cost ({kids_label}, {school_label})",
    f"${lifetime_total:,.0f}",
    help="Total direct costs to age 18 per child — childcare, school, food, clothing, activities, setup, income loss.",
)
m2.metric(
    "Peak Annual Cost",
    f"${peak_cost:,.0f}",
    delta=f"At age {peak_age} (year {peak_yr})",
    delta_color="off",
    help="The single most expensive year across all children combined.",
)

# Monthly DCA reduced during peak year
_peak_monthly_cost = peak_cost / 12.0
_reduced_dca_peak  = max(monthly_dca - _peak_monthly_cost, 0)
_dca_reduction_pct = (1 - _reduced_dca_peak / monthly_dca) * 100 if monthly_dca > 0 else 0

m3.metric(
    "DCA During Peak Year",
    f"${_reduced_dca_peak:,.0f}/mo",
    delta=f"↓ {_dca_reduction_pct:.0f}% vs base ${monthly_dca:,}/mo",
    delta_color="inverse" if _reduced_dca_peak < monthly_dca else "normal",
    help="How much monthly investment contribution remains in the most expensive year.",
)

# FIRE delay estimate via simple projection
def _years_to_fire_no_kids() -> int | None:
    portfolio = float(initial_portfolio)
    fire_target = gross_withdrawal_for_net_spend(float(annual_spending)) / swr if swr > 0 else 0
    annual_dca = monthly_dca * 12
    real_r = (1 + portfolio_return) / (1 + inflation_rate) - 1
    for yr in range(1, 81):
        portfolio = portfolio * (1 + portfolio_return) + annual_dca
        if portfolio >= fire_target:
            return yr
    return None

def _years_to_fire_with_kids() -> int | None:
    portfolio = float(initial_portfolio)
    fire_target = gross_withdrawal_for_net_spend(float(annual_spending)) / swr if swr > 0 else 0
    annual_dca = monthly_dca * 12
    for yr in range(1, 81):
        kids_cost = annual_kids_costs.get(yr, 0.0)
        effective_dca = max(annual_dca - kids_cost, 0.0)
        portfolio = portfolio * (1 + portfolio_return) + effective_dca
        if portfolio >= fire_target:
            return yr
    return None

ytf_no_kids   = _years_to_fire_no_kids()
ytf_with_kids = _years_to_fire_with_kids()

if ytf_no_kids and ytf_with_kids:
    fire_delay = ytf_with_kids - ytf_no_kids
    m4.metric(
        "FIRE Delay from Kids",
        f"+{fire_delay} yr{'s' if fire_delay != 1 else ''}",
        delta=f"Age {_current_age + ytf_no_kids} → Age {_current_age + ytf_with_kids}",
        delta_color="inverse" if fire_delay > 0 else "normal",
        help="How many extra years it takes to reach your FIRE number once kids costs are modelled.",
    )
elif ytf_no_kids:
    m4.metric("FIRE Delay from Kids", "Outside horizon", delta=f"Base: age {_current_age + ytf_no_kids}", delta_color="off")
else:
    m4.metric("FIRE Delay from Kids", "—", delta="Adjust DCA / return above")

st.divider()

# ── Year-by-year cost stacked bar chart ──────────────────────────────────────
st.subheader("📅 Annual Cost Timeline")

years = list(range(HORIZON))
ages  = [_current_age + y for y in years]

fig_costs = go.Figure()
fig_costs.add_trace(go.Bar(
    x=ages, y=costs.setup,
    name="Birth setup",
    marker_color=COLORS["mint"],
    hovertemplate="Year %{x}: Setup $%{y:,.0f}<extra></extra>",
))
fig_costs.add_trace(go.Bar(
    x=ages, y=costs.income_loss,
    name="Income loss (parental leave)",
    marker_color=COLORS["red"],
    hovertemplate="Year %{x}: Income loss $%{y:,.0f}<extra></extra>",
))
fig_costs.add_trace(go.Bar(
    x=ages, y=costs.childcare,
    name="Childcare (CCS net)",
    marker_color=COLORS["blue"],
    hovertemplate="Year %{x}: Childcare $%{y:,.0f}<extra></extra>",
))
fig_costs.add_trace(go.Bar(
    x=ages, y=costs.school,
    name=f"School ({school_label})",
    marker_color=COLORS["purple"],
    hovertemplate="Year %{x}: School $%{y:,.0f}<extra></extra>",
))
fig_costs.add_trace(go.Bar(
    x=ages, y=costs.general,
    name="Food, clothing, activities",
    marker_color=COLORS["soft_yellow"],
    hovertemplate="Year %{x}: General $%{y:,.0f}<extra></extra>",
))
if any(h > 0 for h in costs.housing):
    fig_costs.add_trace(go.Bar(
        x=ages, y=costs.housing,
        name="Housing premium",
        marker_color=COLORS["yellow"],
        hovertemplate="Year %{x}: Housing $%{y:,.0f}<extra></extra>",
    ))

fig_costs.update_layout(
    **CHART_LAYOUT,
    barmode="stack",
    title="Annual Kids Cost by Category (real $)",
    xaxis_title="Your age",
    yaxis_title="Annual cost ($)",
    height=380,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_costs, use_container_width=True)

# Birth year markers
birth_labels = [f"Child {i+1} born (yr {b})" for i, b in enumerate(birth_yrs)]
st.caption(
    "🎯 Birth years: "
    + "  ·  ".join(f"**Age {_current_age + b}** — child {i+1}" for i, b in enumerate(birth_yrs))
)

st.divider()

# ── DCA impact chart ──────────────────────────────────────────────────────────
st.subheader("📉 Monthly DCA Impact")

monthly_base_dca = [monthly_dca] * HORIZON
monthly_kids_dca = [
    max(monthly_dca - costs.total[yr] / 12.0, 0.0)
    for yr in range(HORIZON)
]
monthly_kids_cost_line = [costs.total[yr] / 12.0 for yr in range(HORIZON)]

fig_dca = go.Figure()
fig_dca.add_trace(go.Scatter(
    x=ages, y=monthly_base_dca,
    name="Base monthly DCA (no kids)",
    line=dict(color=COLORS["mint"], width=2, dash="dot"),
    hovertemplate="Base DCA: $%{y:,.0f}/mo<extra></extra>",
))
fig_dca.add_trace(go.Scatter(
    x=ages, y=monthly_kids_dca,
    name="DCA after kids costs",
    line=dict(color=COLORS["blue"], width=3),
    fill="tonexty",
    fillcolor="rgba(255,80,80,0.15)",
    hovertemplate="Kids-adjusted DCA: $%{y:,.0f}/mo<extra></extra>",
))
fig_dca.add_trace(go.Scatter(
    x=ages, y=monthly_kids_cost_line,
    name="Monthly kids cost",
    line=dict(color=COLORS["red"], width=2, dash="dash"),
    hovertemplate="Monthly kids cost: $%{y:,.0f}<extra></extra>",
))

fig_dca.update_layout(
    **CHART_LAYOUT,
    title="Monthly Investment Capacity vs Kids Costs (real $)",
    xaxis_title="Your age",
    yaxis_title="Monthly amount ($)",
    height=360,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_dca, use_container_width=True)
st.caption(
    "The red shaded area shows the investment capacity consumed by kids costs each month. "
    "When kids costs exceed base DCA, investment contributions temporarily pause."
)

st.divider()

# ── Portfolio projection: with vs without kids ────────────────────────────────
st.subheader("📈 Portfolio Projection: With vs Without Kids")

annual_dca = monthly_dca * 12.0
fire_target = gross_withdrawal_for_net_spend(float(annual_spending)) / swr if swr > 0 else 0

portfolio_no_kids   = [float(initial_portfolio)]
portfolio_with_kids = [float(initial_portfolio)]

port_nk = float(initial_portfolio)
port_wk = float(initial_portfolio)

for yr in range(1, HORIZON + 1):
    port_nk = port_nk * (1 + portfolio_return) + annual_dca
    portfolio_no_kids.append(port_nk)

    kids_cost_yr = annual_kids_costs.get(yr, 0.0)
    effective_annual_dca = max(annual_dca - kids_cost_yr, 0.0)
    port_wk = port_wk * (1 + portfolio_return) + effective_annual_dca
    portfolio_with_kids.append(port_wk)

# Inflation-adjust to real $
inf_denoms = [(1 + inflation_rate) ** yr for yr in range(HORIZON + 1)]
portfolio_no_kids_real   = [p / d for p, d in zip(portfolio_no_kids, inf_denoms)]
portfolio_with_kids_real = [p / d for p, d in zip(portfolio_with_kids, inf_denoms)]

ages_proj = [_current_age + yr for yr in range(HORIZON + 1)]

fig_port = go.Figure()
fig_port.add_trace(go.Scatter(
    x=ages_proj, y=portfolio_no_kids_real,
    name="Portfolio without kids",
    line=dict(color=COLORS["mint"], width=2, dash="dot"),
    hovertemplate="No kids: $%{y:,.0f}<extra></extra>",
))
fig_port.add_trace(go.Scatter(
    x=ages_proj, y=portfolio_with_kids_real,
    name="Portfolio with kids",
    line=dict(color=COLORS["blue"], width=3),
    fill="tonexty",
    fillcolor="rgba(100,180,255,0.10)",
    hovertemplate="With kids: $%{y:,.0f}<extra></extra>",
))

# FIRE target line
fig_port.add_hline(
    y=fire_target,
    line_dash="dash",
    line_color=COLORS["yellow"],
    annotation_text=f"FIRE Target: ${fire_target:,.0f}",
    annotation_position="top right",
)

# FIRE crossover markers
if ytf_no_kids and ytf_no_kids <= HORIZON:
    fig_port.add_vline(
        x=_current_age + ytf_no_kids,
        line_dash="dot", line_color=COLORS["mint"],
        annotation_text=f"FIRE no kids: age {_current_age + ytf_no_kids}",
        annotation_position="top left",
    )
if ytf_with_kids and ytf_with_kids <= HORIZON:
    fig_port.add_vline(
        x=_current_age + ytf_with_kids,
        line_dash="dot", line_color=COLORS["blue"],
        annotation_text=f"FIRE with kids: age {_current_age + ytf_with_kids}",
        annotation_position="bottom right",
    )

fig_port.update_layout(
    **CHART_LAYOUT,
    title=f"Portfolio Growth: With vs Without Kids (real $, {swr*100:.1f}% SWR target)",
    xaxis_title="Your age",
    yaxis_title="Portfolio value (real $)",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_port, use_container_width=True)

# Summary text
if ytf_no_kids and ytf_with_kids:
    delay = ytf_with_kids - ytf_no_kids
    port_gap = portfolio_no_kids_real[ytf_no_kids] - portfolio_with_kids_real[min(ytf_no_kids, HORIZON)]
    st.caption(
        f"At your baseline FIRE age (**{_current_age + ytf_no_kids}**), the kids gap is "
        f"**${port_gap:,.0f}** in real portfolio value — "
        f"representing roughly **{delay} year{'s' if delay != 1 else ''}** of delayed compounding. "
        f"The gap narrows as kids become financially independent."
    )

st.divider()

# ── Phase breakdown table ─────────────────────────────────────────────────────
st.subheader("📋 Cost Breakdown by Phase")

phases = [
    ("Birth & Setup", sum(costs.setup) + sum(costs.income_loss)),
    ("Childcare (age 0–4)", sum(costs.childcare) + sum(c for i, c in enumerate(costs.general) if any((b <= i < b + 5) for b in birth_yrs))),
    ("Primary School (age 5–11)", sum(s for i, s in enumerate(costs.school) if any((b + 5 <= i < b + 12) for b in birth_yrs))),
    ("High School (age 12–17)", sum(s for i, s in enumerate(costs.school) if any((b + 12 <= i < b + 18) for b in birth_yrs))),
    ("Housing premium", sum(costs.housing)),
]
phases = [(label, cost) for label, cost in phases if cost > 0]

tbl_cols = st.columns(len(phases))
for col, (label, cost) in zip(tbl_cols, phases):
    col.metric(label, f"${cost:,.0f}")

with st.expander("📖 Cost assumptions & methodology"):
    st.markdown(f"""
**Source**: Australian average cost estimates from child.md research.

| Phase | {kids_cost_label(schooling)} | Notes |
|---|---|---|
| Birth setup | ${setup_cost:,} one-off | Cot, pram, car seat, baby gear |
| Income loss | ${(leave_weeks * (_gross_income / 52) * (1 - leave_income_pct / 100)):,.0f} + ${(partner_leave_weeks * (_partner_income / 52) * (1 - leave_income_pct / 100)):,.0f} | You + partner, {leave_income_pct}% income retained |
| Childcare/yr | ${childcare_annual:,} per child | Ages 0–4 after CCS subsidy |
| Primary school/yr | {"${:,}".format(private_primary) if schooling == "private" else {"public": "$2,000", "catholic": "$8,000"}[schooling]} per child | School fees + activities |
| High school/yr | {"${:,}".format(private_high) if schooling == "private" else {"public": "$3,500", "catholic": "$12,000"}[schooling]} per child | School fees + teen expenses |
| General (food, clothing, activities) | $3,500–$6,000/yr | Grows through teen years |
| Housing premium | ${bigger_house_monthly:,}/mo | {"Applied birth to age 18" if bigger_house_monthly > 0 else "Not modelled"} |

**Key insight from research:** The biggest financial impact is usually *reduced savings rate* during
childcare years rather than permanent damage. FIRE timelines commonly shift **{ytf_with_kids - ytf_no_kids if (ytf_with_kids and ytf_no_kids) else "several"} years**
for a two-child household — with recovery as incomes grow and childcare ends.

**Income loss** is the most underestimated cost: a high earner taking 6 months at 50% income can
lose $30k–$60k+ compared to a full working year.
""")

st.divider()

# ── Export to profile ─────────────────────────────────────────────────────────
st.subheader("📤 Export to Profile")
st.caption(
    "Exporting saves your kids plan to the shared profile so it flows into **FIRE Scenarios** "
    "and **Budget & Savings** automatically."
)

export_vals: dict = {
    "pf_kids_enabled":                    kids_enabled,
    "pf_num_kids":                        num_kids,
    "pf_kid1_birth_yr_from_now":          kid1_birth,
    "pf_kid2_birth_yr_from_now":          kid2_birth if num_kids >= 2 else profile.get("pf_kid2_birth_yr_from_now"),
    "pf_kid3_birth_yr_from_now":          kid3_birth if num_kids >= 3 else profile.get("pf_kid3_birth_yr_from_now"),
    "pf_kids_schooling":                  schooling,
    "pf_kids_private_school_annual":      private_primary,
    "pf_kids_private_highschool_annual":  private_high,
    "pf_kids_childcare_annual":           childcare_annual,
    "pf_kids_setup_cost":                 setup_cost,
    "pf_parental_leave_weeks":            leave_weeks,
    "pf_parental_leave_partner_weeks":    partner_leave_weeks,
    "pf_parental_leave_income_pct":       leave_income_pct,
    "pf_partner_career_break_years":      partner_career_break_years,
    "pf_kids_bigger_house_extra_monthly": bigger_house_monthly,
}
profile.export_button(
    "Save Kids Plan to Profile",
    export_vals,
    help="Sends your kids plan to the shared profile. FIRE Scenarios will automatically include kids costs in the projection.",
)

if profile.get("pf_kids_enabled"):
    st.success(
        f"✅ Kids plan active — **{num_kids} child{'ren' if num_kids > 1 else ''}**, "
        f"{school_label} schooling. "
        f"Annual costs flow into FIRE Scenarios projection automatically."
    )
