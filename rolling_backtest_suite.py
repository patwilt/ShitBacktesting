"""
Rolling Backtest Suite
Computes rolling CAGR and Max Drawdown for multi-asset strategies over
sliding windows of calendar history, then exports results via BacktestExporter.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from tqdm import tqdm

from backtest_export import BacktestExporter

# ==========================================
# CONFIGURATION
# ==========================================

# ── Backtest window ───────────────────────────────────────────────────────────
DATA_FOLDER          = "data/market_data"
START_DATE           = "1980-01-01"  # suggest 1980+ if relying on gold data
ROLLING_WINDOW_YEARS = 20
WINDOW_DAYS          = ROLLING_WINDOW_YEARS * 252   # approx trading days in a window
REBALANCE_DAYS       = 63            # quarterly rebalancing (~63 trading days)
DEBUG_MODE           = False

# ── Strategy weights ──────────────────────────────────────────────────────────
# Weights must sum to 1.0.  Column names in the output CSV are derived
# automatically from the weights — just change the numbers and re-run.

_TICKER_LABELS: dict[str, str] = {
    "spy": "SPY", "msci": "MSCI", "upro": "UPRO", "gold": "Gold"
}

def _strategy_name(weights: dict[str, float]) -> str:
    """Derive a column label from a weights dict.
    e.g. {"spy": 0.70, "upro": 0.15, "gold": 0.15} → 'Hybrid SPY (70/15/15)'
    """
    primary = max(weights, key=weights.__getitem__)
    label   = _TICKER_LABELS.get(primary, primary.upper())
    pcts    = "/".join(str(round(v * 100)) for v in weights.values())
    return f"Hybrid {label} ({pcts})"

# S1: Hybrid SPY — S&P 500 core + small leveraged sleeve + gold hedge
S1_WEIGHTS = {"spy": 0.70, "upro": 0.15, "gold": 0.15}
S1_NAME    = _strategy_name(S1_WEIGHTS)

# S3: Hybrid MSCI — same structure, global index instead of S&P 500
S3_WEIGHTS = {"msci": 0.40, "upro": 0.35, "gold": 0.25}   
S3_NAME    = _strategy_name(S3_WEIGHTS)

# ── Asset model parameters ────────────────────────────────────────────────────

# SPY / S&P 500 total-return model
SPY_DIVIDEND_YIELD     = 0.015   # fallback yield for years absent from _SP500_DIV_YIELD_ANNUAL

# UPRO (3× leveraged S&P 500 ETF) cost model
UPRO_LEVERAGE          = 3.0
UPRO_EXPENSE_RATIO     = 0.0091  # 0.91 % annual expense ratio (actual UPRO ER)
UPRO_FINANCING_SPREAD  = 0.003   # ~30 bps overnight repo spread above fed funds
UPRO_DEFAULT_RF        = 0.04    # fallback rate for years absent from _FED_FUNDS_ANNUAL

# MSCI World synthetic-bridge model
MSCI_DIVIDEND_YIELD    = 0.02    # ~2 % annual dividend yield
MSCI_PRE1990_ALPHA     = 0.01    # +1 %/yr: Japan boom outperformance vs S&P pre-1990
MSCI_POST2010_ALPHA    = -0.02   # −2 %/yr: US tech dominance drag vs S&P post-2010

# Gold synthetic-bridge model (pre real-data era)
GOLD_PRE1980_CAGR      = 0.12    # +12 %/yr: USD decoupling / 1970s gold rush
GOLD_1980_TO_REAL_CAGR = -0.025  # −2.5 %/yr: long bear market until real data begins

# ── S&P 500 historical dividend yield lookup ──────────────────────────────────
# Calendar-year average dividend yield for the S&P 500.
# Source: Shiller CAPE data (1927–1999), SPDR/Bloomberg (2000–2026).
# Used by load_and_prep_spy and load_and_prep_upro so both SPY total-return
# construction and UPRO's leveraged total-return use period-appropriate yields
# rather than a single constant — removes a ~0.5–1.0 pp/yr bias in low-yield
# eras (2000–01, 2020–25) and high-yield eras (1970s–80s, 2010–18).
_SP500_DIV_YIELD_ANNUAL: dict[int, float] = {
    1927: 0.049, 1928: 0.042, 1929: 0.040, 1930: 0.054, 1931: 0.067,
    1932: 0.075, 1933: 0.040, 1934: 0.044, 1935: 0.038, 1936: 0.037,
    1937: 0.044, 1938: 0.050, 1939: 0.046, 1940: 0.054, 1941: 0.064,
    1942: 0.072, 1943: 0.059, 1944: 0.054, 1945: 0.043, 1946: 0.041,
    1947: 0.049, 1948: 0.056, 1949: 0.062, 1950: 0.065, 1951: 0.059,
    1952: 0.059, 1953: 0.062, 1954: 0.053, 1955: 0.046, 1956: 0.046,
    1957: 0.050, 1958: 0.044, 1959: 0.033,
    1960: 0.035, 1961: 0.029, 1962: 0.033, 1963: 0.029, 1964: 0.028,
    1965: 0.027, 1966: 0.031, 1967: 0.028, 1968: 0.027, 1969: 0.031,
    1970: 0.035, 1971: 0.031, 1972: 0.027, 1973: 0.033, 1974: 0.046,
    1975: 0.041, 1976: 0.039, 1977: 0.047, 1978: 0.052, 1979: 0.054,
    1980: 0.049, 1981: 0.052, 1982: 0.054, 1983: 0.044, 1984: 0.044,
    1985: 0.040, 1986: 0.034, 1987: 0.035, 1988: 0.038, 1989: 0.033,
    1990: 0.037, 1991: 0.030, 1992: 0.028, 1993: 0.026, 1994: 0.027,
    1995: 0.022, 1996: 0.021, 1997: 0.017, 1998: 0.013, 1999: 0.011,
    2000: 0.011, 2001: 0.013, 2002: 0.017, 2003: 0.016, 2004: 0.015,
    2005: 0.017, 2006: 0.017, 2007: 0.018, 2008: 0.021, 2009: 0.020,
    2010: 0.018, 2011: 0.021, 2012: 0.021, 2013: 0.020, 2014: 0.019,
    2015: 0.021, 2016: 0.021, 2017: 0.019, 2018: 0.020, 2019: 0.018,
    2020: 0.015, 2021: 0.013, 2022: 0.016, 2023: 0.015, 2024: 0.012,
    2025: 0.012, 2026: 0.012,
}

# ── FRED Federal Funds Rate lookup ────────────────────────────────────────────
# Used to scale UPRO financing cost by interest-rate regime rather than
# applying a single flat rate.  Values are calendar-year averages (FRED FEDFUNDS).
_FED_FUNDS_ANNUAL: dict[int, float] = {
    1970: 0.072, 1971: 0.038, 1972: 0.045, 1973: 0.085, 1974: 0.106,
    1975: 0.058, 1976: 0.052, 1977: 0.054, 1978: 0.078, 1979: 0.114,
    1980: 0.135, 1981: 0.160, 1982: 0.122, 1983: 0.091, 1984: 0.102,
    1985: 0.081, 1986: 0.066, 1987: 0.066, 1988: 0.073, 1989: 0.092,
    1990: 0.082, 1991: 0.057, 1992: 0.036, 1993: 0.030, 1994: 0.046,
    1995: 0.059, 1996: 0.053, 1997: 0.053, 1998: 0.055, 1999: 0.050,
    2000: 0.065, 2001: 0.038, 2002: 0.017, 2003: 0.010, 2004: 0.014,
    2005: 0.031, 2006: 0.053, 2007: 0.052, 2008: 0.020, 2009: 0.001,
    2010: 0.001, 2011: 0.001, 2012: 0.001, 2013: 0.001, 2014: 0.001,
    2015: 0.002, 2016: 0.004, 2017: 0.010, 2018: 0.019, 2019: 0.021,
    2020: 0.001, 2021: 0.001, 2022: 0.033, 2023: 0.053, 2024: 0.052,
    2025: 0.045, 2026: 0.043,
}

# ==========================================
# DATA LOADING & SIMULATION
# ==========================================

def load_market_data() -> pd.DataFrame:
    """
    Load and align all market price series.

    Look-ahead bias note: only ffill() is applied here.  bfill() was removed
    because back-filling prices with *future* values contaminates any
    backtest that begins near a data gap.
    """
    tickers = ["gspc", "gold", "msci_real"]
    data_dict: dict[str, pd.Series] = {}

    for t in tickers:
        path = os.path.join(DATA_FOLDER, f"{t}.csv")
        if os.path.exists(path):
            df = pd.read_csv(path, skiprows=[1, 2], index_col=0, parse_dates=True)
            if not df.empty:
                col = "Adj Close" if "Adj Close" in df.columns else "Close"
                if col not in df.columns:
                    col = df.columns[0]
                data_dict[t] = df[col]

    if "gspc" not in data_dict:
        raise RuntimeError("GSPC data missing. Run data_downloader.py first.")

    spy = load_and_prep_spy(data_dict)
    upro = load_and_prep_upro(data_dict)
    gold = load_and_prep_gold_bridge(data_dict)
    msci = load_and_prep_msci(data_dict)

    combined = pd.DataFrame(
        {"spy": spy, "upro": upro, "gold": gold, "msci": msci}
    )
    # Forward-fill only — using bfill here would be look-ahead bias.
    combined = combined.loc[START_DATE:].ffill().dropna()
    return combined


def load_and_prep_spy(data_dict: dict[str, pd.Series]) -> pd.Series:
    s = data_dict["gspc"].dropna()
    rets = s.pct_change().fillna(0.0)
    div_annual = pd.Series(
        [_SP500_DIV_YIELD_ANNUAL.get(y, SPY_DIVIDEND_YIELD) for y in rets.index.year],
        index=rets.index, dtype=np.float64,
    )
    div_daily = (1.0 + div_annual) ** (1.0 / 252)
    s_tr = (1.0 + rets) * div_daily - 1.0
    spy_prices = (1.0 + s_tr).cumprod() * 100
    return np.maximum(spy_prices, 0.01)


def load_and_prep_upro(data_dict: dict[str, pd.Series]) -> pd.Series:
    """
    3× S&P 500 leveraged ETF proxy with **period-appropriate financing cost**.

    Return model (applied daily):
        u_ret = L × tr_ret − daily_cost

    Where:
        tr_ret        = S&P 500 *total* return (price return + dividend yield)
                        Real UPRO targets the total-return index × 3, not the
                        price index.  Using price returns alone understates the
                        leveraged return by roughly L × div_yield ≈ 3 × 1.5 % =
                        4.5 pp/yr.  The daily dividend is added to GSPC price
                        returns in the same way load_and_prep_spy does.
        L             = UPRO_LEVERAGE   (3)
        daily_cost    = [(L-1) × (r_f + spread) + expense_ratio] / 252
        r_f           = annual Fed Funds Rate for the calendar year (FRED)
        spread        = UPRO_FINANCING_SPREAD  (~30 bps above overnight rate)
        expense_ratio = UPRO_EXPENSE_RATIO     (0.91 %)

    Financing cost scales with the interest-rate regime:
      - ZIRP era   (2009–15): annual cost ≈  0.91 + 2×0.30 = ~1.5 %
      - High-rate  (2022–24): annual cost ≈  0.91 + 2×5.30 = ~11.5 %

    Volatility decay is implicitly and *correctly* captured by the daily
    compounding of 3× returns — no additional drag term is required because
    ∏(1+3rᵢ) already diverges from 3×∏(1+rᵢ) by the exact path-dependent amount.
    """
    s = data_dict["gspc"].dropna()
    rets = s.pct_change().fillna(0.0)

    # Convert GSPC price returns → S&P 500 total returns before applying
    # leverage.  This matches how real UPRO computes its daily target return.
    # Period-appropriate dividend yields from _SP500_DIV_YIELD_ANNUAL are used
    # so the leverage does not amplify a constant-yield approximation error.
    div_annual = pd.Series(
        [_SP500_DIV_YIELD_ANNUAL.get(y, SPY_DIVIDEND_YIELD) for y in rets.index.year],
        index=rets.index, dtype=np.float64,
    )
    div_daily = (1.0 + div_annual) ** (1.0 / 252)
    tr_rets = (1.0 + rets) * div_daily - 1.0

    # Build a daily Series of the annual risk-free rate for each trading date.
    rf_annual = pd.Series(
        [_FED_FUNDS_ANNUAL.get(y, UPRO_DEFAULT_RF) for y in rets.index.year],
        index=rets.index,
        dtype=np.float64,
    )

    # Additive daily cost: deducted from the leveraged return each day.
    daily_cost = (
        (UPRO_LEVERAGE - 1.0) * (rf_annual + UPRO_FINANCING_SPREAD) + UPRO_EXPENSE_RATIO
    ) / 252.0

    # Daily leveraged total return minus financing and expense costs.
    u_rets = UPRO_LEVERAGE * tr_rets - daily_cost
    upro_prices = (1.0 + np.clip(u_rets, -0.9, 0.9)).cumprod() * 100.0
    return np.maximum(upro_prices, 0.01)


def load_and_prep_msci(data_dict: dict[str, pd.Series]) -> pd.Series:
    """
    Smart-Bridged MSCI World Engine.
    Uses real IWDA.L data if available (post-2009).
    Falls back to an enhanced synthetic model for historical coverage.
    """
    gspc_rets = data_dict["gspc"].pct_change().fillna(0.0)
    full_index = data_dict["gspc"].index

    synth_rets = gspc_rets.copy()

    # Pre-1990: Japan boom — add MSCI_PRE1990_ALPHA
    synth_rets.loc[full_index < "1990-01-01"] += (1 + MSCI_PRE1990_ALPHA) ** (1 / 252) - 1
    # Post-2010: US tech dominance — subtract MSCI_POST2010_ALPHA (negative value adds back)
    synth_rets.loc[full_index >= "2010-01-01"] -= (1 + abs(MSCI_POST2010_ALPHA)) ** (1 / 252) - 1

    div_daily = (1 + MSCI_DIVIDEND_YIELD) ** (1 / 252)
    msci_rets_final = (1 + synth_rets) * div_daily - 1

    if "msci_real" in data_dict:
        real_data = data_dict["msci_real"]
        real_rets = real_data.pct_change().fillna(0.0)
        handover_date = real_data.first_valid_index()
        # Zero all post-handover returns first, then overwrite with real IWDA.L
        # returns on the days it actually traded.  Without this step, US-only
        # trading days (GSPC open but London closed) would carry synthetic GSPC
        # returns; those days have an anomalously high average return (~55%/yr
        # annualised) that inflates the model by ~0.8–1.1 pp/yr in bull markets.
        msci_rets_final.loc[handover_date:] = 0.0
        msci_rets_final.update(real_rets.loc[handover_date:])

    msci_prices = (1 + msci_rets_final).cumprod() * 100
    return np.maximum(msci_prices, 0.01)


def load_and_prep_gold_bridge(data_dict: dict[str, pd.Series]) -> pd.Series:
    """
    Synthetic-bridge gold series.
      pre-1980         : GOLD_PRE1980_CAGR      (USD decoupling / gold rush)
      1980–real_start  : GOLD_1980_TO_REAL_CAGR (long bear market)
      real_start–now   : actual price data
    """
    g_real = data_dict["gold"].dropna()
    full_index = data_dict["gspc"].index
    g_rets = pd.Series(0.0, index=full_index)

    real_rets = g_real.pct_change().fillna(0.0)
    g_rets.update(real_rets)

    mask_70s = full_index < "1980-01-01"
    g_rets.loc[mask_70s] = (1 + GOLD_PRE1980_CAGR) ** (1 / 252) - 1

    mask_80_00 = (full_index >= "1980-01-01") & (full_index < g_real.index.min())
    g_rets.loc[mask_80_00] = (1 + GOLD_1980_TO_REAL_CAGR) ** (1 / 252) - 1

    gold_prices = (1 + g_rets).cumprod() * 100
    return np.maximum(gold_prices, 0.01)


# ==========================================
# REBALANCING ENGINE
# ==========================================

def _calculate_metrics_loop(
    prices_slice: pd.DataFrame,
    weights: dict[str, float],
) -> tuple[float, float]:
    """
    Reference loop-based rebalancing — kept for correctness tests only.
    O(n) Python iterations; use calculate_metrics() for production.
    """
    tickers = list(weights.keys())
    w_values = np.array([weights[t] for t in tickers])
    rets = prices_slice[tickers].pct_change().fillna(0).values
    n = len(rets)
    port_val = np.ones(n)
    active_shares = w_values.copy()
    for i in range(1, n):
        asset_vals = active_shares * (1 + rets[i])
        port_val[i] = np.sum(asset_vals)
        if i % REBALANCE_DAYS == 0:
            active_shares = port_val[i] * w_values
        else:
            active_shares = asset_vals
    total_mult = port_val[-1] / port_val[0]
    n_years = (prices_slice.index[-1] - prices_slice.index[0]).days / 365.25
    if n_years <= 0:
        return 0.0, 0.0
    cagr = total_mult ** (1.0 / n_years) - 1.0
    running_peak = np.maximum.accumulate(port_val)
    mdd = float(np.min(port_val / running_peak - 1.0))
    return cagr, mdd


def calculate_metrics(
    prices_slice: pd.DataFrame,
    is_rebalanced: bool = False,
    weights: Optional[dict[str, float]] = None,
) -> tuple[float, float]:
    """
    Vectorised CAGR and Max-Drawdown calculator.

    Rebalancing (every REBALANCE_DAYS trading days, default quarterly) is
    implemented without a per-day Python loop.  Instead we iterate only over
    rebalance *periods* (O(n/REBALANCE_DAYS) iterations) and use numpy's
    cumprod for within-period compounding.

    Parameters
    ----------
    prices_slice : DataFrame
        Columns are asset price series indexed by date.
    is_rebalanced : bool
        If True, simulate periodic rebalancing using `weights`.
    weights : dict[str, float]
        Target weight per ticker (must sum to 1).  Required when
        is_rebalanced=True.

    Returns
    -------
    cagr : float
    mdd  : float  (negative, e.g. -0.35 = 35% drawdown)
    """
    if is_rebalanced:
        if weights is None:
            raise ValueError("weights must be provided when is_rebalanced=True")

        tickers = list(weights.keys())
        w_arr = np.array([weights[t] for t in tickers], dtype=np.float64)

        # Build (n, n_assets) return matrix; first row → 0 (no pct_change).
        # .copy() is required because pandas 3.x to_numpy() returns a
        # read-only view under Copy-on-Write semantics.
        rets = prices_slice[tickers].pct_change().to_numpy(dtype=np.float64).copy()
        rets[0] = 0.0

        n = len(rets)
        port_val = np.empty(n, dtype=np.float64)
        port_val[0] = 1.0

        # --- Vectorised per-period cumulative compounding ---
        # Rebalance every REBALANCE_DAYS trading days (≈ quarterly by default).
        #
        # Key: the rebalance day itself is still computed using the PRE-rebalance
        # shares, then the next period starts from there.  Each period covers
        # [start+1 .. start+REBALANCE_DAYS] inclusive.
        #
        # Within each period the portfolio value is:
        #   port_val[start+k] = shares · cumprod(1+rets, axis=0)[k-1]
        # where cumprod accumulates from start+1 to start+k.
        for start in range(0, n, REBALANCE_DAYS):
            end = min(start + REBALANCE_DAYS + 1, n)   # exclusive upper bound
            if end <= start + 1:
                continue
            shares = port_val[start] * w_arr                              # (n_assets,)
            cum_prod = np.cumprod(1.0 + rets[start + 1 : end], axis=0)   # (seg_len, n_assets)
            port_val[start + 1 : end] = cum_prod @ shares                 # (seg_len,)

        final_series = port_val

    else:
        arr = prices_slice.to_numpy(dtype=np.float64)
        if arr.ndim > 1:
            arr = arr[:, 0]
        final_series = arr / arr[0]

    if len(final_series) < 2:
        return 0.0, 0.0

    total_mult = final_series[-1] / final_series[0]
    n_years = (prices_slice.index[-1] - prices_slice.index[0]).days / 365.25
    if n_years <= 0:
        return 0.0, 0.0

    cagr = total_mult ** (1.0 / n_years) - 1.0
    running_peak = np.maximum.accumulate(final_series)
    mdd = float(np.min(final_series / running_peak - 1.0))
    return cagr, mdd


def run_window(
    start_date: pd.Timestamp,
    assets: pd.DataFrame,
) -> Optional[dict]:
    end_date = start_date + pd.DateOffset(years=ROLLING_WINDOW_YEARS)
    data_slice = assets.loc[start_date:end_date]
    if len(data_slice) < WINDOW_DAYS * 0.8:
        return None

    s1_cagr, s1_mdd = calculate_metrics(data_slice, True, S1_WEIGHTS)
    s2_cagr, s2_mdd = calculate_metrics(data_slice[["spy"]])
    s3_cagr, s3_mdd = calculate_metrics(data_slice, True, S3_WEIGHTS)
    s4_cagr, s4_mdd = calculate_metrics(data_slice[["msci"]])

    return {
        "Window_End":             data_slice.index[-1],
        f"{S1_NAME} CAGR":        s1_cagr,
        f"{S1_NAME} MDD":         s1_mdd,
        "Dull S&P 500 CAGR":      s2_cagr,
        "Dull S&P 500 MDD":       s2_mdd,
        f"{S3_NAME} CAGR":        s3_cagr,
        f"{S3_NAME} MDD":         s3_mdd,
        "Dull MSCI World CAGR":   s4_cagr,
        "Dull MSCI World MDD":    s4_mdd,
    }


def main() -> None:
    print(
        f"🚀 Running GLOBAL Backtest "
        f"({START_DATE} → Present, {ROLLING_WINDOW_YEARS}y Windows)..."
    )
    assets = load_market_data()

    limit_start = assets.index[-1] - pd.DateOffset(years=ROLLING_WINDOW_YEARS)
    rolling_starts = assets.loc[START_DATE:limit_start].index[::5]

    results = Parallel(n_jobs=-1, backend="threading")(
        delayed(run_window)(s, assets) for s in tqdm(rolling_starts)
    )

    results_df = pd.DataFrame([r for r in results if r is not None])
    if results_df.empty:
        print("❌ No valid windows.")
        return

    results_df.set_index("Window_End", inplace=True)
    last_date_str = assets.index[-1].strftime("%Y-%m-%d")
    exporter = BacktestExporter(ROLLING_WINDOW_YEARS, START_DATE, last_date_str)
    exporter.export_dataframe(results_df, "rolling_msci_strategies_results.csv")
    print(f"✨ Backtest complete. Saved to {exporter.folder_name}")


if __name__ == "__main__":
    main()
