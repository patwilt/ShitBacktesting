"""
Shared Financial Profile — persists key inputs across all pages via session state.

Design contract:
  • The home page binds its widgets DIRECTLY to ``pf_*`` session keys, so every
    field on every page reads the latest value via ``profile.get(key)``.
  • Calculator pages READ from the profile to pre-fill their local widgets.
    Local edits stay local until the user clicks an "Export to Profile" button.
  • Export buttons MUST push back every field they collect from the user. If a
    page shows partner inputs, it must export the partner fields too — otherwise
    cross-page changes silently get dropped.

Australian income tax is calculated per individual, so partner fields are
tracked separately. Wealth fields that are not tax-affected (portfolio,
property, etc.) stay joint at the household level for simplicity.
"""
from __future__ import annotations

import streamlit as st

# ── Default values (used if profile hasn't been set) ──────────────────────────
PROFILE_DEFAULTS: dict[str, object] = {
    # Personal (you)
    "pf_age":              30,
    "pf_retirement_age":   65,
    "pf_birth_year":       1995,
    # Income (you)
    "pf_gross_income":     110_000,
    "pf_hecs_balance":     20_000,
    "pf_private_cover":    False,
    # Wealth (household-level, kept joint for simplicity)
    "pf_portfolio":        40_000,   # investable assets, excl. super and property
    "pf_super_balance":    75_000,   # YOUR super only when partnered (see helpers)
    # Partner (Australian tax is individual, so partner fields are tracked separately)
    "pf_partner_enabled":          False,
    "pf_partner_age":              30,
    "pf_partner_gross_income":     85_000,
    "pf_partner_hecs_balance":     0,
    "pf_partner_super_balance":    50_000,
    "pf_partner_private_cover":    False,
    # Assumptions (household-level)
    "pf_inflation":        2.5,      # % per year
    "pf_portfolio_return": 7.0,      # % per year, nominal
    "pf_swr":              4.0,      # % safe withdrawal rate
    # Calculated outputs (set by calculator pages)
    "pf_monthly_savings":  None,     # set by Budget page
    "pf_annual_spending":  None,     # set by Budget page
    "pf_net_worth":        None,     # set by Net Wealth page
}


def init() -> None:
    """Initialise session state with defaults for any missing keys."""
    for key, default in PROFILE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get(key: str):
    """Return the current profile value, falling back to the default."""
    init()
    return st.session_state.get(key, PROFILE_DEFAULTS.get(key))


def set_value(key: str, value) -> None:
    """Write a value back to the shared profile."""
    st.session_state[key] = value


def is_set() -> bool:
    """True if the user has explicitly saved the profile on the home page."""
    return bool(st.session_state.get("_profile_saved", False))


def is_partnered() -> bool:
    """True if the user has enabled partner mode."""
    init()
    return bool(st.session_state.get("pf_partner_enabled", False))


# ── Household aggregations ────────────────────────────────────────────────────
def household_gross_income() -> int:
    """Combined annual gross income across both partners (if enabled)."""
    init()
    total = int(get("pf_gross_income") or 0)
    if is_partnered():
        total += int(get("pf_partner_gross_income") or 0)
    return total


def household_super_balance() -> int:
    """Combined super balance across both partners (if enabled)."""
    init()
    total = int(get("pf_super_balance") or 0)
    if is_partnered():
        total += int(get("pf_partner_super_balance") or 0)
    return total


def household_hecs_balance() -> int:
    """Combined HECS-HELP balance across both partners (if enabled)."""
    init()
    total = int(get("pf_hecs_balance") or 0)
    if is_partnered():
        total += int(get("pf_partner_hecs_balance") or 0)
    return total


# ── Sidebar summary widget ─────────────────────────────────────────────────────
def sidebar_summary() -> None:
    """Render a compact read-only profile card in the sidebar."""
    init()
    partnered = is_partnered()
    title = "🔗 Household Profile" if partnered else "🔗 Your Financial Profile"
    with st.sidebar.expander(title, expanded=False):
        st.caption("Set on the home page. Pre-fills all calculators.")

        c1, c2 = st.columns(2)
        c1.metric("Age",       get("pf_age"))
        c2.metric("Retire At", get("pf_retirement_age"))

        income_label = "Household Income" if partnered else "Income"
        c1.metric(income_label, f"${household_gross_income():,.0f}")
        c2.metric("Portfolio",  f"${get('pf_portfolio'):,.0f}")

        super_label = "Household Super" if partnered else "Super"
        c1.metric(super_label, f"${household_super_balance():,.0f}")
        c2.metric("Inflation", f"{get('pf_inflation'):.1f}%")

        if partnered:
            st.caption(
                f"🧑 You: ${get('pf_gross_income'):,.0f} income · "
                f"${get('pf_super_balance'):,.0f} super  \n"
                f"🧑‍🤝‍🧑 Partner: ${get('pf_partner_gross_income'):,.0f} income · "
                f"${get('pf_partner_super_balance'):,.0f} super"
            )

        ms  = get("pf_monthly_savings")
        nw  = get("pf_net_worth")
        asp = get("pf_annual_spending")
        if ms is not None:
            st.metric("Monthly Savings", f"${ms:,.0f}", help="From Budget page")
        if asp is not None:
            st.metric("Annual Spending", f"${asp:,.0f}", help="From Budget page")
        if nw is not None:
            st.metric("Net Worth", f"${nw:,.0f}", help="From Net Wealth page")

        if not is_set():
            st.info("💡 Go to the **Home** page to set your profile.")
        else:
            badge = "👥 Couple mode" if partnered else "👤 Solo"
            st.success(f"✅ Profile saved · {badge}")


# ── Export button helper ───────────────────────────────────────────────────────
def export_button(label: str, values: dict[str, object], help: str = "") -> bool:
    """
    Render an 'Export to Profile' button. On click, writes all key-value pairs
    to session state and returns True.

    Pages with partner inputs MUST include partner keys in ``values`` whenever
    partner mode is active, otherwise partner edits made on the page silently
    fail to round-trip back to the profile.
    """
    clicked = st.button(f"📤 {label}", help=help or "Send these values to your shared profile.")
    if clicked:
        for key, value in values.items():
            set_value(key, value)
        set_value("_profile_saved", True)
        st.success("✅ Saved to profile. All pages will use these values.")
        return True
    return False
