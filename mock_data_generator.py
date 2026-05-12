"""
Generates synthetic monthly historical CAGR data for testing strategy_evaluator.py.

Returns are expressed as decimal fractions (e.g. 0.07 = 7% annual CAGR) to
match the default format expected by the Streamlit app.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate_mock_data(
    filename: str = "mock_historical_returns.csv",
    periods: int = 240,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate and save mock historical CAGR data.

    Parameters
    ----------
    filename : str
        Output CSV path.
    periods : int
        Number of monthly records (default 240 ≈ 20 years).
    seed : int
        NumPy RNG seed for reproducibility (0 disables seeding).

    Returns
    -------
    pd.DataFrame
        Generated DataFrame (also written to `filename`).
    """
    rng = np.random.default_rng(seed if seed != 0 else None)

    # pd.date_range produces exact month-start dates — no timedelta approximation.
    dates = pd.date_range(start="2004-01-01", periods=periods, freq="MS")

    df = pd.DataFrame(
        {
            "Date": dates,
            "Aggressive Growth": rng.normal(0.10, 0.08, periods),   # ~10% CAGR
            "Conservative Bond": rng.normal(0.04, 0.03, periods),   # ~4% CAGR
            "Balanced Global": rng.normal(0.07, 0.05, periods),     # ~7% CAGR
        }
    )

    df.to_csv(filename, index=False)
    print(f"Mock data generated: {filename}")
    return df


if __name__ == "__main__":
    generate_mock_data()
