"""Page 3: Historical Outcomes — empirical probability analysis of rolling windows."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv
from engines.simulation_engine import percentile_cagr, probability_beat, mdd_frequency, cagr_by_decade

st.set_page_config(page_title="Historical Outcomes", page_icon="📜", layout="wide")
st.title("📜 Historical Outcomes")
st.caption("Empirical distribution of rolling 20-year window returns — no synthetic randomness.")

result = load_latest_backtest_csv()
if result is None:
    st.warning("No backtest CSV found.")
    st.stop()
data, csv_path = result
st.caption(f"Using: `{csv_path}`")

selected = st.multiselect("Strategies", data.strategies, default=data.strategies[:min(3, len(data.strategies))])
if not selected:
    st.stop()

st.subheader("CAGR Percentile Distribution")
percentiles = [10, 25, 50, 75, 90]
rows = []
for strat in selected:
    pcts = percentile_cagr(data.cagr_df[strat], percentiles)
    rows.append({"Strategy": strat, **{f"P{p}": f"{pcts[p]*100:.1f}%" for p in percentiles}})
st.dataframe(pd.DataFrame(rows).set_index("Strategy"), width='stretch')

st.subheader("CAGR Distribution")
fig_hist = go.Figure()
for i, strat in enumerate(selected):
    color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
    fig_hist.add_trace(go.Histogram(
        x=data.cagr_df[strat] * 100,
        name=strat, opacity=0.75,
        marker_color=color,
        hovertemplate="%{x:.1f}% CAGR<br>Count: %{y}<extra>" + strat + "</extra>",
    ))
fig_hist.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                       barmode="overlay", xaxis_title="CAGR (%)", yaxis_title="# of windows",
                       height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_hist, width='stretch')

st.subheader("Probability of Beating a Return Threshold")
threshold = st.slider("Target CAGR (%)", 0.0, 20.0, 7.0, 0.5) / 100.0
beat_cols = st.columns(len(selected))
for i, strat in enumerate(selected):
    prob = probability_beat(data.cagr_df[strat], threshold)
    beat_cols[i].metric(strat, f"{prob*100:.0f}%",
                        help=f"% of 20-yr windows where {strat} beat {threshold*100:.1f}% CAGR")

st.divider()
st.subheader("Drawdown Frequency")
mdd_threshold = st.slider("Drawdown Threshold (%)", -80, -5, -30, 5) / 100.0
mdd_cols = st.columns(len(selected))
for i, strat in enumerate(selected):
    if strat in data.mdd_df.columns:
        freq = mdd_frequency(data.mdd_df[strat], mdd_threshold)
        mdd_cols[i].metric(strat, f"{freq*100:.0f}%",
                           help=f"% of windows with drawdown worse than {mdd_threshold*100:.0f}%")

st.divider()
st.subheader("Median CAGR by Start Decade")
decade_df = cagr_by_decade(data.cagr_df[selected])
if not decade_df.empty:
    fig_heat = px.bar(decade_df.melt(id_vars="Decade", var_name="Strategy", value_name="Median CAGR"),
                      x="Decade", y="Median CAGR", color="Strategy", barmode="group",
                      color_discrete_sequence=STRATEGY_COLORS,
                      template="plotly_dark")
    fig_heat.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                           yaxis_tickformat=".1%", height=400)
    st.plotly_chart(fig_heat, width='stretch')
