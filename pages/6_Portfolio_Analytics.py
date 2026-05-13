"""Page 6: Portfolio Analytics — strategy comparison, rolling returns, risk-return scatter."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv

st.set_page_config(page_title="Portfolio Analytics", page_icon="📈", layout="wide")
st.title("📈 Portfolio Analytics")

result = load_latest_backtest_csv()
if result is None:
    st.warning("No backtest CSV found.")
    st.stop()
data, csv_path = result
st.caption(f"Using: `{csv_path}`")

selected = st.multiselect("Strategies", data.strategies, default=data.strategies)
if not selected:
    st.stop()

st.subheader("Median CAGR vs Max Drawdown")
medians_cagr = {s: float(data.cagr_df[s].median()) for s in selected}
medians_mdd  = {s: float(data.mdd_df[s].median()) for s in selected if s in data.mdd_df.columns}

fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(x=selected, y=[medians_cagr[s]*100 for s in selected],
                          name="Median CAGR (%)", marker_color=COLORS["mint"],
                          hovertemplate="%{x}<br>CAGR: %{y:.1f}%<extra></extra>"))
fig_bar.add_trace(go.Bar(x=selected, y=[abs(medians_mdd.get(s, 0))*100 for s in selected],
                          name="Median MDD (%)", marker_color=COLORS["orange"],
                          hovertemplate="%{x}<br>MDD: %{y:.1f}%<extra></extra>"))
fig_bar.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                      barmode="group", yaxis_title="(%)", height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_bar, use_container_width=True)

st.subheader("Rolling CAGR Over Time")
fig_roll = go.Figure()
for i, strat in enumerate(selected):
    color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
    fig_roll.add_trace(go.Scatter(
        x=data.cagr_df.index, y=data.cagr_df[strat] * 100,
        name=strat, line=dict(color=color, width=1.5),
        hovertemplate=f"{strat}<br>%{{x|%Y-%m-%d}}: %{{y:.1f}}%<extra></extra>",
    ))
fig_roll.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                       xaxis_title="Window End Date", yaxis_title="20-Year CAGR (%)",
                       height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_roll, use_container_width=True)

st.subheader("Risk-Return Scatter (Median CAGR vs Median MDD)")
scatter_data = [{"Strategy": s, "CAGR (%)": medians_cagr[s]*100,
                  "MDD (%)": abs(medians_mdd.get(s, 0))*100} for s in selected]
fig_scatter = px.scatter(scatter_data, x="MDD (%)", y="CAGR (%)", text="Strategy",
                          color="Strategy", color_discrete_sequence=STRATEGY_COLORS,
                          template="plotly_dark")
fig_scatter.update_traces(textposition="top center", marker_size=12)
fig_scatter.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                           xaxis_title="Median Max Drawdown (%)", yaxis_title="Median CAGR (%)",
                           showlegend=False, height=400)
st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()
st.subheader("Asset Allocation")
strats_with_alloc = [s for s in selected if s in data.allocations]
if strats_with_alloc:
    alloc_cols = st.columns(min(len(strats_with_alloc), 4))
    for i, strat in enumerate(strats_with_alloc):
        weights = data.allocations[strat]
        if i < len(alloc_cols):
            fig_pie = go.Figure(go.Pie(
                labels=list(weights.keys()),
                values=list(weights.values()),
                hole=0.4,
                marker_colors=STRATEGY_COLORS[:len(weights)],
                textinfo="label+percent",
            ))
            fig_pie.update_layout(
                template="plotly_dark", paper_bgcolor="#0d1117",
                showlegend=True, height=250,
                title=dict(text=strat[:30], font_size=11),
            )
            alloc_cols[i].plotly_chart(fig_pie, use_container_width=True)
else:
    st.info("Allocation breakdown not available for selected strategies.")
