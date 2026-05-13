"""Page 4: Australian Tax — income tax, super, HECS, CGT with current vs 2027 law toggle."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
from datetime import date

from utils.colors import COLORS
from engines.tax_engine import (
    CGTLaw, income_tax, medicare_levy, medicare_levy_surcharge, division_293_tax,
    hecs_repayment, super_concessional_tax, cgt_liability, effective_tax_rate,
    marginal_rate,
)

st.set_page_config(page_title="Australian Tax", page_icon="🦘", layout="wide")
st.title("🦘 Australian Tax")

with st.sidebar:
    st.header("💼 Income")
    gross_income   = st.number_input("Gross Income (AUD)",       min_value=0, value=120_000, step=5_000)
    super_contribs = st.number_input("Super Contributions/yr",  min_value=0, value=15_000,  step=1_000)
    hecs_balance   = st.number_input("HECS-HELP Balance",        min_value=0, value=25_000,  step=1_000)
    private_cover  = st.checkbox(
        "Private Hospital Cover",
        value=False,
        help="Holding an eligible private hospital policy exempts you from the Medicare Levy Surcharge.",
    )
    st.divider()
    st.header("📈 Capital Gains")
    cgt_gain   = st.number_input("Capital Gain (AUD)",  min_value=0, value=100_000, step=5_000)
    held_years = st.slider("Asset Held (Years)",         0.0, 30.0, 3.0, 0.5)
    st.divider()
    st.header("⚖️ CGT Law")
    use_proposed = st.toggle("Use Proposed July 2027 CGT Law", value=False)
    law = CGTLaw.PROPOSED_2027 if use_proposed else CGTLaw.CURRENT
    if use_proposed:
        st.warning(
            "⚠️ **Proposed only — not enacted law.**  "
            "These rules have NOT been legislated as of May 2026. "
            "Do not make financial decisions based solely on this model."
        )
        st.info("Proposed 2027: Indexation replaces 50% discount. 30% minimum tax floor applies.")
        cpi_acquisition = st.number_input("CPI at Acquisition", min_value=50.0, value=100.0, step=1.0)
        cpi_now         = st.number_input("CPI Now",            min_value=50.0, value=115.0, step=1.0)
        acquisition_dt  = st.date_input("Acquisition Date", value=date(2025, 1, 1))
        is_new_build    = st.checkbox("New Build (transitional lower tax)", value=False)
        cost_base       = st.number_input(
            "Asset Cost Base (AUD)", min_value=0, value=max(0, cgt_gain - 20_000), step=5_000
        )
    else:
        cpi_acquisition = cpi_now = None
        acquisition_dt  = None
        is_new_build    = False
        cost_base       = None

main_res = st.sidebar.checkbox("Main Residence (CGT Exempt)", value=False)

# ── Compute all tax components ────────────────────────────────────────────────
result = effective_tax_rate(
    gross_income, super_contribs, hecs_balance, cgt_gain, held_years, law,
    acquisition_date=acquisition_dt,
    cpi_at_acquisition=cpi_acquisition,
    cpi_current=cpi_now,
    is_main_residence=main_res,
    is_new_build=is_new_build,
    has_private_hospital_cover=private_cover,
)

# ── Display tax breakdown ─────────────────────────────────────────────────────
st.subheader(f"{'Proposed 2027' if use_proposed else 'Current'} CGT Law — Tax Breakdown")

row1_c1, row1_c2, row1_c3, row1_c4 = st.columns(4)
row1_c1.metric("Income Tax (+ LITO)",  f"${result['income_tax']:,.0f}",
               help="Progressive rates on ordinary income, after Low Income Tax Offset.")
row1_c2.metric("Medicare Levy",        f"${result['medicare_levy']:,.0f}",
               help="2% levy (phase-in zone $26k–$32.5k). Computed on combined income including CGT.")
row1_c3.metric("Medicare Levy Surcharge", f"${result['medicare_levy_surcharge']:,.0f}",
               help="MLS for singles without private hospital cover earning >$93k (0% if covered).")
row1_c4.metric("HECS Repayment",       f"${result['hecs_repayment']:,.0f}",
               help="Compulsory HECS-HELP repayment based on combined repayment income.")

row2_c1, row2_c2, row2_c3, row2_c4 = st.columns(4)
row2_c1.metric("Super Tax (15%)",      f"${result['super_tax']:,.0f}",
               help="15% flat tax on concessional super contributions.")
row2_c2.metric("Division 293 Tax",     f"${result['division_293_tax']:,.0f}",
               help="Extra 15% on concessional contributions where income + contributions > $250,000.")
row2_c3.metric("CGT",                  f"${result['cgt']:,.0f}",
               help="Capital gains tax using marginal rate at combined income (ordinary + CGT).")
row2_c4.metric("Effective Tax Rate",   f"{result['effective_rate']*100:.1f}%",
               help="Total tax ÷ (gross income + capital gain).")

st.metric("Net Take-Home", f"${result['net_income']:,.0f}",
          help="Gross income minus income tax (LITO-adjusted), Medicare levy, MLS, and HECS.")

st.divider()
st.subheader("Income Tax vs. Salary")
salaries  = list(range(0, 301_000, 5_000))
tax_vals  = [income_tax(s) for s in salaries]
levy_vals = [medicare_levy(s) for s in salaries]

fig = go.Figure()
fig.add_trace(go.Scatter(x=salaries, y=tax_vals,  name="Income Tax",
                          line=dict(color=COLORS["blue"],   width=2)))
fig.add_trace(go.Scatter(x=salaries, y=levy_vals, name="Medicare Levy",
                          line=dict(color=COLORS["teal"],   width=2)))
fig.add_trace(go.Scatter(x=salaries, y=[a + b for a, b in zip(tax_vals, levy_vals)],
                          name="Total", line=dict(color=COLORS["orange"], width=3)))
fig.add_vline(x=gross_income, line_dash="dash", line_color=COLORS["yellow"],
              annotation_text=f"You (${gross_income:,})", annotation_font_color=COLORS["yellow"])
fig.update_layout(
    template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
    xaxis_title="Annual Salary (AUD)", yaxis_title="Tax (AUD)", height=400,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width='stretch')

st.divider()
st.subheader("CGT: Current vs Proposed 2027 Law")

# Chart uses the marginal rate at gross_income for a fixed comparison baseline.
# (Gain amount varies along x-axis; marginal rate held constant at user's income level.)
chart_marg_rate = marginal_rate(gross_income)
gains    = list(range(0, 501_000, 10_000))
curr_cgt = [cgt_liability(g, held_years, chart_marg_rate, CGTLaw.CURRENT) for g in gains]
prop_cgt = [
    cgt_liability(g, held_years, chart_marg_rate, CGTLaw.PROPOSED_2027,
                  acquisition_date=date(2025, 1, 1),
                  cpi_at_acquisition=100.0, cpi_current=115.0)
    for g in gains
]
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=gains, y=curr_cgt, name="Current Law",
                           line=dict(color=COLORS["mint"],   width=2)))
fig2.add_trace(go.Scatter(x=gains, y=prop_cgt, name="Proposed 2027",
                           line=dict(color=COLORS["orange"], width=2)))
fig2.update_layout(
    template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
    xaxis_title="Capital Gain (AUD)", yaxis_title="CGT Liability (AUD)",
    height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig2, width='stretch')

if use_proposed:
    st.warning(
        "⚠️ **Legislative status:** The proposed July 2027 CGT rules have **not been enacted** "
        "as of May 2026. This is a modelling estimate based on publicly available proposals. "
        "Do not make irreversible financial decisions based on this projection alone."
    )
    st.info("""
**Proposed July 2027 CGT Law — Key Rules (as proposed):**
- Indexation replaces the 50% discount: only the real (inflation-adjusted) gain is taxed at your marginal rate.
- **30% minimum tax floor:** You always pay at least 30% of the nominal gain.
- **Main residence:** Still fully exempt.
- **New builds:** Transitional rule — taxed under the more favourable of current or proposed law.
    """)
