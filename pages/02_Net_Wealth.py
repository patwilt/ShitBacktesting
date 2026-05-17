"""Net Wealth Calculator — assets minus liabilities with inflation-adjusted projections.

All projection figures can be viewed in nominal or real (inflation-adjusted) terms.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from utils.colors import COLORS, CHART_LAYOUT, CHART_BG
from utils import shared_profile as profile

st.set_page_config(page_title="Net Wealth Calculator", page_icon="💼", layout="wide")
profile.init()
st.title("💼 Net Wealth Calculator")
st.caption(
    "Steps 1 & 3 of your journey: record every asset and liability to know your true financial position, "
    "track your emergency fund, and plan debt repayment. "
    "30-year projections show where you're headed in real (inflation-adjusted) terms."
)

_partnered = profile.is_partnered()

# ── Input columns ─────────────────────────────────────────────────────────────
col_assets, col_liab = st.columns(2)

with col_assets:
    st.subheader("Assets")
    if _partnered:
        st.caption(
            "👥 Couple mode: super is tracked per-partner (Australian super accounts "
            "are individual). Other assets are joint household figures."
        )
    with st.expander("Cash & Liquid", expanded=True):
        cash_savings     = st.number_input("Cash / Savings Account ($)", min_value=0, value=25_000,  step=1_000)
        emergency_fund   = st.number_input("Emergency Fund ($)",          min_value=0, value=15_000,  step=1_000)
        term_deposits    = st.number_input("Term Deposits ($)",           min_value=0, value=0,       step=1_000)
    with st.expander("Investments", expanded=True):
        if _partnered:
            sc1, sc2 = st.columns(2)
            your_super_balance    = sc1.number_input("Your Super ($)",    min_value=0, value=profile.get("pf_super_balance"),         step=5_000)
            partner_super_balance = sc2.number_input("Partner Super ($)", min_value=0, value=profile.get("pf_partner_super_balance"), step=5_000)
            super_balance = your_super_balance + partner_super_balance
        else:
            super_balance = st.number_input("Superannuation ($)", min_value=0, value=profile.get("pf_super_balance"), step=5_000)
            your_super_balance, partner_super_balance = super_balance, 0
        shares_etfs      = st.number_input("Shares / ETFs ($)",           min_value=0, value=profile.get("pf_portfolio"),      step=5_000)
        crypto           = st.number_input("Crypto / Other Digital ($)",  min_value=0, value=5_000,   step=1_000)
        business         = st.number_input("Business Interests ($)",      min_value=0, value=0,       step=5_000)
    with st.expander("Property", expanded=True):
        ppor_value       = st.number_input("Owner-Occupied Property ($)", min_value=0, value=0,       step=25_000)
        investment_prop  = st.number_input("Investment Property ($)",     min_value=0, value=0,       step=25_000)
    with st.expander("Other", expanded=True):
        vehicle          = st.number_input("Vehicles ($)",                min_value=0, value=20_000,  step=1_000)
        other_assets     = st.number_input("Other Assets ($)",            min_value=0, value=5_000,   step=1_000)

with col_liab:
    st.subheader("Liabilities")
    with st.expander("Property Debt", expanded=True):
        ppor_mortgage    = st.number_input("PPOR Mortgage ($)",           min_value=0, value=0,       step=10_000)
        inv_prop_loan    = st.number_input("Investment Property Loan ($)", min_value=0, value=0,      step=10_000)
    with st.expander("Personal Debt", expanded=True):
        hecs_debt        = st.number_input("HECS-HELP Debt ($)",          min_value=0, value=22_000,  step=1_000)
        car_loan         = st.number_input("Car Loan ($)",                min_value=0, value=12_000,  step=1_000)
        personal_loan    = st.number_input("Personal Loan ($)",           min_value=0, value=0,       step=1_000)
        credit_card      = st.number_input("Credit Card Balance ($)",     min_value=0, value=3_000,   step=500)
    with st.expander("Other Debt", expanded=True):
        other_debt       = st.number_input("Other Debt ($)",              min_value=0, value=0,       step=1_000)

st.divider()

# ── Projection assumptions (sidebar) ─────────────────────────────────────────
with st.sidebar:
    profile.sidebar_summary()
    st.header("📈 Growth Assumptions")
    st.caption("Inflation and return pre-filled from profile.")
    inflation_rate    = st.slider("Inflation (%/yr)",           0.0, 8.0,  profile.get("pf_inflation"),        0.25) / 100.0
    investment_return = st.slider("Investment Return (%/yr)",   0.0, 15.0, profile.get("pf_portfolio_return"), 0.25) / 100.0
    super_return      = st.slider("Super Return (%/yr)",        0.0, 12.0, 7.5,  0.25) / 100.0
    property_growth   = st.slider("Property Growth (%/yr)",     0.0, 10.0, 4.0,  0.25) / 100.0
    cash_return       = st.slider("Cash / HISA Return (%/yr)",  0.0, 8.0,  4.5,  0.25) / 100.0
    vehicle_deprec    = st.slider("Vehicle Depreciation (%/yr)", 0.0, 20.0, 10.0, 1.0)  / 100.0

    st.divider()
    st.header("💳 Debt Repayments (Annual)")
    annual_mortgage_repay = st.number_input("Mortgage Repayments/yr ($)", min_value=0, value=0, step=5_000)
    annual_inv_repay      = st.number_input("Investment Loan Repay/yr ($)", min_value=0, value=0, step=5_000)
    annual_hecs_repay     = st.number_input("HECS Repayments/yr ($)",    min_value=0, value=6_000, step=1_000)
    annual_car_repay      = st.number_input("Car Loan Repay/yr ($)",      min_value=0, value=6_000, step=500)
    annual_personal_repay = st.number_input("Personal Loan Repay/yr ($)", min_value=0, value=0,    step=500)
    annual_cc_repay       = st.number_input("Credit Card Repay/yr ($)",   min_value=0, value=3_000, step=500)

    st.divider()
    st.header("💰 Annual Surplus to Invest")
    annual_investment_addition = st.number_input(
        "New $$ Invested/yr (excl. super)", min_value=0, value=15_000, step=1_000,
        help="Your estimated annual addition to shares/ETFs after all expenses and debt repayments."
    )
    annual_super_addition = st.number_input(
        "Super Contributions/yr (total)", min_value=0, value=18_000, step=1_000,
        help="Total super going in (employer + salary sacrifice)."
    )

    st.divider()
    horizon = st.slider("Projection Horizon (Years)", 5, 40, 20)
    show_real = st.toggle("Show Real (Inflation-Adjusted) Values", value=True)

# ── Totals ────────────────────────────────────────────────────────────────────
total_assets = (
    cash_savings + emergency_fund + term_deposits
    + super_balance + shares_etfs + crypto + business
    + ppor_value + investment_prop
    + vehicle + other_assets
)
total_liabilities = (
    ppor_mortgage + inv_prop_loan
    + hecs_debt + car_loan + personal_loan + credit_card
    + other_debt
)
net_worth = total_assets - total_liabilities

# ── Summary metrics ───────────────────────────────────────────────────────────
ma, ml, mn = st.columns(3)
ma.metric("Total Assets",       f"${total_assets:,.0f}")
ml.metric("Total Liabilities",  f"${total_liabilities:,.0f}")
sign = "+" if net_worth >= 0 else ""
mn.metric("Net Worth",          f"${net_worth:,.0f}",
          delta=f"{sign}{net_worth / total_assets * 100:.1f}% of assets" if total_assets > 0 else "N/A",
          delta_color="normal" if net_worth >= 0 else "inverse")

debt_ratio = total_liabilities / total_assets if total_assets > 0 else 0
if debt_ratio > 0.7:
    st.error(f"🚨 **High leverage:** Debt is {debt_ratio*100:.0f}% of assets. Prioritise paying down high-interest debt.")
elif debt_ratio > 0.4:
    st.warning(f"⚠️ **Moderate leverage:** Debt is {debt_ratio*100:.0f}% of assets. Monitor and reduce over time.")
elif total_liabilities > 0:
    st.success(f"✅ **Healthy balance sheet:** Debt is {debt_ratio*100:.0f}% of assets.")

st.divider()

# ── Current net worth breakdown ───────────────────────────────────────────────
st.subheader("Current Wealth Breakdown")

asset_labels = [
    "Cash & Savings", "Emergency Fund", "Term Deposits",
    "Superannuation", "Shares / ETFs", "Crypto / Digital", "Business",
    "PPOR Property", "Investment Property",
    "Vehicles", "Other",
]
asset_values = [
    cash_savings, emergency_fund, term_deposits,
    super_balance, shares_etfs, crypto, business,
    ppor_value, investment_prop,
    vehicle, other_assets,
]
asset_colors = [
    COLORS["teal"], COLORS["mint"], COLORS["light_blue"],
    COLORS["blue"], COLORS["purple"], COLORS["pink"], COLORS["lavender"],
    COLORS["green"], COLORS["cyan"],
    COLORS["yellow"], COLORS["muted"],
]

liab_labels = [
    "PPOR Mortgage", "Investment Loan",
    "HECS-HELP", "Car Loan", "Personal Loan", "Credit Card", "Other Debt",
]
liab_values = [
    ppor_mortgage, inv_prop_loan,
    hecs_debt, car_loan, personal_loan, credit_card, other_debt,
]

pie_col1, pie_col2 = st.columns(2)

with pie_col1:
    non_zero_assets = [(l, v, c) for l, v, c in zip(asset_labels, asset_values, asset_colors) if v > 0]
    if non_zero_assets:
        fig_pie = go.Figure(go.Pie(
            labels=[x[0] for x in non_zero_assets],
            values=[x[1] for x in non_zero_assets],
            marker_colors=[x[2] for x in non_zero_assets],
            hole=0.4,
            textinfo="percent+label",
        ))
        fig_pie.update_layout(
            template="plotly_white", paper_bgcolor=CHART_BG,
            title="Assets", height=380,
            legend=dict(font=dict(size=10)),
        )
        st.plotly_chart(fig_pie, width="stretch")

with pie_col2:
    non_zero_liab = [(l, v) for l, v in zip(liab_labels, liab_values) if v > 0]
    if non_zero_liab:
        fig_pie2 = go.Figure(go.Pie(
            labels=[x[0] for x in non_zero_liab],
            values=[x[1] for x in non_zero_liab],
            marker_colors=[COLORS["red"], COLORS["orange"], COLORS["yellow"],
                           COLORS["pink"], COLORS["lavender"], COLORS["purple"], COLORS["muted"]][:len(non_zero_liab)],
            hole=0.4,
            textinfo="percent+label",
        ))
        fig_pie2.update_layout(
            template="plotly_white", paper_bgcolor=CHART_BG,
            title="Liabilities", height=380,
            legend=dict(font=dict(size=10)),
        )
        st.plotly_chart(fig_pie2, width="stretch")
    else:
        st.info("No liabilities entered.")

st.divider()

# ── 30-year projection ────────────────────────────────────────────────────────
st.subheader(f"{'Real (Inflation-Adjusted)' if show_real else 'Nominal'} Net Worth Projection: {horizon} Years")

years = list(range(horizon + 1))
proj_net_worth, proj_assets, proj_liabs = [], [], []

# Running balances (nominal)
cash_bal      = cash_savings + emergency_fund + term_deposits
super_bal     = super_balance
invest_bal    = shares_etfs + crypto + business
ppor_val      = ppor_value
inv_prop_val  = investment_prop
vehicle_val   = vehicle
other_val     = other_assets

ppor_mort_bal = ppor_mortgage
inv_loan_bal  = inv_prop_loan
hecs_bal      = hecs_debt
car_bal       = car_loan
personal_bal  = personal_loan
cc_bal        = credit_card
other_dbt_bal = other_debt

for yr in years:
    cpi = (1 + inflation_rate) ** yr

    # Total assets (nominal)
    ta = (cash_bal + super_bal + invest_bal + ppor_val + inv_prop_val + vehicle_val + other_val)
    # Total liabilities (nominal, floored at 0)
    tl = max(ppor_mort_bal, 0) + max(inv_loan_bal, 0) + max(hecs_bal, 0) + \
         max(car_bal, 0) + max(personal_bal, 0) + max(cc_bal, 0) + max(other_dbt_bal, 0)

    nw = ta - tl
    proj_assets.append(ta / cpi if show_real else ta)
    proj_liabs.append(tl / cpi if show_real else tl)
    proj_net_worth.append(nw / cpi if show_real else nw)

    if yr < horizon:
        # Grow assets
        cash_bal     *= (1 + cash_return)
        super_bal     = super_bal * (1 + super_return) + annual_super_addition
        invest_bal    = invest_bal * (1 + investment_return) + annual_investment_addition
        ppor_val     *= (1 + property_growth)
        inv_prop_val *= (1 + property_growth)
        vehicle_val  *= (1 - vehicle_deprec)
        vehicle_val   = max(vehicle_val, 1_000)

        # Pay down debt (floor at 0)
        ppor_mort_bal  = max(ppor_mort_bal  - annual_mortgage_repay, 0)
        inv_loan_bal   = max(inv_loan_bal   - annual_inv_repay,      0)
        hecs_bal       = max(hecs_bal       - annual_hecs_repay,     0)
        car_bal        = max(car_bal        - annual_car_repay,       0)
        personal_bal   = max(personal_bal   - annual_personal_repay,  0)
        cc_bal         = max(cc_bal         - annual_cc_repay,        0)

fig_proj = go.Figure()

fig_proj.add_trace(go.Scatter(
    x=years, y=proj_assets,
    name="Total Assets",
    fill="tozeroy",
    fillcolor="rgba(78,154,114,0.15)",
    line=dict(color=COLORS["mint"], width=2),
))
fig_proj.add_trace(go.Scatter(
    x=years, y=proj_liabs,
    name="Total Liabilities",
    fill="tozeroy",
    fillcolor="rgba(168,72,72,0.15)",
    line=dict(color=COLORS["red"], width=2),
))
fig_proj.add_trace(go.Scatter(
    x=years, y=proj_net_worth,
    name="Net Worth",
    line=dict(color=COLORS["blue"], width=3),
))
fig_proj.add_hline(y=0, line_dash="dash", line_color=COLORS["muted"], line_width=1)

label = "Real" if show_real else "Nominal"
fig_proj.update_layout(
    **CHART_LAYOUT,
    xaxis_title="Years from Now",
    yaxis_title=f"AUD ({label})",
    height=440,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_proj, width="stretch")

# ── Milestones table ──────────────────────────────────────────────────────────
st.subheader("Wealth Milestones")
milestones = [1, 3, 5, 10, 15, 20, 25, 30]
milestones = [m for m in milestones if m <= horizon]
cols = st.columns(len(milestones))
for col, m in zip(cols, milestones):
    idx = min(m, horizon)
    nw_val = proj_net_worth[idx]
    real_or_nom = f"{'Real $' if show_real else 'Nom $'}"
    col.metric(f"Year {m}", f"${nw_val:,.0f}", help=f"{real_or_nom} net worth at year {m}.")

st.divider()

# ── Export to Profile ─────────────────────────────────────────────────────────
st.subheader("Send to Profile")
st.caption(
    "Export your net worth and investable portfolio to the shared profile. "
    "The Dashboard, FIRE Scenarios, and other pages will pre-fill from these values."
)
exp_col1, exp_col2 = st.columns([2, 1])
invest_assets = shares_etfs + crypto + business
with exp_col1:
    if _partnered:
        st.info(
            f"**Net Worth:** ${net_worth:,.0f}  ·  "
            f"**Portfolio (shares+ETFs):** ${invest_assets:,.0f}  ·  "
            f"**Super (you / partner):** ${your_super_balance:,.0f} / ${partner_super_balance:,.0f}"
        )
    else:
        st.info(
            f"**Net Worth:** ${net_worth:,.0f}  ·  "
            f"**Investment Portfolio (shares+ETFs):** ${invest_assets:,.0f}  ·  "
            f"**Super:** ${super_balance:,.0f}"
        )
with exp_col2:
    nw_export: dict[str, object] = {
        "pf_net_worth":     net_worth,
        "pf_portfolio":     invest_assets,
        "pf_super_balance": your_super_balance,
    }
    if _partnered:
        nw_export["pf_partner_super_balance"] = partner_super_balance
    profile.export_button(
        "Export Net Worth & Portfolio to Profile",
        nw_export,
        help="Updates the shared profile so FIRE, Dashboard, and Super pages use these figures. "
             "When partnered, your super and partner super are exported separately.",
    )

st.divider()

# ── Balance sheet table ───────────────────────────────────────────────────────
with st.expander("📋 Full Balance Sheet & Assumptions"):
    st.markdown("#### Balance Sheet")
    rows = []
    for label, val in zip(asset_labels, asset_values):
        if val > 0:
            rows.append(f"| {label} | ${val:,.0f} | Asset |")
    for label, val in zip(liab_labels, liab_values):
        if val > 0:
            rows.append(f"| {label} | ${val:,.0f} | Liability |")
    st.markdown(
        "| Item | Value | Type |\n|---|---|---|\n" + "\n".join(rows)
        + f"\n| **Net Worth** | **${net_worth:,.0f}** | |"
    )

    st.markdown("#### Projection Assumptions")
    st.markdown(f"""
| Parameter | Rate |
|---|---|
| Inflation | {inflation_rate*100:.2f}%/yr |
| Investment Return | {investment_return*100:.2f}%/yr |
| Super Return | {super_return*100:.2f}%/yr |
| Property Growth | {property_growth*100:.2f}%/yr |
| Cash / HISA | {cash_return*100:.2f}%/yr |
| Vehicle Depreciation | {vehicle_deprec*100:.2f}%/yr |

Real $ values deflate nominal by CPI compounded at {inflation_rate*100:.2f}%/yr.

⚠️ This is a planning model only. Returns are not guaranteed.
""")
