# Partner Salary Ceiling & House Purchase Design

**Date:** 2026-05-18

---

## Feature 1: Partner Salary Ceiling

**Problem:** The partner's salary projection in `04_Home_Deposit.py` incorrectly applies the main user's salary ceiling. Each partner needs an independent cap.

**Solution:**
- Add `pf_partner_salary_ceiling: None` to `shared_profile.py`
- Add a partner ceiling toggle + input on the home page (`fire_dashboard.py`) in the Salary Growth section (visible only in couple mode)
- Add a matching local-override toggle in the Home Deposit sidebar (matches existing pattern for main salary)
- Split `_proj_gross_single` into two callsites — one for each partner — each using the correct ceiling

---

## Feature 2: House Purchase Checkbox

**Checkbox location:** Home Deposit page, after the Mortgage Serviceability section.

**Behaviour when checked:**
- Shows an "After You Buy" metrics section:
  - Projected net monthly income at purchase date
  - Monthly mortgage repayment
  - Remaining income after mortgage (with cashflow verdict)
  - Info note: deposit is locked as home equity, not free investable cash
- Export button also pushes purchase/mortgage data to profile

**Downstream profile propagation:**
- `pf_wants_to_purchase: bool`
- `pf_property_value` — nominal future property price at purchase
- `pf_mortgage_loan_amount` — loan amount
- `pf_mortgage_monthly` — monthly repayment
- `pf_mortgage_rate` — interest rate
- `pf_loan_term_years` — loan term
- `pf_purchase_years_from_now` — years until purchase

**Budget page:** Pre-fills "Rent / Mortgage ($)" from `pf_mortgage_monthly` when `pf_wants_to_purchase` is set.

---

## Feature 3: Remove Net Wealth Calculator Page

**Rationale:** The page requires fully manual input with no pre-fill from the profile; no values are persisted back. FIRE Scenarios provides sufficient wealth overview.

**Changes:**
- Delete `pages/02_Net_Wealth.py`
- Update home page journey cards: Steps 1 & 3 previously linked to Net Wealth — update to point to Budget & Savings
- Remove `pf_net_worth` from profile defaults and all references
- Remove `nw` from the home page priority detection logic (the `nw is None → Step 1` branch)
