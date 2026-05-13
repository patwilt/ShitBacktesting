"""Auto-discovers and loads the most recently modified backtest CSV."""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field

import pandas as pd


# Maps primary-asset labels in strategy names to canonical ticker strings.
_LABEL_TO_TICKER: dict[str, str] = {
    "SPY": "SPY",
    "S&P": "SPY",
    "MSCI": "MSCI",
    "IVV": "IVV",
    "QQQ": "QQQ",
}
# Secondary assets assumed in hybrid strategies (order matches percentage string).
_HYBRID_SECONDARY = ["UPRO", "Gold"]


def parse_strategy_allocation(name: str) -> dict[str, float]:
    """
    Derive asset allocation from a strategy name.

    Supported patterns:
      "Hybrid SPY (70/15/15)"   → {SPY: 0.70, UPRO: 0.15, Gold: 0.15}
      "Hybrid MSCI (40/35/25)"  → {MSCI: 0.40, UPRO: 0.35, Gold: 0.25}
      "Dull S&P 500"            → {SPY: 1.0}
      "Dull MSCI World"         → {MSCI: 1.0}
    Falls back to {name: 1.0} for unrecognised patterns.
    """
    # Dull (100% single asset)
    if name.lower().startswith("dull"):
        if "msci" in name.lower():
            return {"MSCI": 1.0}
        return {"SPY": 1.0}

    # Hybrid: extract primary label and percentage string "(X/Y/Z)"
    m = re.search(r"Hybrid\s+(\S+)\s+\((\d+(?:/\d+)+)\)", name)
    if m:
        primary_label = m.group(1)
        pcts = [int(p) / 100.0 for p in m.group(2).split("/")]
        total = sum(pcts)
        pcts = [p / total for p in pcts]
        primary_ticker = _LABEL_TO_TICKER.get(primary_label, primary_label)
        assets = [primary_ticker] + _HYBRID_SECONDARY[: len(pcts) - 1]
        return dict(zip(assets, pcts))

    return {name: 1.0}


@dataclass
class BacktestData:
    strategies: list[str]
    cagr_df: pd.DataFrame
    mdd_df: pd.DataFrame
    allocations: dict[str, dict[str, float]] = field(default_factory=dict)


def load_latest_backtest_csv(search_root: str = ".") -> tuple[BacktestData, str] | None:
    """
    Finds the newest rolling_msci_strategies_results.csv in any data/BT_* subfolder.
    Returns (BacktestData, filepath) or None if not found.
    """
    pattern = os.path.join(search_root, "data", "BT_*", "rolling_msci_strategies_results.csv")
    candidates = glob.glob(pattern)
    if not candidates:
        return None

    latest = max(candidates, key=os.path.getmtime)
    # Column 0 is "Window_End" by convention from BacktestExporter.export_dataframe()
    df = pd.read_csv(latest, index_col=0, parse_dates=True)

    cagr_cols = {c: c.replace(" CAGR", "") for c in df.columns if c.endswith(" CAGR")}
    mdd_cols  = {c: c.replace(" MDD", "")  for c in df.columns if c.endswith(" MDD")}
    strategies = list(cagr_cols.values())

    cagr_df = df[[c for c in cagr_cols]].rename(columns=cagr_cols)
    mdd_df  = df[[c for c in mdd_cols]].rename(columns=mdd_cols)
    allocations = {s: parse_strategy_allocation(s) for s in strategies}

    return BacktestData(strategies=strategies, cagr_df=cagr_df, mdd_df=mdd_df, allocations=allocations), latest
