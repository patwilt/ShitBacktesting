"""
Australian Financial Planner - home page and shared Financial Profile.
Run: streamlit run fire_dashboard.py
"""
from __future__ import annotations

import streamlit as st

from utils.csv_loader import find_csv_on_disk, load_from_uploaded_file, load_latest_backtest_csv
from utils import shared_profile as profile
from utils import ui

st.set_page_config(
    page_title="Australian Financial Planner",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

profile.init()
ui.inject_base_styles()

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Step cards ─────────────────────────────────────────────────────────── */
.step-card {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 12px;
    border-left: 4px solid #9E9590;
    box-shadow: 0 1px 4px rgba(44,37,32,0.07);
}
.step-tag {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.8px;
    margin-bottom: 5px;
}
.step-title {
    font-size: 16px;
    font-weight: 700;
    color: #2C2520;
    margin-bottom: 7px;
}
.step-body {
    font-size: 13px;
    color: #5A5048;
    line-height: 1.65;
    margin-bottom: 6px;
}
.step-why {
    font-size: 12px;
    color: #8A8480;
    line-height: 1.55;
    font-style: italic;
    border-top: 1px solid #E8E4DC;
    padding-top: 7px;
    margin-top: 7px;
}
.step-status {
    font-size: 12px;
    margin-top: 9px;
    padding: 6px 10px;
    border-radius: 6px;
    background: rgba(44,37,32,0.04);
}

/* ── Progress bar row ───────────────────────────────────────────────────── */
.progress-bar {
    display: flex;
    gap: 6px;
    margin-bottom: 20px;
}
.progress-pill {
    flex: 1;
    border-radius: 8px;
    padding: 10px 8px;
    text-align: center;
    opacity: 0.5;
    transition: opacity 0.2s;
}
.progress-pill.active {
    opacity: 1;
    box-shadow: 0 0 0 2px rgba(44,37,32,0.15);
}
.progress-pill-step {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.8;
    margin-bottom: 3px;
}
.progress-pill-label {
    font-size: 11px;
    font-weight: 600;
    line-height: 1.35;
    color: #2C2520;
}

/* ── Priority callout ───────────────────────────────────────────────────── */
.priority-box {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 16px 20px;
    border: 1px solid #E8E4DC;
    margin-bottom: 20px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    box-shadow: 0 1px 4px rgba(44,37,32,0.06);
}
.priority-icon {
    font-size: 26px;
    line-height: 1;
    flex-shrink: 0;
}
.priority-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #8A8480;
    margin-bottom: 3px;
}
.priority-heading {
    font-size: 15px;
    font-weight: 700;
    color: #2C2520;
    margin-bottom: 4px;
}
.priority-text {
    font-size: 13px;
    color: #5A5048;
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)

# ── Hero ───────────────────────────────────────────────────────────────────────
st.title("🔥 Australian Financial Planner")
st.markdown(
    "A systematic, evidence-based toolkit for building wealth in Australia: "
    "budgeting, home deposits, FIRE planning, super, and portfolio backtesting.  \n"
    "**Set your profile once below.** Every calculator pre-fills from it automatically."
)

st.divider()

# ── Financial Profile ──────────────────────────────────────────────────────────
ui.section_header(
    "Your Financial Profile",
    "Enter your numbers here once. Every calculator page reads from this profile. "
    "You can still override values locally on any individual page.",
)

# Partner toggle lives OUTSIDE the form so it can immediately show/hide partner fields.
# Australian tax is individual, so the calculators compute each partner's tax separately.
_partnered = st.toggle(
    "👥  Include a partner (model as a couple)",
    key="pf_partner_enabled",
    help="Australian income tax is calculated individually for each partner. "
         "Enable this to add a partner's salary, super, and HECS for accurate household projections.",
)

with st.form("profile_form"):
    st.markdown("**🧑 You**")
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    age       = r1c1.number_input("Current Age",            min_value=18, max_value=80,    value=profile.get("pf_age"),              step=1)
    ret_age   = r1c2.number_input("Retirement Age",         min_value=40, max_value=100,   value=profile.get("pf_retirement_age"),   step=1)
    birth_yr  = r1c3.number_input("Birth Year",             min_value=1940, max_value=2006, value=profile.get("pf_birth_year"),      step=1)
    priv_cover = r1c4.checkbox("Private Hospital Cover",    value=profile.get("pf_private_cover"))

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    gross_inc = r2c1.number_input("Gross Annual Income ($)",  min_value=0, value=profile.get("pf_gross_income"),  step=5_000)
    hecs      = r2c2.number_input("HECS-HELP Balance ($)",    min_value=0, value=profile.get("pf_hecs_balance"),  step=1_000)
    super_bal = r2c3.number_input("Your Super Balance ($)",   min_value=0, value=profile.get("pf_super_balance"), step=5_000)
    r2c4.markdown("")

    # Partner fields appear only when partner mode is enabled.
    if _partnered:
        st.divider()
        st.markdown("**🧑‍🤝‍🧑 Your Partner**")
        p1c1, p1c2, p1c3, p1c4 = st.columns(4)
        p_age        = p1c1.number_input("Partner Age",                  min_value=18, max_value=80,
                                          value=profile.get("pf_partner_age"), step=1, key="ui_p_age")
        p_gross      = p1c2.number_input("Partner Gross Income ($)",     min_value=0,
                                          value=profile.get("pf_partner_gross_income"), step=5_000, key="ui_p_gross")
        p_hecs       = p1c3.number_input("Partner HECS-HELP ($)",        min_value=0,
                                          value=profile.get("pf_partner_hecs_balance"), step=1_000, key="ui_p_hecs")
        p_super      = p1c4.number_input("Partner Super ($)",            min_value=0,
                                          value=profile.get("pf_partner_super_balance"), step=5_000, key="ui_p_super")
        p_priv_cover = st.checkbox("Partner has Private Hospital Cover",
                                    value=profile.get("pf_partner_private_cover"), key="ui_p_priv")
    else:
        p_age = p_gross = p_hecs = p_super = None
        p_priv_cover = None

    st.divider()
    st.markdown("**🏦 Household Wealth & Assumptions**")
    r3c1, r3c2, r3c3, r3c4 = st.columns(4)
    portfolio  = r3c1.number_input("Investment Portfolio ($)",  min_value=0, value=profile.get("pf_portfolio"),     step=5_000,
                                    help="Combined household shares, ETFs, and cash savings (excludes super and property).")
    inflation  = r3c2.number_input("Inflation (%/yr)",         min_value=0.0, max_value=15.0, value=profile.get("pf_inflation"),        step=0.25, format="%.2f")
    port_ret   = r3c3.number_input("Portfolio Return (%/yr)",   min_value=0.0, max_value=25.0, value=profile.get("pf_portfolio_return"), step=0.25, format="%.2f")
    swr        = r3c4.number_input("Safe Withdrawal Rate (%)",  min_value=1.0, max_value=10.0, value=profile.get("pf_swr"),              step=0.25, format="%.2f")

    saved = st.form_submit_button("💾 Save Profile", type="primary")

if saved:
    profile.set_value("pf_age",              age)
    profile.set_value("pf_retirement_age",   ret_age)
    profile.set_value("pf_birth_year",       birth_yr)
    profile.set_value("pf_gross_income",     gross_inc)
    profile.set_value("pf_hecs_balance",     hecs)
    profile.set_value("pf_portfolio",        portfolio)
    profile.set_value("pf_super_balance",    super_bal)
    profile.set_value("pf_inflation",        inflation)
    profile.set_value("pf_portfolio_return", port_ret)
    profile.set_value("pf_swr",              swr)
    profile.set_value("pf_private_cover",    priv_cover)
    if _partnered:
        profile.set_value("pf_partner_age",            p_age)
        profile.set_value("pf_partner_gross_income",   p_gross)
        profile.set_value("pf_partner_hecs_balance",   p_hecs)
        profile.set_value("pf_partner_super_balance",  p_super)
        profile.set_value("pf_partner_private_cover",  p_priv_cover)
    profile.set_value("_profile_saved",      True)
    st.success("✅ Profile saved. All calculator pages are now pre-filled.")

# Show calculated outputs pushed back from tool pages
ms  = profile.get("pf_monthly_savings")
asp = profile.get("pf_annual_spending")
nw  = profile.get("pf_net_worth")

if ms is not None or asp is not None or nw is not None:
    st.markdown("**Values calculated by your tools:**")
    _pcols = st.columns(3)
    if ms is not None:
        _pcols[0].metric("Monthly Savings", f"${ms:,.0f}",  help="From Budget & Savings Rate page")
    if asp is not None:
        _pcols[1].metric("Annual Spending",  f"${asp:,.0f}", help="From Budget & Savings Rate page")
    if nw is not None:
        _pcols[2].metric("Net Worth",        f"${nw:,.0f}",  help="From Net Wealth Calculator")

st.divider()

# ── Journey section ────────────────────────────────────────────────────────────
ui.section_header(
    "Your Financial Journey",
    "Work through these steps in order. Skip any that don't apply, but sequence matters. "
    "Each step links to the calculator built for it.",
)

# ── Priority detection ─────────────────────────────────────────────────────────
_gross     = profile.get("pf_gross_income") or 110_000
_portfolio = profile.get("pf_portfolio") or 0
_super     = profile.get("pf_super_balance") or 0
_hecs      = profile.get("pf_hecs_balance") or 0

# Rough after-tax income approximation (ignores HECS, MLS edge cases)
_approx_net_annual = _gross * 0.72
_savings_rate_est  = (ms * 12 / _approx_net_annual) if (ms is not None and _approx_net_annual > 0) else None


def _priority() -> tuple[int, str, str]:
    """
    Returns (step_number, heading, explanation) for the smart priority callout.
    Mirrors the logic of the Personal Income Spending Flowchart.
    """
    if ms is None:
        return (0,
                "Start with your budget",
                "You haven't mapped your cashflow yet. Until you know your monthly surplus, "
                "every other decision is guesswork. Run the Budget & Savings Rate calculator first.")
    if ms < 0:
        return (0,
                "Spending exceeds income: fix this first",
                f"You're currently spending ${-ms:,.0f}/month more than you earn after tax. "
                "No investment plan works without positive cashflow. Reduce discretionary expenses "
                "or look for ways to increase income before anything else.")
    if nw is None:
        return (1,
                "Map your full balance sheet",
                "Run the Net Wealth Calculator to record your assets and liabilities, including "
                "your emergency fund. You need to know where you stand before deciding what to do next.")
    if _savings_rate_est is not None and _savings_rate_est < 0.05:
        return (0,
                "Savings rate is very low: revisit your budget",
                f"Your savings rate is approximately {_savings_rate_est*100:.0f}% of take-home pay. "
                "Aim for at least 15–20%. Small cuts to variable spending compound into major "
                "long-term wealth differences.")
    if _hecs > 30_000 and _portfolio < 10_000:
        return (3,
                "Build savings before aggressive debt paydown",
                f"You have a HECS-HELP balance of ${_hecs:,.0f}. HECS is indexed to CPI and "
                "compulsory repaid through payroll, so it generally doesn't need manual extra repayments. "
                "Focus first on any high-interest debt (credit cards, personal loans), then build your "
                "emergency fund and investment portfolio.")
    if _savings_rate_est is not None and _savings_rate_est >= 0.20 and _portfolio > 30_000:
        return (6,
                "You're ready to optimise your investment strategy",
                f"Strong savings rate (~{_savings_rate_est*100:.0f}%) and a growing portfolio. "
                "Your focus now is refining your asset allocation, super contributions, and FIRE timeline. "
                "Use the FIRE Scenarios page to model your path to financial independence.")
    if _savings_rate_est is not None and _savings_rate_est >= 0.15:
        return (5,
                "Consider salary sacrificing into super",
                f"Good savings rate (~{_savings_rate_est*100:.0f}%). With a stable cashflow, "
                "salary sacrificing into super up to the $30,000 concessional cap is likely your "
                "highest tax-efficiency move. Run the Super Calculator to model the impact.")
    return (4,
            "Set a goal for your surplus savings",
            "Your cashflow is positive. Now decide where your surplus goes: a home deposit, "
            "growing your emergency fund, or beginning to invest in the market. "
            "Use the Home Deposit Planner or FIRE Scenarios pages to map your options.")


_step_num, _priority_heading, _priority_text = _priority()

# Step colours (matching flowchart)
STEP_COLORS = {
    0: "#8A8480",   # Stone grey     - Budget
    1: "#A84848",   # Muted brick    - Emergency Fund
    2: "#C08A38",   # Warm amber     - Employer Super
    3: "#4E9A72",   # Sage green     - Pay Down Debt
    4: "#7060A8",   # Dusty purple   - Large Goals
    5: "#4275A0",   # Dusty blue     - Optimise Super
    6: "#5A7250",   # Muted olive    - Invest & FIRE
}
STEP_NAMES = {
    0: "Budget",
    1: "Emergency Fund",
    2: "Super Matching",
    3: "Pay Down Debt",
    4: "Large Goals",
    5: "Optimise Super",
    6: "Invest & FIRE",
}

# ── Progress bar ───────────────────────────────────────────────────────────────
pills_html = '<div class="progress-bar">'
for s, name in STEP_NAMES.items():
    colour = STEP_COLORS[s]
    active_cls = "active" if s == _step_num else ""
    pills_html += f"""
    <div class="progress-pill {active_cls}" style="background:{colour}20;border:1px solid {colour}55;">
      <div class="progress-pill-step" style="color:{colour};">Step {s}</div>
      <div class="progress-pill-label" style="color:#2C2520;">{name}</div>
    </div>"""
pills_html += "</div>"
st.markdown(pills_html, unsafe_allow_html=True)

# ── Priority callout ───────────────────────────────────────────────────────────
_col = STEP_COLORS[_step_num]
st.markdown(f"""
<div class="priority-box" style="border-left:4px solid {_col};">
  <div class="priority-icon">🎯</div>
  <div>
    <div class="priority-label">Your current focus: Step {_step_num}: {STEP_NAMES[_step_num]}</div>
    <div class="priority-heading">{_priority_heading}</div>
    <div class="priority-text">{_priority_text}</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")


# ── Step card helper ───────────────────────────────────────────────────────────
def _step_card(
    step: int,
    title: str,
    body: str,
    why: str,
    tool: str,          # sidebar page name(s), shown as navigation hint
    page_num: str = "", # sidebar page number(s) e.g. "1" or "2 & 3"
    status_html: str = "",
) -> None:
    colour = STEP_COLORS[step]
    active_marker = " ← You are here" if step == _step_num else ""
    st.markdown(f"""
<div class="step-card" style="border-left-color:{colour};">
  <div class="step-tag" style="color:{colour};">Step {step}{active_marker}</div>
  <div class="step-title">{title}</div>
  <div class="step-body">{body}</div>
  <div class="step-why">{why}</div>
  {f'<div class="step-status" style="color:{colour};">{status_html}</div>' if status_html else ""}
</div>
""", unsafe_allow_html=True)
    page_hint = f" (sidebar page {page_num})" if page_num else " in the sidebar"
    st.caption(f"→ **{tool}**{page_hint}")


# ── Two-column layout: steps 0–2 left, steps 3–5 right ────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    # Step 0: Budget
    _s0_status = ""
    if ms is not None:
        if ms < 0:
            _s0_status = f"🔴 Spending exceeds income by ${-ms:,.0f}/month"
        elif _savings_rate_est is not None and _savings_rate_est < 0.10:
            _s0_status = f"⚠️ Savings rate ~{_savings_rate_est*100:.0f}%, aim for 20%+"
        elif _savings_rate_est is not None:
            _s0_status = f"✅ ~{_savings_rate_est*100:.0f}% savings rate · ${ms:,.0f}/month surplus"

    _step_card(
        0,
        "Create Your Budget",
        "Map exactly where your money goes after Australian tax. Calculate your real take-home "
        "pay (after income tax, Medicare levy, and HECS), categorise your spending into fixed and "
        "discretionary, and find your monthly surplus.",
        "Cashflow clarity is the foundation of every financial decision. Without knowing your surplus, "
        "every subsequent step is guesswork.",
        "Budget Savings", "1",
        _s0_status,
    )

    # Step 1: Emergency Fund
    _s1_status = ""
    if nw is not None:
        _s1_status = "✅ Net wealth calculated. Check your liquid cash vs. 1–3 months of expenses"
    elif profile.is_set():
        _s1_status = "→ Run Net Wealth Calculator to record your emergency fund and full balance sheet"

    _step_card(
        1,
        "Build Your Emergency Fund",
        "Start with 1 month of total expenses in a high-interest savings account. "
        "Once the foundations below are done, grow this to 3–6 months. "
        "Keep it separate from your everyday account. Friction is a feature, not a bug.",
        "An emergency fund prevents you selling investments at the worst possible time. "
        "It is not an investment. It is financial insurance.",
        "Net Wealth", "2",
        _s1_status,
    )

    # Step 2: Employer Super Matching
    _s2_status = ""
    if _super > 0:
        _s2_status = f"Super balance: ${_super:,.0f}. Confirm you're receiving full employer SG contributions"

    _step_card(
        2,
        "Capture Employer Super Contributions",
        "Confirm your employer is paying the 11.5% Superannuation Guarantee (SG) into your chosen fund. "
        "If they match voluntary salary sacrifice contributions, maximise that benefit before any other "
        "investing. It is an immediate, guaranteed return.",
        "Employer SG contributions are the single best guaranteed return available to you. "
        "Never leave free employer matching on the table.",
        "Super Calculator", "3",
        _s2_status,
    )

with col_right:
    # Step 3: High-Interest Debt
    _s3_status = ""
    if _hecs > 0:
        _s3_status = f"HECS balance: ${_hecs:,.0f}, generally low priority vs. other debts (CPI-indexed, salary-deducted)"

    _step_card(
        3,
        "Eliminate High-Interest Debt",
        "If you have credit cards, personal loans, or any debt above ~10% interest: clear it "
        "before investing. Use the <strong>Avalanche method</strong> (highest rate first) for lowest total cost, "
        "or the <strong>Snowball method</strong> (smallest balance first) for psychological momentum. "
        "Moderate debt (4.5–10%) can be run alongside investing. Run the numbers.",
        "A 19% credit card rate is a guaranteed -19% return. No investment consistently beats that. "
        "Paying off high-interest debt is the highest risk-adjusted return available to you.",
        "Net Wealth", "2",
        _s3_status,
    )

    # Step 4: Large Near-Term Goals
    _step_card(
        4,
        "Plan for Large Near-Term Goals",
        "If you're targeting a home deposit, a vehicle purchase, extended travel, or a career change "
        "requiring a financial runway: build a dedicated savings goal. "
        "The Home Deposit Planner calculates exactly how much you need to save each month, "
        "accounting for property price growth and inflation.",
        "Mixing your home deposit savings with your investment portfolio usually means doing both poorly. "
        "Separate your goals into separate accounts. Clarity and commitment compound.",
        "Home Deposit", "4",
    )

    # Step 5: Super Optimisation
    _step_card(
        5,
        "Optimise Super Contributions",
        "Once high-interest debt is cleared, consider salary sacrificing into super up to the "
        "$30,000 concessional cap. Super contributions are taxed at 15%, far below the 32.5–47% "
        "most Australians pay on marginal income. Use Division 293 awareness if your income "
        "exceeds $250,000. But don't over-contribute if you have near-term liquidity needs.",
        "Super is your most tax-efficient long-term vehicle. Compounding at lower tax rates inside "
        "super over 20–30 years is transformative, but it's locked away until preservation age (~60).",
        "Super Calculator", "3",
    )

# Step 6 full-width: Long-term Investing & FIRE
_s6_status = ""
if _portfolio > 0:
    _s6_status = f"Investment portfolio: ${_portfolio:,.0f} · Run FIRE Scenarios to model your timeline"

_step_card(
    6,
    "Invest for Long-Term Wealth & FIRE",
    "With a budget, emergency fund, employer super secured, and high-interest debt cleared, invest "
    "your monthly surplus. Low-cost, diversified index ETFs are the evidence-based default for "
    "long-term wealth. Invest consistently. Frequency and discipline beat timing. "
    "Use the FIRE tools to model when your portfolio can sustain your lifestyle without employment income.",
    "Time in the market beats timing the market. A consistent DCA strategy into a globally diversified "
    "index ETF portfolio has historically been the most reliable path to long-term wealth for "
    "the majority of investors. Evidence, not hype.",
    "FIRE Scenarios · Retirement Drawdown · Portfolio Analytics", "5 → 8",
    _s6_status,
)

st.divider()

# ── FIRE & Backtest Tools ──────────────────────────────────────────────────────
with st.expander("📊 FIRE & Portfolio Backtest Data", expanded=False):
    st.caption(
        "FIRE Scenarios, Retirement Drawdown, Historical Outcomes, and Portfolio Analytics "
        "use rolling historical backtest data. Load a CSV or use the bundled sample below."
    )

    has_disk_data    = find_csv_on_disk() is not None
    has_session_data = "backtest_data" in st.session_state

    if has_disk_data or has_session_data:
        result = load_latest_backtest_csv()
        if result:
            data, source = result
            if has_session_data and not has_disk_data:
                st.success(
                    f"✅ **Uploaded data active**: `{source}` "
                    f"({len(data.strategies)} strategies: {', '.join(data.strategies)})"
                )
            else:
                is_sample = "sample" in source.replace("\\", "/")
                label = "📦 **Bundled sample data**" if is_sample else "📊 **Local backtest data**"
                st.info(
                    f"{label}: `{source.split('/')[-1]}` "
                    f"({len(data.strategies)} strategies: {', '.join(data.strategies)})"
                )
            if has_session_data:
                if st.button("🗑️ Clear uploaded data (revert to disk/sample)", type="secondary"):
                    del st.session_state["backtest_data"]
                    st.session_state.pop("backtest_path", None)
                    st.rerun()
    else:
        st.error(
            "⚠️ **No backtest data found.** "
            "Generate data by running `rolling_backtest_suite.py`, or upload a CSV below."
        )

    with st.expander(
        "📂 Upload a backtest CSV" if (has_disk_data or has_session_data)
        else "📂 Upload a backtest CSV (required)",
        expanded=not (has_disk_data or has_session_data),
    ):
        st.markdown(
            "Upload a `rolling_msci_strategies_results.csv` exported by `rolling_backtest_suite.py`.  \n"
            "Uploaded data takes priority over any file on disk for this session."
        )
        uploaded = st.file_uploader(
            "Choose CSV file",
            type="csv",
            help="Must contain columns like 'Strategy Name CAGR' and 'Strategy Name MDD'.",
        )
        if uploaded is not None:
            try:
                new_data, new_path = load_from_uploaded_file(uploaded)
                if not new_data.strategies:
                    st.error("❌ No strategy columns found.")
                else:
                    st.session_state["backtest_data"] = new_data
                    st.session_state["backtest_path"] = uploaded.name
                    st.success(
                        f"✅ Loaded **{uploaded.name}**: "
                        f"{len(new_data.strategies)} strategies: {', '.join(new_data.strategies)}"
                    )
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to parse CSV: {e}")

ui.spacer(3)

ui.callout(
    "caution",
    "This tool is for educational and modelling purposes only. It does not constitute "
    "financial advice. Past performance does not guarantee future results. "
    "Consult a licensed financial adviser before making investment decisions.",
    title="Disclaimer",
)
