"""Simulation engine — empirical probability analysis of rolling backtest windows."""
from __future__ import annotations

import numpy as np
import pandas as pd


def percentile_cagr(
    cagr_series: pd.Series,
    percentiles: list[int],
) -> dict[int, float]:
    """Return requested percentiles of the CAGR distribution."""
    arr = cagr_series.dropna().to_numpy(dtype=float)
    return {p: float(np.percentile(arr, p)) for p in percentiles}


def probability_beat(cagr_series: pd.Series, threshold: float) -> float:
    """Fraction of historical windows where CAGR strictly exceeded threshold."""
    arr = cagr_series.dropna().to_numpy(dtype=float)
    if len(arr) == 0:
        return 0.0
    return float(np.mean(arr > threshold))


def mdd_frequency(mdd_series: pd.Series, threshold: float) -> float:
    """
    Fraction of windows where MDD was worse (more negative) than threshold.
    threshold should be negative, e.g. -0.30 for a 30% drawdown.
    """
    arr = mdd_series.dropna().to_numpy(dtype=float)
    if len(arr) == 0:
        return 0.0
    return float(np.mean(arr < threshold))


def cagr_by_decade(cagr_df: pd.DataFrame) -> pd.DataFrame:
    """
    Group median CAGR per strategy by the decade of each rolling window end date.
    Returns a long-form DataFrame with columns: Decade, <strategy_cols>...
    """
    if cagr_df.empty or not isinstance(cagr_df.index, pd.DatetimeIndex):
        return pd.DataFrame()
    df = cagr_df.copy()
    df["Decade"] = (df.index.year // 10 * 10).astype(str) + "s"
    return df.groupby("Decade")[cagr_df.columns.tolist()].median().reset_index()
