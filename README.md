# Australian Financial Planner — FIRE Dashboard

> A systematic, evidence-based toolkit for building long-term wealth in Australia.  
> Budgeting, superannuation, home deposits, FIRE planning, and portfolio backtesting — all in one place.

---

## What This Tool Is (And What It Isn't)

This dashboard is a **financial modelling and planning toolkit**, not a financial product.

It is built around a single core principle: **cashflow comes before investing**. Every tool in this suite follows a deliberate sequence — understand your income, control your spending, eliminate high-cost liabilities, then direct your surplus toward long-term wealth creation. Skipping steps doesn't accelerate progress; it creates fragile plans that collapse under real-world pressure.

The tax calculations use **2024-25 Australian tax law** (income tax, Medicare levy, Medicare Levy Surcharge, HECS-HELP, and concessional super caps). Where legislation may have changed, this is noted explicitly. **Verify current legislation before implementing any strategy.**

This tool is for educational and modelling purposes only. It does not constitute financial advice. Consult a licensed financial adviser before making investment decisions.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| pip | Any current version |

Install the dependencies:

```bash
pip install -r requirements.txt
```

Core packages used by the dashboard:

| Package | Purpose |
|---|---|
| `streamlit >= 1.41.0` | Web app framework |
| `pandas >= 2.0.0` | Data manipulation and CSV handling |
| `numpy >= 1.24.0` | Numerical calculations |
| `plotly >= 5.18.0` | Interactive charts |

---

## Launching the Dashboard

```bash
streamlit run fire_dashboard.py
```

The app opens in your browser at `http://localhost:8501`.

Navigate between tools using the **sidebar on the left**. The home page (`fire_dashboard.py`) is your central hub — complete the Financial Profile here first. Every calculator page reads from it automatically.

---

## Step 1: Set Your Financial Profile

**This is where you start.** Fill in your profile once on the home page and every calculator pre-fills from it. You can always override values locally on any individual page without affecting your saved profile.

### Your Details

| Field | What to Enter | Why It Matters |
|---|---|---|
| **Current Age** | Your age today | Drives preservation age calculations (~60) and years-to-retirement projections |
| **Retirement Age** | Your target retirement age | Used in super and FIRE projections |
| **Birth Year** | Auto-calculated | Derived from current age — no manual entry required |
| **Private Hospital Cover** | Yes/No | Affects Medicare Levy Surcharge (MLS). Without private hospital cover, incomes above $93,000 incur an additional 1–1.5% levy. Enter this accurately — it changes your real take-home pay |
| **Gross Annual Income** | Total pre-tax salary (AUD) | Used by the tax engine to calculate true after-tax income |
| **HECS-HELP Balance** | Outstanding student loan balance | HECS is compulsory-deducted via payroll and CPI-indexed annually. The tax engine includes your repayment rate automatically |
| **Your Super Balance** | Current superannuation balance | Starting point for all super projections |

### Partner Mode

Toggle **Include a partner** to model household finances as a couple.

Australian income tax is calculated **individually** — each partner has their own tax bracket, HECS rate, MLS status, and super account. The dashboard models this correctly; it does not aggregate incomes into a single tax calculation, which would overstate tax significantly for households where partners are on different marginal rates.

Partner fields mirror the personal fields above. Where relevant (FIRE, super projections), pages allow switching between individual and combined household views.

### Household Wealth & Assumptions

| Field | Default | What It Drives |
|---|---|---|
| **Investment Portfolio** | $0 | Combined shares, ETFs, and cash savings — excludes super and property equity. Used as the starting balance in all FIRE projections |
| **Inflation (%/yr)** | 2.50% | Real purchasing-power erosion. Used to convert nominal projections to today's dollars. The RBA's target band is 2–3%. Using 2.5% is reasonable; consider 3.0% for a conservative scenario |
| **Portfolio Return (%/yr)** | 7.00% | Nominal expected annual return on your investment portfolio. A globally diversified index ETF portfolio has historically returned 9–10% nominal over long periods. Using 7% applies a meaningful margin of safety. Do not assume recent bull-market returns perpetuate |
| **Safe Withdrawal Rate (%)** | 4.00% | The percentage of your portfolio you draw annually in retirement without depleting capital over a 30-year horizon. The 4% Rule originates from the Trinity Study (1998) using US market data. For Australian investors, a 3.5–4% SWR is considered conservative. Higher SWRs work over shorter retirements; lower SWRs provide more resilience against sequence risk |

### Salary Growth

| Field | Guidance |
|---|---|
| **Annual Salary Growth (%/yr)** | 3–4% is typical for Australia. This is a nominal figure — real salary growth (above inflation) averages around 1–1.5%/yr historically. Used by the Home Deposit, Super, and FIRE pages to project future income |
| **Salary Ceiling (optional)** | Cap salary growth at a real-dollar ceiling. Useful if you expect income to plateau at a senior role. Indexed to inflation automatically — a $200k ceiling in today's dollars becomes $205k nominal at 2.5% inflation next year |

Partner salary growth and ceiling fields appear when partner mode is enabled.

### Housing & Liabilities

| Field | Notes |
|---|---|
| **Home Ownership** | Renting, Owner-Occupier, or Property Investor. Affects emergency fund sizing guidance and whether the Home Deposit Planner step is highlighted |
| **Mortgage Balance** | Outstanding principal on your home loan. Used in net wealth context and debt prioritisation guidance |
| **Other High-Interest Debt** | Combined balance of credit cards, personal loans, and car loans (not HECS or mortgage). Any debt above ~10% interest rate should be treated as a priority before investing |
| **Tax Law Scenario** | Choose between **Current (2024-25)** — 50% CGT discount for assets held >12 months — or **Proposed 2027** — indexation method with a 30% minimum tax floor. This affects after-tax income and FIRE projections across all pages |

### Saving Your Profile

Click **Save Profile** to persist your data across all calculator pages. Streamlit resets form widget values on navigation by default; the Save button writes your values to a persistent session store that survives page switching.

Click **Reset to Defaults** to wipe all fields back to their starter values.

---

## Step 2: Follow the Financial Journey

After saving your profile, the home page displays a **7-step financial journey** and a smart priority callout showing which step you should be focused on right now, based on your profile data.

The steps are sequential for a reason. Each one creates the conditions for the next. Working them out of order typically means doing multiple things poorly instead of one thing well.

```
Step 0 → Budget         Understand your cashflow
Step 1 → Emergency Fund Financial resilience before risk-taking
Step 2 → Super Matching Capture guaranteed employer returns
Step 3 → Pay Down Debt  Eliminate guaranteed negative returns
Step 4 → Large Goals    Separate near-term capital requirements
Step 5 → Optimise Super Reduce tax on long-term compounding
Step 6 → Invest & FIRE  Deploy surplus toward financial independence
```

The priority callout reads your saved profile to tell you which step applies right now. It will not recommend salary sacrificing into super if you haven't mapped your cashflow yet. It will flag if your spending exceeds your income. It updates automatically as you work through the pages and save results back to your profile.

---

## Calculator Pages

Navigate to each page from the left sidebar. Pages are numbered to match the step they correspond to in the financial journey.

---

### Page 1 — Budget & Savings Rate

**What it does:** Calculates your true after-tax income using the Australian tax engine (income tax brackets, LITO, Medicare levy, MLS, and HECS repayment), then helps you categorise spending into fixed and discretionary buckets to find your monthly surplus.

**Why this comes first:** Every downstream calculation — FIRE targets, super contribution modelling, home deposit timelines — depends on knowing your monthly investable surplus. If you don't know your real surplus, you are guessing at everything else.

**Key outputs:**
- Real after-tax take-home pay (monthly and annual)
- Monthly surplus after all expenses
- Savings rate as a percentage of net income
- Estimated FIRE horizon based on current savings rate
- How quickly your surplus becomes your primary income source (crossover year)
- ABS benchmark comparisons for each expense category

**Results are pushed back to your profile.** Monthly savings and annual spending figures saved here automatically pre-fill the FIRE Scenarios page — you won't need to re-enter them.

---

### Page 3 — Super Calculator

**What it does:** Projects your superannuation balance from today to your retirement age, accounting for employer SG contributions, salary sacrifice, non-concessional contributions, investment returns, and tax.

**Why super is critical:** Super is Australia's most tax-efficient long-term savings vehicle. Contributions are taxed at 15% — well below the 32.5–47% most Australians pay at the margin. Compounding at a lower tax rate over 20–30 years produces meaningfully different outcomes than investing the same amount in a taxable account. The caveat is access: super is preserved until approximately age 60. Do not over-contribute at the expense of near-term liquidity.

**Key inputs and what they affect:**
- **Employer SG rate** (currently 11.5% for 2024-25): Confirm your employer is paying the correct rate into your chosen fund. This is the single best guaranteed return available to you.
- **Salary sacrifice ($)**: Voluntary pre-tax contributions. Taxed at 15% inside super, reducing your marginal tax bill. Subject to the $30,000 concessional cap (combined employer SG + salary sacrifice).
- **Division 293 awareness**: If your income plus concessional contributions exceeds $250,000, an additional 15% tax applies to concessional contributions (total 30%). The calculator models this automatically.
- **Non-concessional contributions**: After-tax money added to super. Capped at $110,000/yr (or up to $330,000 via the bring-forward rule). Useful for high savers who have exhausted the concessional cap.

**When partnered:** Switch between individual and combined household super projections. Australian super accounts are individual — model each partner separately for accurate outcomes.

---

### Page 4 — Home Deposit Planner

**What it does:** Calculates a monthly savings target and timeline to reach a chosen home deposit, accounting for property price growth, stamp duty, LMI, and First Home Buyer concessions where applicable.

**Why a separate tool for this:** Mixing a home deposit target with your investment portfolio typically results in doing both poorly. Your deposit sits in cash or a HISA — not in the market — because it has a finite, near-term call on it. If your timeline is under 5 years, market risk is inappropriate for this capital. Separating it forces clarity on trade-offs: every dollar directed at a deposit is a dollar not compounding in the market.

**Key inputs:**
- Target property value
- Current deposit savings
- Target deposit percentage (typically 20% to avoid LMI)
- Expected property price growth
- Savings account interest rate

**Results are pushed back to your profile.** If you opt for a property purchase, the estimated monthly mortgage repayment flows into the FIRE Scenarios page so it can model your investable surplus post-purchase correctly.

---

### Page 5 — FIRE Scenarios

**What it does:** Models different paths to financial independence. Compares Coast FIRE, Lean FIRE, Barista FIRE, and Fat FIRE targets side by side. Projects portfolio growth under your current DCA rate and shows the year your portfolio can sustain your lifestyle without employment income.

**FIRE target types explained:**

| Type | Description | Suitable If |
|---|---|---|
| **Lean FIRE** | Minimal spending; typically ~$40–50k/yr Australia | You value freedom above lifestyle |
| **FIRE (Standard)** | Covers your current spending level | Your current lifestyle is your target retirement lifestyle |
| **Barista FIRE** | Partial financial independence; you supplement with part-time work | You want to step back but not fully retire |
| **Fat FIRE** | Generous spending; typically $120k+/yr | You want to maintain or increase your current lifestyle |
| **Coast FIRE** | The portfolio you need *now* so compounding alone reaches your FIRE number without further contributions | You've built enough to "coast"; useful for career change decisions |

**Key inputs:**
- Monthly DCA (regular investment contributions)
- Annual spending in retirement
- Target portfolio return and SWR (pre-filled from your profile)
- Salary growth rate

**Backtest data integration:** If you have loaded rolling historical backtest data (see below), this page overlays real historical strategy performance onto your projections. This shows the range of FIRE timelines that would have occurred under actual market conditions — not just a single assumed return.

---

### Page 7 — Historical Outcomes

**What it does:** Uses rolling historical backtest data to show the distribution of real-world retirement outcomes. Rather than projecting a single assumed return, it answers: *"Across every 20-year period in market history, what percentage of starting portfolios were still solvent after X years of withdrawals?"*

**Why this is more useful than a single-return projection:** A 7% assumed return produces one deterministic answer. Reality is a range. A retiree in 1965 faced a very different sequence of returns than one in 1985, even if the 20-year average return was similar. Historical outcome analysis forces honest engagement with that uncertainty.

**Requires backtest data.** See the *Backtest Data* section below.

---

### Page 8 — Portfolio Analytics

**What it does:** Deep-dive analysis of historical strategy performance from your backtest data. Covers CAGR distributions, maximum drawdowns, Sharpe proxy, underwater periods, and month-by-month alpha maps.

**Key charts:**
- Rolling CAGR over time for each strategy
- Performance distributions (violin + box plots)
- Underwater drawdown chart (crimson fill)
- Pain period summary: longest stretches in worst-quartile drawdown
- CDF of max drawdown (shows probability of experiencing a given loss)
- Monthly alpha heatmap (median CAGR by year × calendar month)

**Requires backtest data.** See the *Backtest Data* section below.

---

### Page 9 — Kids

**What it does:** Models the financial impact of children on your cashflow, savings rate, and FIRE timeline. Incorporates childcare costs (ECEC), schooling (public/private), and indexed cost trajectories.

**Why this is worth modelling:** Children are one of the largest and least-anticipated cashflow disruptions for younger Australians. Childcare alone can cost $2,000–$4,000/month per child depending on location and the Childcare Subsidy rate applicable to your income. Modelling it explicitly — rather than assuming it "sorts itself out" — is the difference between a realistic plan and a wishful one.

---

## Backtest Data

Several pages — FIRE Scenarios, Historical Outcomes, and Portfolio Analytics — can display results enriched with rolling historical backtest data. This data is generated separately and loaded into the dashboard.

### Option A: Use the Bundled Sample Data

A sample CSV is included with the project. If no other data source is detected, the dashboard uses this automatically. It provides a baseline set of strategy results for demonstration purposes.

### Option B: Generate Your Own Backtest Data

Run the full backtest pipeline to produce data calibrated to your chosen strategies and time windows:

**Step 1 — Download market data:**

```bash
python data_downloader.py
```

Fetches S&P 500 (`^GSPC`), Gold (`GC=F`), and MSCI World (`IWDA.L`) from Yahoo Finance. Saves to `data/market_data/`. A VPN may improve Yahoo Finance reliability.

**Step 2 — Configure the backtest** (optional):

Open `rolling_backtest_suite.py` and adjust the variables at the top of the file. No digging into functions required.

| Variable | Default | Description |
|---|---|---|
| `ROLLING_WINDOW_YEARS` | `20` | Length of each rolling window in years |
| `START_DATE` | `1960-01-01` | Earliest window start date |
| `REBALANCE_DAYS` | `63` | Rebalance frequency in trading days (~quarterly) |

Strategy weights (column names update automatically):

```python
S1_WEIGHTS = {"spy": 0.70, "upro": 0.15, "gold": 0.15}
# → "Hybrid SPY (70/15/15)"

S3_WEIGHTS = {"msci": 0.70, "upro": 0.15, "gold": 0.15}
# → "Hybrid MSCI (70/15/15)"
```

**Step 3 — Run the backtest:**

```bash
python rolling_backtest_suite.py
```

Output is written to:

```
data/BT_<window>y_<start>_to_<end>_<timestamp>/rolling_msci_strategies_results.csv
```

The dashboard detects the most recent CSV in `data/BT_*/` automatically. No manual file selection is needed.

### Option C: Upload a CSV Manually

On the home page, expand the **FIRE & Portfolio Backtest Data** section. Upload a `rolling_msci_strategies_results.csv` file directly. Uploaded data takes priority over any file on disk for that session.

The CSV must contain columns in the format `Strategy Name CAGR` and `Strategy Name MDD`. Any strategies matching this pattern are loaded automatically.

---

## Assumptions & Known Limitations

The dashboard uses 2024-25 Australian tax law throughout. The following specific legislative figures are applied:

| Parameter | Value | Notes |
|---|---|---|
| Superannuation Guarantee rate | 11.5% | Scheduled to reach 12% in 2025-26 |
| Concessional contribution cap | $30,000/yr | Employer SG + salary sacrifice combined |
| Non-concessional contribution cap | $110,000/yr | Bring-forward rule allows up to $330k over 3 years |
| Division 293 threshold | $250,000 | Income + concessional contributions above this threshold incur additional 15% super tax |
| Preservation age | ~60 | Applies to those born after 30 June 1964 |
| Medicare Levy Surcharge threshold | $93,000 (singles) | Surcharge avoided with qualifying private hospital cover |

**Always verify current legislation before implementing any contribution or tax strategy. Laws change.**

**Model limitations specific to the backtest engine:**

- Pre-1974 gold data uses a constant-return proxy. Backtest windows starting before 1974 should be treated as directional only.
- MSCI World pre-2009 is synthetic, built from S&P 500 with alpha adjustments. The 2020s show ~1.15 pp CAGR gap vs actual IWDA.L due to ~94 UK-only trading days per year that the model cannot capture.
- No transaction costs or taxes on rebalancing are modelled. Real-world implementation will incur some friction.
- UPRO intraday slippage (~5–10 bps/yr) is not modelled. Negligible over long rolling windows.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Covers the tax engine, calculation engine, portfolio engine, simulation engine, CSV loader, and backtest real-world validation (including calibrated accuracy checks against actual ETF data across non-overlapping sub-periods).

---

## Disclaimer

This tool is for educational and modelling purposes only. It does not constitute financial advice. Past performance does not guarantee future results. Tax calculations are based on 2024-25 Australian legislation — verify current law before implementation. Consult a licensed financial adviser before making investment decisions.
