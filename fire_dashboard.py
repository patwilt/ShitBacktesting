"""
FIRE Dashboard — entry point.
Run: streamlit run fire_dashboard.py
"""
from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="FIRE Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔥 FIRE Dashboard")
st.markdown("""
Australian Financial Independence, Retire Early planning tool.  
Load your backtest data and explore your path to FIRE.
""")

st.info("👈 Use the sidebar to navigate between pages.")

st.warning("""
⚠️ **Disclaimer:** This tool is for educational and modelling purposes only.  
It does not constitute financial advice. Past performance does not guarantee future results.  
Consult a licensed financial adviser before making investment decisions.
""")
