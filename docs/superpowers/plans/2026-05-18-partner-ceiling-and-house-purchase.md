# Partner Salary Ceiling & House Purchase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independent partner salary ceiling, a house purchase checkbox on the Home Deposit page that propagates mortgage data downstream, and remove the unused Net Wealth Calculator page.

**Architecture:** Shared profile (`utils/shared_profile.py`) is the single source of truth; UI pages read from it to pre-fill and write back via Export buttons. All new keys default to None/False so existing behaviour is unchanged for users who don't use the new features.

**Tech Stack:** Python, Streamlit, Plotly

---

### Task 1: shared_profile.py — add new profile keys

**Files:**
- Modify: `utils/shared_profile.py`

- [ ] Add 8 new keys to `PROFILE_DEFAULTS`:
  - `pf_partner_salary_ceiling: None`
  - `pf_wants_to_purchase: False`
  - `pf_property_value: None`
  - `pf_mortgage_loan_amount: None`
  - `pf_mortgage_monthly: None`
  - `pf_mortgage_rate: None`
  - `pf_loan_term_years: None`
  - `pf_purchase_years_from_now: None`

- [ ] Remove `pf_net_worth: None` from `PROFILE_DEFAULTS` (Net Wealth page is being deleted)

- [ ] Remove `pf_net_worth` metric from `sidebar_summary()` function

---

### Task 2: fire_dashboard.py — partner ceiling + remove net worth

**Files:**
- Modify: `fire_dashboard.py`

- [ ] In the Salary Growth section, after the main ceiling block, add a partner ceiling toggle visible only when `_partnered` is True

- [ ] In `Save Profile` button handler, add `profile.set_value("pf_partner_salary_ceiling", _p_salary_ceiling)`

- [ ] Remove `nw = profile.get("pf_net_worth")` and all its usages from the file

- [ ] Remove the `nw is None` branch from `_priority()` (Step 1: "Map your full balance sheet")

- [ ] Update Step 1 journey card tool hint from `"Net Wealth", "2"` to `"Budget & Savings", "1"`

- [ ] Update Step 3 journey card tool hint from `"Net Wealth", "2"` to `"Budget & Savings", "1"`

---

### Task 3: 04_Home_Deposit.py — partner ceiling + purchase checkbox

**Files:**
- Modify: `pages/04_Home_Deposit.py`

- [ ] In the Salary Growth sidebar section, after the main ceiling block, add a partner ceiling toggle/input (visible only when `_partnered`)

- [ ] Add `_proj_gross_partner(base_gross, yrs)` function that uses `p_salary_ceiling_today` instead of `salary_ceiling_today`

- [ ] Update `proj_household_gross()` to call `_proj_gross_partner` for partner instead of `_proj_gross_single`

- [ ] Update `_proj_gross_partner_at_purchase` to call `_proj_gross_partner` instead of `_proj_gross_single`

- [ ] After the Mortgage Serviceability section, add "I intend to purchase this property" checkbox (pre-fills from `pf_wants_to_purchase`)

- [ ] When checkbox is checked, show "After You Buy" metrics: projected net income, mortgage repayment, remaining after mortgage; info note that deposit is home equity not free cash

- [ ] Update the Export button to also push purchase/mortgage keys when checkbox is checked (or clear them when unchecked)

---

### Task 4: 01_Budget_Savings.py — mortgage pre-fill

**Files:**
- Modify: `pages/01_Budget_Savings.py`

- [ ] Before the `rent_mortgage` number_input, read `pf_wants_to_purchase` and `pf_mortgage_monthly` from profile

- [ ] Use mortgage amount as default value when purchase flag is set, otherwise keep 2200

- [ ] Add caption below the field when pre-filled

---

### Task 5: Remove Net Wealth page

**Files:**
- Delete: `pages/02_Net_Wealth.py`

- [ ] Delete the file

---

### Task 6: Launch and smoke test

- [ ] Run `streamlit run fire_dashboard.py` and verify all pages load
- [ ] Verify partner ceiling appears on dashboard when couple mode enabled
- [ ] Verify partner ceiling appears on Home Deposit sidebar when partnered
- [ ] Verify "I intend to purchase" checkbox appears and "After You Buy" section renders
- [ ] Verify Export pushes mortgage data; navigate to Budget — confirm rent/mortgage is pre-filled
- [ ] Verify Net Wealth page is gone from sidebar
- [ ] Run `python -m pytest tests/ -v` to confirm no regressions
