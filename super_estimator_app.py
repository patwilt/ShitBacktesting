import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import glob

# Set page layout and aesthetics
st.set_page_config(page_title="Superannuation Estimator", layout="wide", page_icon="📈")

def find_latest_csv():
    """Finds the most recently created 'rolling_stats_results.csv' in the current working directory subfolders."""
    files = glob.glob("**/rolling_stats_results.csv", recursive=True)
    if files:
        latest_file = max(files, key=os.path.getctime)
        return latest_file
    return None

def calculate_future_value(principal, pmt, freq_per_year, years, cagr):
    """
    Calculates the future value of an investment with regular contributions.
    Uses vectorization if cagr is a pandas Series.
    Formula: FV = P * (1 + r)^n + PMT * [ ( (1 + r)^n - 1 ) / r ]
    """
    freq = freq_per_year
    n = years * freq
    
    # Calculate per-period rate
    r = (1 + cagr) ** (1 / freq) - 1
    
    # Handle the r == 0 edge case to avoid division by zero
    fv = np.where(
        r == 0, 
        principal + pmt * n, 
        principal * (1 + r)**n + pmt * (((1 + r)**n - 1) / r)
    )
    return fv

def main():
    st.title("💸 Superannuation Growth Estimator")
    st.markdown("Estimate and visualize potential superannuation growth across different historical market conditions using rolling CAGR backtest results.")
    
    # --- Sidebar Inputs ---
    with st.sidebar:
        st.header("📊 Data Management")
        latest_csv = find_latest_csv()
        uploaded_file = st.file_uploader("Upload rolling_stats_results.csv", type=["csv"])
        
        st.markdown("---")
        st.header("⚙️ Investment Parameters")
        principal = st.number_input("Initial Principal Invested ($)", min_value=0.0, value=100000.0, step=1000.0)
        pmt = st.number_input("Regular Contribution Amount ($)", min_value=0.0, value=1000.0, step=100.0)
        frequency = st.selectbox("Contribution Frequency", ["Fortnightly", "Monthly"], index=1)
        years = st.number_input("Investment Horizon (Years)", min_value=1, value=15, step=1)
        generic_cagr_pct = st.number_input("Generic Expected CAGR (%)", min_value=0.0, value=7.0, step=0.1)
        
        st.markdown("---")
        st.header("🧱 Inflation Adjustment")
        use_inflation = st.checkbox("Adjust for Inflation (Today's $)", value=False)
        inflation_rate_pct = st.number_input("Annual Inflation Rate (%)", min_value=0.0, value=3.0, step=0.1)

    # --- Derived Variables ---
    freq_map = {"Fortnightly": 26, "Monthly": 12}
    freq_per_year = freq_map[frequency]
    total_invested = principal + (pmt * freq_per_year * years)
    generic_cagr = generic_cagr_pct / 100.0
    hisa_cagr = 0.05
    
    # Calculate Inflation adjustments
    inflation_factor = 1.0 # Default (no change)
    adj_suffix = ""
    if use_inflation:
        # Today's value = Future Value / (1 + inflation)^years
        inflation_factor = (1 + (inflation_rate_pct / 100.0)) ** years
        adj_suffix = " (Inflation Adj.)"
    
    # --- Data Loading ---
    df = None
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    elif latest_csv is not None:
        st.info(f"💡 Automatically loaded the most recent backtest data: `{latest_csv}`")
        df = pd.read_csv(latest_csv)
    else:
        st.warning("Please run your backtest to generate `rolling_stats_results.csv` or upload a file in the sidebar to proceed.")
        return

    # Deep Historical Data mapping (Rename proxy columns to match app logic)
    rename_map = {
        'SPY_Proxy_CAGR': 'SPY_CAGR',
        'UPRO_Proxy_CAGR': 'UPRO_CAGR'
    }
    df = df.rename(columns=rename_map)

    # Required columns format check
    possible_strategies = ['Strat_50_50_CAGR', 'Strat_15_15_70_CAGR', 'UPRO_CAGR', 'SPY_CAGR']
    available_strats = [col for col in possible_strategies if col in df.columns]
    
    if not available_strats:
        st.error("The loaded CSV does not contain the required CAGR columns (e.g., Strat_50_50_CAGR, UPRO_CAGR).")
        return

    # --- Core Calculations ---
    hisa_fv = (calculate_future_value(principal, pmt, freq_per_year, years, hisa_cagr)) / inflation_factor
    generic_fv = (calculate_future_value(principal, pmt, freq_per_year, years, generic_cagr)) / inflation_factor
    total_invested_adj = total_invested / inflation_factor

    fv_data = {}
    for col in available_strats:
        cagr_series = df[col].dropna()
        fv_series = (calculate_future_value(principal, pmt, freq_per_year, years, cagr_series)) / inflation_factor
        fv_data[col] = fv_series

    # --- UI & Visualizations ---
    st.markdown(f"### 🏆 Projection Benchmarks{adj_suffix}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Invested", f"${total_invested_adj:,.2f}")
    col2.metric("5% HISA Benchmark", f"${float(hisa_fv):,.2f}")
    col3.metric(f"Generic Expected ({generic_cagr_pct}%)", f"${float(generic_fv):,.2f}")
    st.markdown("---")

    # --- Descriptive Name Mapping ---
    strat_names = {
        'Strat_50_50_CAGR': '50% Gold - 50% UPRO',
        'Strat_15_15_70_CAGR': '15% Gold - 15% UPRO - 70% S&P 500',
        'UPRO_CAGR': '100% UPRO',
        'SPY_CAGR': '100% S&P 500'
    }

    # Plotly Histogram
    st.markdown(f"### 📊 Final Portfolio Values Distribution{adj_suffix}")
    
    fig = go.Figure()
    colors = ['#2980B9', '#9B59B6', '#27AE60', '#E67E22']
    
    for i, col in enumerate(available_strats):
        display_name = strat_names.get(col, col.replace('_CAGR', '').replace('_', ' '))
        data = fv_data[col]
        upper_bound = np.percentile(data, 75)
        conservative_data = data[data <= upper_bound]
        
        fig.add_trace(go.Histogram(
            x=conservative_data,
            name=display_name,
            opacity=0.75,
            marker_color=colors[i % len(colors)]
        ))

    # Add benchmark vertical lines
    fig.add_vline(x=total_invested_adj, line_dash="dash", line_color="red", 
                  annotation_text="Principle Invested", annotation_position="top left")
    fig.add_vline(x=float(hisa_fv), line_dash="dash", line_color="blue", 
                  annotation_text="5% HISA", annotation_position="bottom left")
    fig.add_vline(x=float(generic_fv), line_dash="solid", line_color="green", 
                  annotation_text=f"{generic_cagr_pct}% Expected", annotation_position="top right")
    
    fig.update_layout(
        barmode='overlay',
        xaxis_title=f"Projected Final Portfolio Value{adj_suffix} ($)",
        yaxis_title="Frequency",
        legend_title="Strategy",
        font=dict(family="Inter, sans-serif"),
        xaxis=dict(tickformat="$,.0f"),
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary Statistics
    st.markdown(f"### 📈 Projected Growth Percentiles by Strategy{adj_suffix}")
    
    for col in available_strats:
        display_name = strat_names.get(col, col.replace('_CAGR', '').replace('_', ' '))
        st.markdown(f"**{display_name}**")
        p25, p50, p75 = np.percentile(fv_data[col], [25, 50, 75])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("25th Percentile (Conservative)", f"${float(p25):,.2f}")
        m2.metric("50th Percentile (Median)", f"${float(p50):,.2f}")
        m3.metric("75th Percentile (Optimistic)", f"${float(p75):,.2f}")
        st.write("") 

if __name__ == '__main__':
    main()
