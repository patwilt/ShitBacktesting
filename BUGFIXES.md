# Bug Fixes — FIRE Dashboard (May 2026)

This document summarises the bugs found and fixed across `pages/04_Home_Deposit.py` and `pages/06_FIRE_Scenarios.py` (previously `05_FIRE_Scenarios.py` before the Kids page was reordered ahead of it) during an audit of the cashflow and projection system.

---

## Bug 1 — Home Deposit page unaware of budget data

**File:** `pages/04_Home_Deposit.py`  
**Symptom:** The "Your Monthly Income Breakdown" chart on the Home Deposit page was not pulling living expenses from the Budget page. It showed raw gross income without subtracting mortgage repayments or living expenses, so the investable surplus bar was grossly inflated.  
**Fix:** Wired `pf_annual_spending` (from the shared profile / Budget page) into the chart calculation, and ensured the chart correctly showed `Net Income − Mortgage − Living Expenses = Investable Surplus`.

---

## Bug 2 — DCA not accounting for mortgage repayments or living expenses

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** After selecting "Yes, I plan to buy a house", the default monthly DCA amount on the FIRE Scenarios page did not account for the mortgage repayment or living expenses. The DCA was therefore set far too high — projecting the user investing money they do not have.  
**Fix:** The Home Deposit page now exports `pf_monthly_investable_surplus = net_income − mortgage − living_expenses` to the shared profile. The FIRE Scenarios page uses this as the default DCA, ensuring it reflects what is genuinely available to invest post-purchase.

---

## Bug 3 — DCA not accounting for deposit savings (pre-purchase drag)

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** During the pre-purchase saving phase the model was still DCA-ing the full post-purchase investable surplus. Funds being set aside for the house deposit were not being deducted, so the model was double-counting that money.  
**Fix:** A deposit savings override was added to the projection engine for all pre-purchase years. Each year the required monthly deposit savings (`pf_deposit_monthly_savings`) is subtracted from the DCA via the `annual_cost_overrides` mechanism. A corresponding pre-purchase boost (equal to the mortgage repayment amount) was also added, because the mortgage is not yet active and that cash is genuinely free to deploy.

---

## Bug 4 — Investable surplus export used projected future income, causing inflated starting DCA

**File:** `pages/04_Home_Deposit.py`  
**Symptom:** The exported `pf_monthly_investable_surplus` was calculated using projected future net income (salary grown forward), not today's income. The FIRE Scenarios engine then applied salary growth *on top* of this already-grown value, double-counting growth and starting the DCA unrealistically high.  
**Fix:** Changed the export to use today's net income as the baseline (`net_monthly` not `proj_net_monthly`). Salary growth is applied once, by the projection engine.

---

## Bug 5 — Audit chart bars exceeding gross salary (tax engine missing)

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** The Annual Cashflow Audit chart showed stacked bars (Tax + Living + DCA etc.) that exceeded the gross salary reference line. Tax was being approximated using a fixed effective-rate fraction calculated at today's income, not recalculated for each year's real salary.  
**Fix:** Per-year tax calculation was implemented. Inside the projection loop, `effective_tax_rate()` is called each year using that year's real salary (proportionally split across partners). This correctly accounts for progressive tax brackets, Medicare levy, LITO, and HECS as income grows over the horizon.

---

## Bug 6 — Kids costs shown as a bar but not separately tracked, masking the gap

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** The audit chart had no explicit "Kids Costs" bar. Because the projection engine subtracts kids costs from the DCA via overrides, the kids spending was hidden inside a reduced DCA bar and the "Gap" bar was confusingly sized.  
**Fix:** Kids costs are now extracted from `_kids_annual_costs` for each year and rendered as an explicit pink bar (`Kids Costs`) in the audit chart. The gap formula subtracts them explicitly, ensuring all outflows are named and visible.

---

## Bug 7 — DCA feasibility check used the wrong ceiling (double-subtracting deposit savings)

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** Even after the DCA clamping was introduced, the audit chart still showed bars exceeding the gross salary line. Bars overflowed by approximately the deposit savings amount each pre-purchase year.  
**Root cause:** The DCA ceiling in the feasibility check was `net − living − deposit − kids`. But the projection engine *also* subtracts deposit savings and kids costs via the override system. This meant:
- The feasibility check reduced the DCA base by deposit savings (first subtraction).
- The engine then subtracted deposit savings again via the deposit-drag override (second subtraction).

The net effect was that deposit savings were double-counted, creating an artificial deficit equal to the deposit savings amount.  
**Fix:** The feasibility ceiling is now `net − living − mortgage` (the post-purchase steady state only). Deposit savings and kids costs are intentionally excluded from the ceiling because the engine handles them via overrides. Additionally, the household net income is now derived by splitting the sidebar salary across partners using the profile income ratio, then passing each slice through the tax engine — ensuring the ceiling matches the salary used in the audit chart.

---

## Bug 8 — Audit chart deflating mortgage and deposit bars, mismatching engine overrides

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** A small but growing gap appeared in the audit chart over time, even when the model was balanced at year 0. The gap grew larger in later years.  
**Root cause:** The audit chart was deflating the mortgage repayment and deposit savings bars by `(1 + inflation)^year`, making them shrink in real-term display over time. However, the projection engine applies its overrides as *constant real values* (inflation-indexed — i.e., it inflates them back to nominal before applying, keeping the real impact constant). The bars and the DCA they accounted for were therefore on different bases, creating a growing discrepancy.  
**Fix:** Mortgage and deposit bars in the audit chart are now shown as constant real values (today's AUD, no deflation), matching exactly how the engine applies its overrides.

---

## Bug 9 — Negative gap bar in top panel rendered below zero axis, not pulling stack down

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** The "Gap / Buffer" bar was added to the top panel stacked chart to visually anchor the bars to the gross salary line. When the gap was negative (deficit), the intent was for the bar to pull the stack downward. Instead, Plotly rendered the negative bar *below the zero axis*, leaving the positive bars at their full height and adding a confusing downward spike below the chart floor.  
**Root cause:** Plotly's `barmode="stack"` does not subtract negative bar values from the cumulative stack. Negative values drop to the opposite side of the zero axis.  
**Fix:** The gap bar was removed from the top panel entirely. The gap is displayed exclusively in the bottom panel, where it reads cleanly as green (surplus) or red (deficit) without visual ambiguity.

---

## Bug 10 — `NameError: name '_has_deposit_drag' is not defined`

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** After the DCA feasibility check block was added, the app threw a `NameError` because the check referenced `_has_deposit_drag` before it was defined. The variable was originally defined much later in the script (inside the DCA Impact Chart section).  
**Fix:** The definition `_has_deposit_drag = _annual_deposit_savings > 0` was moved to immediately after `_annual_deposit_savings` is calculated, ensuring it is always defined before any code that references it.

---

## Bug 11 — `NameError: name '_m_purchase_yr' is not defined` (sidebar caption)

**File:** `pages/06_FIRE_Scenarios.py`  
**Symptom:** The sidebar contained a caption that referenced `_m_purchase_yr` and `_m_monthly_real`. These variables are derived values computed later in the main body of the script, but the sidebar block runs before the main body, so they were undefined at that point.  
**Fix:** The sidebar caption was updated to reference the raw profile values (`_pf_purchase_yrs`, `_pf_mortgage_monthly`) which are loaded at the top of the file and are always defined when the sidebar renders.

---

*All fixes are in `pages/04_Home_Deposit.py` and `pages/06_FIRE_Scenarios.py` (file numeric prefix changed from `05` to `06` when the Kids page was reordered ahead of it). No changes to engine files (`engines/tax_engine.py`, `engines/portfolio_engine.py`) or the shared profile (`utils/shared_profile.py`) were required.*

---

# Round 2 — Audit follow-ups (May 2026)

After verifying the original eleven bugs, the FireAuditor pass surfaced four residual issues which are now fixed below.

---

## Bug 12 — Mortgage modelled as constant real instead of constant nominal

**Files:** `pages/04_Home_Deposit.py`, `pages/06_FIRE_Scenarios.py`
**Symptom:** Real-world mortgage P&I repayments are **fixed in nominal AUD** for the life of the loan — the real burden DECLINES over time as CPI erodes the payment. The model was treating the mortgage as constant in real terms, which over-stated the mortgage drag on the DCA in later years and ultimately delayed projected FIRE dates.

Compounding this, the previous design subtracted the future nominal mortgage from `pf_monthly_investable_surplus` and added it back via "boost" overrides for pre-purchase and post-payoff years. Because the DCA base is grown by salary growth each year, the embedded mortgage was being implicitly inflated by salary growth (not CPI) — the boost over-corrected in later years, compounding the error.

**Fix:**
1. `pages/04_Home_Deposit.py` now exports `pf_monthly_investable_surplus = net_monthly − non_housing` (no mortgage subtraction). It represents today's pre-mortgage investable surplus.
2. `pages/06_FIRE_Scenarios.py` removes the `_mort_payoff_boost` mechanism entirely and introduces `_mort_drag_overrides[yr] = M_annual_nominal / (1 + inflation)^yr` for the mortgage-active years only. Because the portfolio engine re-inflates real overrides back to nominal, this deducts a **constant nominal** mortgage payment each year — declining in real, which is how a fixed-rate AU mortgage actually behaves.
3. DCA feasibility ceiling becomes `net − living` (no mortgage); the engine handles mortgage as an automatic per-year drag on top of whatever DCA the user enters.

---

## Bug 13 — Audit chart and DCA Impact chart disagreed on inflation handling

**File:** `pages/06_FIRE_Scenarios.py`
**Symptom:** After Bug 8 fixed the audit chart's bars to be constant real, the **DCA Impact** chart still deflated mortgage and deposit-savings bars each year. The same two values appeared with different conventions on the same page.

**Fix:** Aligned both charts to the engine's underlying treatment:
- **Mortgage:** declining real in both charts (`/ (1 + inflation)^yr`), matching the new constant-nominal mortgage drag from Bug 12.
- **Deposit savings:** constant real in both charts. `pf_deposit_monthly_savings` is the required flat monthly saving in today's dollars to hit the deposit goal, so its real value is held constant.
- **Kids costs:** constant real (unchanged — `kids_engine` already returns real AUD).

---

## Bug 14 — No disclosure of bracket-creep simplification & living-expense convention

**File:** `pages/06_FIRE_Scenarios.py`
**Symptom:** The audit-chart caption read "Living expenses are held constant in real terms." Users misinterpreted the flat bar as "living expenses do not rise with inflation" — when in fact a flat real bar means **rising with CPI in nominal** (purchasing power preserved). Separately, the per-year tax engine treats brackets as inflation-indexed (a planning convention) but this assumption was undocumented; current Australian brackets are not statutorily indexed, so real bracket creep will make tax slightly higher than shown.

**Fix:** The audit chart caption now leads with a "📏 All values are in today's AUD (real)" explainer and explicitly notes:
- A flat real bar = constant in today's purchasing power = rising with CPI in nominal.
- A declining real bar = constant nominal (e.g. mortgage P&I).
- The Australian tax engine is run per-year against the bracket schedule as if brackets were inflation-indexed; if wages outpace inflation, real tax may be a touch higher than modelled.

---

## Feature 18 — Cumulative Cash Balance chart

**File:** `pages/06_FIRE_Scenarios.py`
**Motivation:** The audit chart's bottom panel shows per-year surplus/deficit gaps, but the user could not easily see *the running cash position* — i.e. how much money would accumulate outside the investment portfolio from banked surpluses, or how deep a cash buffer they'd need to survive deficit years.

**Implementation:** A new `st.expander("💰 Cumulative Cash Balance …")` block sits directly below the audit chart. It integrates `_au_gap` year-by-year into a running balance, compounded at a user-configurable real cash yield (default 0% — a typical HISA roughly tracks CPI; slider range −2% to +5% real for money-market funds, higher-yield accounts, or under-CPI assumptions).

Renders include:
- Four headline metrics: Peak Cash (at age), Lowest Cash (at age), End-of-Horizon Cash, and First Year Cash < $0 ("Never" if the plan stays positive).
- A line+area chart in real AUD with green fill above zero (surplus), red fill below (deficit), zero reference line, and the same event vlines as the audit chart (house purchased, mortgage paid off, children born).
- A contextual caption that either:
  - ⚠️ Warns about the first cash-negative age and quantifies the minimum starting cash buffer needed; *or*
  - ✅ Confirms the cash balance stays positive and suggests redirecting excess HISA cash into the investment portfolio for higher compounded returns.

This complements the negative-gap warning by surfacing **cumulative** plan stress, not just per-year stress — a single bad year is easy to absorb if surrounded by surplus years, but a multi-year deficit cluster after the cash buffer is exhausted is a much bigger problem.

---

## Bug 17 — "Mortgage + Kids Adjusted" FIRE age could come out earlier than unadjusted (counter-intuitive)

**File:** `pages/06_FIRE_Scenarios.py`
**Symptom:** With Fat FIRE settings (e.g. `$143k/yr` target, mortgage `$56k/yr`), the `Fat FIRE (Mortgage + Kids Adjusted)` metric showed **age 51**, while the unadjusted `Fat FIRE (Tax-Adjusted)` showed **age 52** — i.e. adding more obligations apparently made the user retire *earlier*.

**Root cause:** The PV-based adjusted threshold is mathematically correct but optimistic. `_cashflow_mort_threshold(yr, base_target, high_gross)` computes:

```
PV(annuity of high_gross over remaining mortgage years)
+ PV(base_target lump sum at payoff year)
```

When the real return assumption `r` exceeds the effective drawdown rate during the mortgage period (i.e. `high_gross < base_target × r`), this PV formula returns a value *below* `base_target`. The portfolio is assumed to grow faster than it's drawn down during the high-spend phase, so a starting portfolio smaller than the perpetual-SWR target can still grow into `base_target` by mortgage payoff.

The math is valid in a deterministic-return world but ignores sequence-of-returns risk, and produces a misleading UI where "Adjusted" reads as "*earlier than* unadjusted."

**Fix:** Floor `_cashflow_mort_threshold` at `base_target`:

```python
return max(base_target, pv_threshold)
```

Because `_kids_threshold_addition(yr) ≥ 0` always, the combined `_full_adj_threshold` is now guaranteed to be `≥ base_target`. The adjusted FIRE age can therefore never come out earlier than the unadjusted SWR FIRE age. The PV optimization still applies when it makes the threshold *higher* than base_target (i.e. when mortgage genuinely dominates), so Lean and Your FIRE continue to show realistic delay deltas — but the conservatism kicks in for Fat-style scenarios where the PV math would otherwise allow optimistic early-retirement implications.

Documented in both `_cashflow_mort_threshold` and `_full_adj_threshold` docstrings.

---

## Bug 16 — DCA clamp banner didn't reflect kids or deposit-savings drag

**File:** `pages/06_FIRE_Scenarios.py`
**Symptom:** When the DCA was clamped (e.g. `DCA clamped: 10,657/mo → 7,910/mo`), the warning text mentioned only the mortgage drag. With a kids plan enabled (e.g. peak $72,000/yr at age 45), the user had no indication from the banner that the engine would *additionally* deduct kids costs from the post-clamp DCA — making it easy to think the displayed ceiling was the final number. The same blind spot existed for deposit-savings drag pre-purchase.

**Fix:**
1. A single `_engine_drags` list is now built up-front, enumerating every per-year deduction the engine will apply (mortgage, deposit savings, kids), each with $/mo magnitude and active year window. The list is rendered as bullet points inside both the clamp `st.error()` / `st.warning()` banners.
2. A new `_peak_drag_annual` / `_peak_drag_yr` summary is computed by scanning all override years. The clamp banner now includes a "Worst-year combined drag" line that tells the user the peak monthly hit, the age it occurs, and either the residual DCA at that point or a "DCA will floor at $0 that year" callout pointing to the red banner below the audit chart.
3. When the user is **not** clamped but still has engine drags configured, a new banner appears:
   - `st.warning(...)` if the peak drag exceeds the user's starting DCA (the engine will floor contributions at $0 in that year).
   - `st.info(...)` otherwise, just listing the per-year drags so the user knows what's already modelled.
4. The old "Kids plan active" `st.info()` banner is demoted to a `st.caption()` so the per-year cost info isn't duplicated between two boxes.

---

## Bug 15 — Negative-gap years not surfaced as warnings

**File:** `pages/06_FIRE_Scenarios.py`
**Symptom:** When the user's combined obligations (DCA + living + mortgage + deposit + kids) exceeded net income in some years, the bottom panel of the audit chart showed a red notch but the consequence was easy to miss — and the engine silently floors DCA at $0 for those years, so the projected portfolio quietly under-performs the user's input DCA.

**Fix:** A prominent `st.error()` banner is rendered below the audit chart whenever **any** year has a negative gap. It reports:
- Number of deficit years and the age range affected.
- The worst-year deficit magnitude (real AUD).
- Cumulative real-AUD shortfall across all deficit years.
- A short list of recommended actions (reduce DCA, increase salary input, extend loan term, lower deposit %, or revisit kids/budget assumptions).

The banner makes it impossible to plan in deficit without explicit acknowledgement, in line with the FireAuditor principle of preferring conservative modelling and refusing false precision.
