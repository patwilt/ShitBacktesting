# FIRE Dashboard — Design Spec
**Date:** 2026-05-13  
**Status:** Approved  

---

## Overview

A multi-page Streamlit web application that ingests rolling CAGR/MDD backtest data produced by `rolling_backtest_suite.py` and provides a fully interactive Australian FIRE (Financial Independence, Retire Early) planning dashboard. All numbers are editable via sliders and inputs. All calculations are inflation-aware. The app is educational/modelling only — not financial advice.

---

## Architecture

### Entry Point
`streamlit run fire_dashboard.py`

### File Structure
```
fire_dashboard.py              ← Streamlit entry point, shared sidebar state
pages/
  1_Dashboard.py
  2_FIRE_Scenarios.py
  3_Historical_Outcomes.py
  4_Australian_Tax.py
  5_Retirement_Drawdown.py
  6_Portfolio_Analytics.py
  7_Assumptions.py
engines/
  calculation_engine.py        ← Pure Python FIRE math
  tax_engine.py                ← Australian tax rules (versioned)
  simulation_engine.py         ← Historical outcomes / percentile analysis
  portfolio_engine.py          ← DCA compounding, SWR, annuity math
utils/
  csv_loader.py                ← Auto-discovers latest BT_* CSV
tests/
  test_calculation_engine.py
  test_tax_engine.py
  test_simulation_engine.py
  test_portfolio_engine.py
  test_csv_loader.py
```

### Key Principles
- All engine modules are pure Python with no Streamlit dependencies — fully unit-testable.
- No tax rates hardcoded in UI components — all tax logic lives in `tax_engine.py`.
- All assumptions are configurable — no magic numbers outside engine defaults.
- Engines are built test-first (TDD): failing test → minimal implementation → refactor.
- Streamlit is launched after each engine passes tests to verify live.

---

## Data Layer

### CSV Ingestion (`utils/csv_loader.py`)
- Auto-discovers most recently modified `data/BT_*/rolling_msci_strategies_results.csv`.
- Falls back to manual file upload via `st.file_uploader`.
- Parses `Window_End` as datetime index.
- Detects strategy columns automatically (anything with `CAGR` suffix = strategy return column; `MDD` suffix = drawdown column).
- Returns a typed `BacktestData` dataclass: `{strategies: list[str], cagr_df: DataFrame, mdd_df: DataFrame}`.

---

## Engine Modules

### `engines/calculation_engine.py`
Responsibilities:
- `fire_target(annual_spending, swr) -> float` — required portfolio for target spending
- `coast_fire_target(target_portfolio, years_to_retire, annual_return) -> float`
- `lean_fire_target(annual_spending, swr) -> float` — 25× lean spending
- `fat_fire_target(annual_spending, swr) -> float` — 25× fat spending
- `barista_fire_target(annual_spending, part_time_income, swr) -> float`
- `net_worth_projection(principal, monthly_dca, annual_return, years, inflation_rate, salary_growth) -> DataFrame` — year-by-year projection with real and nominal columns
- `fire_age(current_age, projection_df, target_portfolio) -> Optional[int]`

Default assumptions: inflation 2.5%, equity return 7%, SWR 4%.

### `engines/portfolio_engine.py`
Responsibilities:
- `project_portfolio(principal, monthly_pmt, annual_growth_rate, years, annual_return) -> tuple[float, float]` — FV using annuity-due formula (reuse logic from `strategy_evaluator.py`)
- `real_value(nominal, inflation_rate, years) -> float` — deflate to real dollars
- `swr_income(portfolio, swr_rate, tax_engine_fn) -> float` — annual withdrawal after tax
- `dca_crossover_year(projection_df, strategy) -> Optional[int]` — first year profit > DCA
- `salary_crossover_year(projection_df, strategy) -> Optional[int]` — first year profit > salary

### `engines/simulation_engine.py`
Operates on the rolling window CAGR/MDD data as an empirical probability distribution.
- `percentile_cagr(cagr_series, percentiles) -> dict[int, float]` — 10th/25th/50th/75th/90th
- `probability_beat(cagr_series, threshold) -> float` — fraction of windows exceeding threshold
- `mdd_frequency(mdd_series, threshold) -> float` — fraction of windows with MDD worse than threshold
- `cagr_by_decade(cagr_df, window_end_index) -> DataFrame` — median CAGR grouped by decade

### `engines/tax_engine.py`
Versioned CGT law: a `CGTLaw` enum (`CURRENT`, `PROPOSED_2027`).

**Current law:**
- Income tax: 2024-25 AUS brackets (0%, 16%, 30%, 37%, 45%)
- Medicare levy: 2% on taxable income above threshold
- Super concessional contributions: taxed at 15% in fund (up to $30k/yr cap)
- HECS-HELP repayment: income-contingent thresholds, 1%–10% of income
- CGT discount: 50% discount on assets held >12 months, taxed at marginal rate

**Proposed law (effective 1 July 2027) — `CGTLaw.PROPOSED_2027`:**
- 50% flat discount replaced with **indexation**: only real gains above CPI are taxed
- **30% minimum tax floor** on net capital gains (prevents near-zero tax on large gains)
- **Transitional split-treatment**: assets acquired before 1 July 2027 split-taxed — pre-cutoff gains use old 50% discount; post-cutoff gains use new indexation rules
- **New build exemption**: investor may elect old 50% discount or new indexation model for new residential properties
- **Main residence exemption**: unchanged, full CGT exemption on principal place of residence

Public functions:
- `income_tax(taxable_income, cgt_law: CGTLaw) -> float`
- `medicare_levy(taxable_income) -> float`
- `hecs_repayment(income, hecs_balance) -> float`
- `super_tax(concessional_contributions) -> float`
- `cgt_liability(gain, held_years, marginal_rate, law, acquisition_date, cpi_at_acquisition, cpi_current, is_new_build, is_main_residence) -> float`
- `effective_tax_rate(gross_income, tax_engine_inputs) -> float`

---

## Pages

### Page 1 — Dashboard
- Sidebar: current age, target retirement age, current portfolio, monthly DCA, salary, inflation rate, expected return, target annual spending in retirement.
- Main: FIRE age estimate (metric card), required portfolio (metric card), projected net worth at retirement (metric card), net worth timeline chart (nominal vs real, Plotly line chart), disclaimer footer.

### Page 2 — FIRE Scenarios
- Strategy selector (multi-select from CSV strategies).
- Double-crossover chart: annual profit vs DCA vs salary over time.
- FIRE variant cards: Coast / Lean / Fat / Barista with required portfolios and estimated ages.
- All sliders live-update charts with no page reload.

### Page 3 — Historical Outcomes
Empirical probability analysis of the rolling window CSV data:
- CAGR histogram per strategy (Plotly).
- Percentile table: 10th/25th/50th/75th/90th CAGR.
- "Beat X% CAGR" slider → shows what % of historical windows achieved it.
- MDD frequency chart: drawdown threshold slider → shows how often that drawdown occurred.
- CAGR heatmap by start decade.

### Page 4 — Australian Tax
- Income inputs: gross salary, super contributions, HECS balance, investment income.
- **CGT Law toggle**: Current (pre-July 2027) / Proposed (post-July 2027).
  - Proposed mode: acquisition date input, CPI at acquisition, new-build checkbox, main residence checkbox.
  - Transitional split-treatment calculation shown clearly.
- Output: tax breakdown table (income tax, Medicare, HECS, super tax, CGT), effective rate, net income.

### Page 5 — Retirement Drawdown
- SWR sensitivity table (2.5%–5.5% in 0.25% steps): annual income, monthly income, portfolio required.
- Inflation erosion chart: real value of a fixed dollar withdrawal over 30 years at configurable inflation rates.
- Super access bridge: preservation age (60 for post-1964 births), years between FIRE date and super access, bridge portfolio required.
- Portfolio survival: using historical MDD data, shows in what fraction of periods a given drawdown would have depleted the portfolio within N years.

### Page 6 — Portfolio Analytics
- Strategy CAGR/MDD comparison (bar chart).
- Rolling CAGR over time (line chart, all strategies).
- CAGR/MDD scatter plot (risk-return).
- Asset allocation breakdown (pie/donut chart using weights from rolling_backtest_suite.py constants).

### Page 7 — Assumptions & Methodology
- All default values editable: inflation, equity return, bond return, SWR, salary growth.
- Description of each calculation formula.
- Links to data sources (Shiller CAPE, FRED, MSCI).
- Disclaimer: educational use only, not financial advice.

---

## Testing Strategy (TDD)

Each engine module follows strict Red → Green → Refactor:

1. Write test file with all tests for a module — **run to confirm they fail**.
2. Write minimal implementation to pass.
3. All tests green before building any page that depends on that engine.
4. Streamlit launched to confirm page renders after each page is complete.

Test coverage targets:
- `calculation_engine`: FIRE targets, projection math, edge cases (0 DCA, 0 return, negative inflation).
- `tax_engine`: Each bracket boundary, Medicare threshold, both CGT law modes, transitional split-treatment.
- `simulation_engine`: Empty series, single-window series, all-same-value degenerate case.
- `portfolio_engine`: Annuity-due compounding against manual calculation, crossover detection.
- `csv_loader`: Missing directory, empty directory, multiple BT_* dirs (picks latest).

---

## UI Style
- Streamlit dark theme (`theme.base = "dark"`).
- Plotly `plotly_dark` template throughout.
- Sidebar for all primary inputs; main area for outputs and charts.
- No financial jargon without tooltip explanation (`help=` on every input).
- All projections labelled nominal vs real clearly.
- Disclaimer on every page footer.

---

## Dependencies
Additions to `requirements.txt`: `streamlit`, `plotly` (already present in project).  
No new dependencies required — all existing packages are sufficient.
