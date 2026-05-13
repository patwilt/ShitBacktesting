"""Page 7: Assumptions — all model parameters documented for transparency."""
from __future__ import annotations
import streamlit as st
import pandas as pd

from utils.csv_loader import load_latest_backtest_csv

st.set_page_config(page_title="Assumptions", page_icon="📋", layout="wide")
st.title("📋 Assumptions & Methodology")

st.markdown("""
This page documents every assumption baked into the models. Transparency is a core principle — 
you should know exactly what this tool assumes before trusting its projections.
""")

result = load_latest_backtest_csv()

st.header("📊 Data Source")
if result:
    _, csv_path = result
    data, _ = result
    st.success(f"✅ Backtest CSV loaded: `{csv_path}`")
    st.metric("Strategies loaded", len(data.strategies))
    st.metric("Rolling window entries", len(data.cagr_df))
    st.write("**Strategies:**", ", ".join(data.strategies))
else:
    st.warning("No backtest CSV found. Run `rolling_backtest_suite.py` to generate data.")

st.divider()
st.header("📈 Return Projections")
st.markdown("""
- **Source:** Empirical rolling 20-year CAGR windows from `rolling_backtest_suite.py`
- **Method:** Median historical CAGR used for base-case projections. Not a Monte Carlo simulation.
- **Inflation adjustment:** Real (CPI-deflated) values shown throughout. Default CPI assumption: **2.5% pa**
- **DCA:** Dollar-cost averaging contributions modelled as end-of-month annuity payments
- **Returns:** Nominal gross returns; no taxes or fees deducted unless specified on the Tax page
""")

st.divider()
st.header("🔥 FIRE Numbers")
st.markdown("""
| Metric | Formula |
|--------|---------|
| FIRE Number | Annual Spending ÷ SWR |
| Coast FIRE | FIRE Number ÷ (1 + r)^years |
| Lean FIRE | Same formula, frugal spending |
| Fat FIRE | Same formula, high spending |
| Barista FIRE | (Spending − Part-Time Income) ÷ SWR |

Default Safe Withdrawal Rate: **4%** (Bengen 1994; updated Trinity Study)
""")

st.divider()
st.header("🦘 Australian Tax")
st.markdown("""
- **Income tax:** 2024-25 post-Stage-3 brackets: $0-$18,200 = 0%, $18,200-$45,000 = 16%, 
  $45,000-$135,000 = 30%, $135,000-$190,000 = 37%, $190,000+ = 45%
- **Medicare Levy:** 2% of taxable income (reduced below low-income threshold)
- **HECS-HELP:** 2024-25 repayment schedule (income-contingent, 1%–10%)
- **Super concessional contributions:** 15% flat contribution tax
- **CGT (current law):** 50% discount for assets held > 12 months; taxed at marginal rate
- **CGT (proposed July 2027):** Indexation method (real gain taxed at marginal rate); 30% minimum tax floor on nominal gain; main residence still exempt; new builds use lower of current/proposed
""")

st.divider()
st.header("⚠️ Limitations & Disclaimers")
st.markdown("""
1. **Past performance ≠ future results.** The backtest data reflects historical returns only.
2. **Sequence of returns risk** is not explicitly modelled. Actual outcomes depend on the order returns occur.
3. **Tax estimates** are simplified. They do not account for: offsets (LITO, LMITO), franking credits, trust distributions, negative gearing, or state taxes.
4. **No fees** are deducted from returns unless you adjust manually.
5. **Inflation** is modelled as a constant annual rate — real CPI is variable.
6. **This tool is for educational purposes only.** It does not constitute financial advice.  
   Consult a licensed financial adviser (AFS licence holder) before making investment decisions.
""")

st.divider()
st.header("🔬 Rolling Backtest Methodology")
st.markdown("""
- **Window length:** 20 years (configurable in `rolling_backtest_suite.py`)
- **CAGR:** Compound Annual Growth Rate from start to end of each window
- **MDD:** Maximum Drawdown (largest peak-to-trough decline) within each window
- **Rebalancing:** Annual rebalancing assumed for multi-asset strategies
- **Assets:** S&P 500 (SPY/IVV proxy), 3× leveraged S&P 500 (UPRO proxy), Gold
""")

st.divider()
st.header("🛠️ Tech Stack")
st.markdown("""
| Component | Technology |
|-----------|------------|
| Web framework | Streamlit |
| Charts | Plotly |
| Numerics | Pandas + NumPy |
| Tests | pytest |
| Language | Python 3.14 |
""")
