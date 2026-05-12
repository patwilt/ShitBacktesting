"""
Financial Independence Tracker — Streamlit app.

Loads historical rolling CAGR results from the backtest pipeline and
projects portfolio growth forward using user-defined DCA parameters.
"""
from __future__ import annotations

import glob
import os
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --- Page Configuration ---
st.set_page_config(
    page_title="Investment Strategy Evaluator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling ---
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #30363d;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def parse_date(date_val: object) -> Optional[datetime]:
    """Attempt to parse date from various formats. Returns None on failure."""
    try:
        result = pd.to_datetime(date_val)
        # pd.to_datetime(None) returns NaT rather than raising; treat as None.
        if pd.isna(result):
            return None
        return result
    except (ValueError, TypeError):
        try:
            return datetime(int(date_val), 1, 1)
        except (ValueError, TypeError):
            return None

def detect_frequency(df: pd.DataFrame, date_col: str) -> str:
    """Detect if data is monthly or yearly based on average date spacing."""
    dates = pd.to_datetime(df[date_col])
    if len(dates) < 2:
        return "Yearly"
    avg_diff = dates.diff().dropna().dt.days.mean()
    return "Monthly" if 25 <= avg_diff <= 35 else "Yearly"


def calculate_scenario_fv(
    principal: float,
    monthly_pmt: float,
    annual_growth_rate: float,
    years: int,
    annual_return: float,
) -> tuple[float, float]:
    """
    Closed-form final value for a growing annuity-due.

    Each year the monthly payment grows by annual_growth_rate (%).
    Contributions are made at the *start* of each month (annuity due),
    so each contribution earns one full month of returns in the month
    it is deposited.

    Uses the FV-of-annuity-due formula to eliminate the inner month loop,
    giving an O(years) algorithm instead of O(years * 12).
    """
    total_portfolio = float(principal)
    current_monthly_pmt = float(monthly_pmt)
    total_contributed = float(principal)
    monthly_return = (1.0 + annual_return) ** (1.0 / 12.0) - 1.0

    for _ in range(years):
        if abs(monthly_return) < 1e-10:
            growth_factor_12 = 1.0
            annuity_fv = current_monthly_pmt * 12.0
        else:
            growth_factor_12 = (1.0 + monthly_return) ** 12
            # FV of annuity due: C*(1+r)*((1+r)^12 - 1)/r
            annuity_fv = (
                current_monthly_pmt
                * (1.0 + monthly_return)
                * (growth_factor_12 - 1.0)
                / monthly_return
            )

        total_portfolio = total_portfolio * growth_factor_12 + annuity_fv
        total_contributed += current_monthly_pmt * 12.0
        current_monthly_pmt *= 1.0 + annual_growth_rate / 100.0

    return total_portfolio, total_contributed

def get_strategy_palette(index):
    """Returns a color palette (Principal, DCA, Growth) for a strategy index."""
    palettes = [
        ["#212F3D", "#2E86C1", "#28B463"], # Blue/Green
        ["#4A235A", "#8E44AD", "#BB8FCE"], # Purple/Magenta
        ["#641E16", "#C0392B", "#E67E22"], # Red/Orange
        ["#145A32", "#229954", "#7DCEA0"], # Deep Green
        ["#1B4F72", "#2E86C1", "#AED6F1"], # Ocean Blue
    ]
    return palettes[index % len(palettes)]

def run_yearly_projection(
    df: pd.DataFrame,
    strategy_cols: list[str],
    initial_portfolio: float,
    dca_method: str,
    dca_value: float,
    dca_grows: bool,
    stop_at_coast: bool,
    salary_growth: float,
    initial_salary: float,
    horizon_years: int,
    return_format: str,
    inflation_rate: float,
    adjust_inflation: bool,
) -> pd.DataFrame:
    """
    Projects portfolio value year-by-year using median historical CAGR per strategy.

    The inner 12-month compounding loop is replaced with the closed-form
    FV-of-annuity-due formula, giving O(horizon_years * n_strategies) instead
    of O(horizon_years * n_strategies * 12).
    """
    is_percentage = "Percentage" in return_format

    strategy_returns: dict[str, float] = {}
    for strat in strategy_cols:
        rets = pd.to_numeric(df[strat], errors="coerce").dropna()
        if is_percentage:
            rets = rets / 100.0
        strategy_returns[strat] = float(rets.median())

    projection_data: list[dict] = []
    current_portfolios = {s: float(initial_portfolio) for s in strategy_cols}
    current_contributions = {s: float(initial_portfolio) for s in strategy_cols}
    has_coasted = {s: False for s in strategy_cols}
    current_salary = float(initial_salary)

    if dca_method == "Percentage of Salary":
        current_monthly_dca = (initial_salary * dca_value / 100.0) / 12.0
    else:
        current_monthly_dca = float(dca_value)

    # Year 0 baseline row
    row: dict = {
        "Year": 0,
        "Salary": current_salary,
        "Cost Basis": initial_portfolio,
        "Yearly_DCA": 0,
    }
    for strat in strategy_cols:
        row[f"{strat}_Principal"] = initial_portfolio
        row[f"{strat}_Contributions"] = 0
        row[f"{strat}_Growth"] = 0
        row[f"{strat}_Total"] = initial_portfolio
        row[f"{strat}_Yearly_Profit"] = 0
    projection_data.append(row)

    inf_factor = 1.0 + inflation_rate / 100.0

    for year in range(1, horizon_years + 1):
        year_row: dict = {"Year": year}

        if year > 1:
            current_salary *= 1.0 + salary_growth / 100.0
            if dca_method == "Percentage of Salary":
                current_monthly_dca = (current_salary * dca_value / 100.0) / 12.0
            elif dca_grows:
                current_monthly_dca *= 1.0 + salary_growth / 100.0

        current_inf_denominator = (inf_factor ** year) if adjust_inflation else 1.0
        year_row["Salary"] = current_salary / current_inf_denominator
        year_row["Yearly_DCA"] = (current_monthly_dca * 12.0) / current_inf_denominator

        for strat in strategy_cols:
            ann_ret = strategy_returns[strat]
            monthly_ret = (1.0 + ann_ret) ** (1.0 / 12.0) - 1.0

            active_monthly_dca = (
                0.0 if (stop_at_coast and has_coasted[strat]) else current_monthly_dca
            )
            start_of_year_val = current_portfolios[strat]

            # --- Vectorised 12-month compounding (annuity-due formula) ---
            # Replaces the per-month Python loop; mathematically identical.
            if abs(monthly_ret) < 1e-10:
                growth_factor_12 = 1.0
                annuity_fv = active_monthly_dca * 12.0
            else:
                growth_factor_12 = (1.0 + monthly_ret) ** 12
                annuity_fv = (
                    active_monthly_dca
                    * (1.0 + monthly_ret)
                    * (growth_factor_12 - 1.0)
                    / monthly_ret
                )

            current_portfolios[strat] = (
                current_portfolios[strat] * growth_factor_12 + annuity_fv
            )
            current_contributions[strat] += active_monthly_dca * 12.0
            # --- End vectorised block ---

            nominal_yearly_profit = (
                current_portfolios[strat] - start_of_year_val
            ) - (active_monthly_dca * 12.0)

            if nominal_yearly_profit > (current_monthly_dca * 12.0):
                has_coasted[strat] = True

            real_total = current_portfolios[strat] / current_inf_denominator
            real_invested = current_contributions[strat] / current_inf_denominator
            real_principal = initial_portfolio / current_inf_denominator
            real_profit = nominal_yearly_profit / current_inf_denominator

            year_row[f"{strat}_Total"] = real_total
            year_row[f"{strat}_Principal"] = real_principal
            year_row[f"{strat}_Contributions"] = real_invested - real_principal
            year_row[f"{strat}_Growth"] = real_total - real_invested
            year_row[f"{strat}_Yearly_Profit"] = real_profit
            year_row[f"{strat}_Cost_Basis"] = real_invested

        projection_data.append(year_row)

    return pd.DataFrame(projection_data)

def find_latest_results_csv():
    """Finds the most recently created results CSV in a BT_* directory."""
    files = glob.glob("data/BT_*/rolling_msci_strategies_results.csv")
    if not files:
        files = glob.glob("rolling_msci_strategies_results.csv")
    if not files: return None
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def main():
    st.title("💸 Financial Independence Tracker")
    st.markdown("""
    Identify key milestones and simulate **Coast FI** scenarios.
    1. **Growth > DCA**: Your money is doing more work than you are putting in.
    2. **Growth > Salary**: Your money is working harder than you are.
    """)

    # --- Sidebar: Inputs ---
    with st.sidebar:
        st.header("📂 Data Input")
        latest_csv = find_latest_results_csv()
        uploaded_file = st.file_uploader("Upload Historical Returns CSV", type=["csv"])
        df = None
        if uploaded_file is not None: df = pd.read_csv(uploaded_file)
        elif latest_csv is not None: df = pd.read_csv(latest_csv)

        if df is not None:
            st.success(f"Loaded: {os.path.basename(latest_csv) if latest_csv else 'Uploaded'}")
            
        st.divider()
        st.header("💰 Financial Inputs")
        initial_salary = st.number_input("Current Salary (AUD)", min_value=0, value=100000, step=5000)
        salary_growth = st.number_input("Annual Salary Growth (%)", min_value=0.0, value=4.0, step=0.5)
        initial_portfolio = st.number_input("Starting Portfolio (AUD)", min_value=0, value=10000, step=5000)
        
        st.divider()
        st.header("📥 DCA Contribution")
        dca_method = st.radio("Contribution Method", ["Fixed Monthly Amount", "Percentage of Salary"])
        
        dca_grows = True
        if dca_method == "Fixed Monthly Amount":
            dca_value = st.number_input("Monthly DCA (AUD)", min_value=0, value=1000, step=100)
            dca_grows = st.checkbox("DCA Amount Grows with Salary", value=True)
        else:
            dca_value = st.number_input("Salary Contribution (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            st.caption(f"Initial Monthly DCA: **${(initial_salary * dca_value / 100) / 12:,.0f}**")

        stop_at_coast = st.toggle("Stop DCA after Coast Year hit", value=False, help="If enabled, monthly contributions stop for a strategy once its annual profit exceeds its annual DCA.")

        st.divider()
        st.header("📉 Inflation & Horizon")
        current_age = st.number_input("Current Age", min_value=0, max_value=120, value=30, step=1)
        inflation_rate = st.number_input("Annual Inflation Rate (%)", min_value=0.0, value=2.5, step=0.1)
        adjust_inflation = st.toggle("Adjust for Inflation (Real Dollars)", value=True)
        horizon_years = st.slider("Projection Horizon (Years)", 1, 50, 30)
        return_format = st.radio("CSV Returns are in:", ["Decimal (0.05 = 5%)", "Percentage (5.0 = 5%)"], index=0)

    if df is None:
        st.warning("Please upload a CSV file.")
        return

    # --- Strategy Selection ---
    all_cols = df.columns.tolist()
    date_col = st.selectbox("Date/Window Column", all_cols, index=0)
    potential_strategies = [c for c in all_cols if c != date_col and "MDD" not in c]
    strategy_cols = st.multiselect("Strategies to Analyze", potential_strategies, default=potential_strategies[:min(len(potential_strategies), 3)])
    
    if not strategy_cols:
        st.error("Select at least one strategy.")
        return

    # --- Run Projection ---
    proj_df = run_yearly_projection(
        df, strategy_cols, initial_portfolio, 
        dca_method, dca_value, dca_grows, stop_at_coast,
        salary_growth, initial_salary, 
        horizon_years, return_format, inflation_rate, adjust_inflation
    )

    # --- CROSSOVER ANALYSIS ---
    st.header("🚀 The Double Crossover")
    
    # Track milestones for summary
    milestones = []

    fig_fi = go.Figure()
    
    # 1. Salary Line
    fig_fi.add_trace(go.Scatter(
        x=proj_df["Year"], y=proj_df["Salary"],
        name="Annual Salary",
        line=dict(color='#FFD700', width=4),
        hovertemplate="Salary: %{y:$,.0f}<extra></extra>"
    ))

    # 2. DCA Line
    fig_fi.add_trace(go.Scatter(
        x=proj_df["Year"], y=proj_df["Yearly_DCA"],
        name="Potential Annual DCA",
        line=dict(color='#AED6F1', width=3, dash='dot'),
        hovertemplate="Annual DCA: %{y:$,.0f}<extra></extra>"
    ))

    # 3. Strategy Growth Lines
    for i, strat in enumerate(strategy_cols):
        palette = get_strategy_palette(i)
        growth_series = proj_df[f"{strat}_Yearly_Profit"]
        
        fig_fi.add_trace(go.Scatter(
            x=proj_df["Year"], y=growth_series,
            name=f"{strat} Annual Profit",
            line=dict(color=palette[2], width=3),
            hovertemplate=f"{strat} Profit: %{{y:$,.0f}}<extra></extra>"
        ))
        
        # Detect crossovers — vectorised with numpy (avoids O(n) Python loop)
        profit_arr = growth_series.to_numpy()
        salary_arr = proj_df["Salary"].to_numpy()
        dca_arr = proj_df["Yearly_DCA"].to_numpy()

        above_salary_idx = np.where(profit_arr[1:] > salary_arr[1:])[0]
        above_dca_idx = np.where(profit_arr[1:] > dca_arr[1:])[0]

        salary_crossover = int(above_salary_idx[0]) + 1 if len(above_salary_idx) > 0 else None
        dca_crossover = int(above_dca_idx[0]) + 1 if len(above_dca_idx) > 0 else None
        
        if dca_crossover:
            fig_fi.add_annotation(
                x=dca_crossover, y=proj_df["Yearly_DCA"][dca_crossover],
                text=f"Coast Year: {dca_crossover}",
                showarrow=True, arrowhead=2, ax=-40, ay=-40,
                bgcolor="#2E86C1", font=dict(color="white")
            )
            
        if salary_crossover:
            fig_fi.add_annotation(
                x=salary_crossover, y=proj_df["Salary"][salary_crossover],
                text=f"FI Year: {salary_crossover}",
                showarrow=True, arrowhead=1, ax=40, ay=-40,
                bgcolor=palette[2], font=dict(color="white")
            )
            milestones.append({"Strategy": strat, "Year": salary_crossover, "Age": current_age + salary_crossover})

    fig_fi.update_layout(
        template="plotly_dark",
        xaxis_title="Years",
        yaxis_title="Annual Amount (AUD)",
        hovermode="x unified",
        height=650,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_fi, width='stretch')

    # --- FI SUMMARY ---
    if milestones:
        st.divider()
        st.subheader("🏁 Financial Independence Milestones")
        
        # Sort by year to find the earliest
        milestones.sort(key=lambda x: x["Year"])
        best = milestones[0]
        
        cols = st.columns(len(milestones))
        for i, m in enumerate(milestones):
            with cols[i]:
                st.metric(f"FI Age ({m['Strategy']})", f"Age {m['Age']}")
                st.caption(f"Reached in Year {m['Year']}")
        
        st.success(f"🎉 **Earliest FI Prediction:** With the **{best['Strategy']}** strategy, you could reach financial independence at **age {best['Age']}**.")

    # --- TRADITIONAL BREAKDOWN ---
    with st.expander("📊 View Portfolio Composition Breakdown"):
        st.subheader("Cumulative Portfolio Value")
        fig_comp = go.Figure()
        for i, strat in enumerate(strategy_cols):
            palette = get_strategy_palette(i)
            fig_comp.add_trace(go.Bar(x=proj_df["Year"], y=proj_df[f"{strat}_Principal"], name=f"{strat} (Principal)", marker_color=palette[0], offsetgroup=i, legendgroup=strat))
            fig_comp.add_trace(go.Bar(x=proj_df["Year"], y=proj_df[f"{strat}_Contributions"], name=f"{strat} (DCA)", marker_color=palette[1], offsetgroup=i, base=proj_df[f"{strat}_Principal"], legendgroup=strat))
            fig_comp.add_trace(go.Bar(x=proj_df["Year"], y=proj_df[f"{strat}_Growth"], name=f"{strat} (Returns)", marker_color=palette[2], offsetgroup=i, base=proj_df[f"{strat}_Principal"] + proj_df[f"{strat}_Contributions"], legendgroup=strat))
        
        fig_comp.update_layout(template="plotly_dark", barmode='group', xaxis_title="Years", yaxis_title="Portfolio Value (AUD)", height=600)
        st.plotly_chart(fig_comp, width='stretch')

if __name__ == "__main__":
    main()
