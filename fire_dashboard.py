"""
FIRE Dashboard — entry point.
Run: streamlit run fire_dashboard.py
"""
from __future__ import annotations
import streamlit as st
from utils.csv_loader import find_csv_on_disk, load_from_uploaded_file, load_latest_backtest_csv

st.set_page_config(
    page_title="FIRE Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔥 FIRE Dashboard")
st.markdown(
    "Australian Financial Independence, Retire Early planning tool.  \n"
    "Load your backtest data and explore your path to FIRE."
)

# ── Data source detection ──────────────────────────────────────────────────────
has_disk_data    = find_csv_on_disk() is not None
has_session_data = "backtest_data" in st.session_state

if has_disk_data or has_session_data:
    # Show which data source is active
    result = load_latest_backtest_csv()
    if result:
        data, source = result
        if has_session_data and not has_disk_data:
            st.success(
                f"✅ **Uploaded data active** — `{source}` "
                f"({len(data.strategies)} strategies: {', '.join(data.strategies)})"
            )
        else:
            is_sample = "sample" in source.replace("\\", "/")
            label = "📦 **Bundled sample data**" if is_sample else "📊 **Local backtest data**"
            st.info(
                f"{label} — `{source.split('/')[-1]}` "
                f"({len(data.strategies)} strategies: {', '.join(data.strategies)})"
            )
        if has_session_data:
            if st.button("🗑️ Clear uploaded data (revert to disk/sample)", type="secondary"):
                del st.session_state["backtest_data"]
                st.session_state.pop("backtest_path", None)
                st.rerun()
else:
    # No CSV found anywhere — prompt upload
    st.error(
        "⚠️ **No backtest data found.** "
        "Generate data by running `rolling_backtest_suite.py`, or upload a CSV below."
    )

# ── CSV uploader ───────────────────────────────────────────────────────────────
with st.expander(
    "📂 Upload a backtest CSV" if (has_disk_data or has_session_data)
    else "📂 Upload a backtest CSV (required)",
    expanded=not (has_disk_data or has_session_data),
):
    st.markdown(
        "Upload a `rolling_msci_strategies_results.csv` exported by `rolling_backtest_suite.py`.  \n"
        "Uploaded data takes priority over any file on disk for this browser session."
    )
    uploaded = st.file_uploader(
        "Choose CSV file",
        type="csv",
        help="Must contain columns like 'Strategy Name CAGR' and 'Strategy Name MDD'.",
    )
    if uploaded is not None:
        try:
            new_data, new_path = load_from_uploaded_file(uploaded)
            if not new_data.strategies:
                st.error("❌ No strategy columns found. Make sure the file has '... CAGR' and '... MDD' columns.")
            else:
                st.session_state["backtest_data"] = new_data
                st.session_state["backtest_path"] = uploaded.name
                st.success(
                    f"✅ Loaded **{uploaded.name}** — "
                    f"{len(new_data.strategies)} strategies: {', '.join(new_data.strategies)}"
                )
                st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to parse CSV: {e}")

st.divider()
st.info("👈 Use the sidebar to navigate between pages.")

st.warning(
    "⚠️ **Disclaimer:** This tool is for educational and modelling purposes only.  \n"
    "It does not constitute financial advice. Past performance does not guarantee future results.  \n"
    "Consult a licensed financial adviser before making investment decisions."
)
