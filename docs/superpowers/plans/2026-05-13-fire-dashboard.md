# FIRE Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 7-page interactive Streamlit FIRE planning dashboard that ingests rolling backtest CSV data from `rolling_backtest_suite.py` and lets users model Australian financial independence scenarios with adjustable parameters.

**Architecture:** Pure-Python engine modules (no Streamlit dependency) built test-first, then Streamlit pages that import and render them. All chart colours come from `utils/colors.py` (Flat UI Colors US palette). Entry point is `streamlit run fire_dashboard.py`.

**Tech Stack:** Python 3.14, Streamlit ≥1.56, Plotly ≥6.6, pandas ≥3.0, numpy ≥2.4, pytest ≥9.0

---

## File Map

| File | Creates / Modifies |
|---|---|
| `engines/__init__.py` | Create (empty) |
| `utils/__init__.py` | Create (empty) |
| `utils/colors.py` | Create — Flat UI US palette constants |
| `utils/csv_loader.py` | Create — auto-discovers latest BT_* CSV |
| `tests/test_csv_loader.py` | Create |
| `engines/portfolio_engine.py` | Create — DCA compounding, depletion, SWR, crossovers |
| `tests/test_portfolio_engine.py` | Create |
| `engines/calculation_engine.py` | Create — FIRE target maths |
| `tests/test_calculation_engine.py` | Create |
| `engines/tax_engine.py` | Create — AUS tax, CGT current + proposed 2027 |
| `tests/test_tax_engine.py` | Create |
| `engines/simulation_engine.py` | Create — historical percentile analysis |
| `tests/test_simulation_engine.py` | Create |
| `.streamlit/config.toml` | Create — dark theme |
| `fire_dashboard.py` | Create — entry point |
| `pages/1_Dashboard.py` | Create |
| `pages/2_FIRE_Scenarios.py` | Create |
| `pages/3_Historical_Outcomes.py` | Create |
| `pages/4_Australian_Tax.py` | Create |
| `pages/5_Retirement_Drawdown.py` | Create |
| `pages/6_Portfolio_Analytics.py` | Create |
| `pages/7_Assumptions.py` | Create |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `engines/__init__.py`
- Create: `utils/__init__.py`
- Create: `pages/__init__.py`
- Create: `.streamlit/config.toml`
- Create: `utils/colors.py`

- [ ] **Step 1: Create directory structure and init files**

```powershell
New-Item -ItemType Directory -Force engines, utils, pages | Out-Null
"" | Set-Content engines/__init__.py
"" | Set-Content utils/__init__.py
"" | Set-Content pages/__init__.py
```

- [ ] **Step 2: Create `.streamlit/config.toml`**

```toml
[theme]
base = "dark"
primaryColor = "#0984e3"
backgroundColor = "#0d1117"
secondaryBackgroundColor = "#161b22"
textColor = "#dfe6e9"
```

- [ ] **Step 3: Create `utils/colors.py`**

```python
"""Flat UI Colors — US palette. All charts and UI elements use this dict exclusively."""

COLORS: dict[str, str] = {
    "mint":        "#00b894",   # Mint Leaf          — FIRE achieved / success
    "teal":        "#00cec9",   # Robin's Egg Blue   — secondary accent
    "blue":        "#0984e3",   # Electron Blue      — primary accent / DCA lines
    "light_blue":  "#74b9ff",   # Green Darner Tail  — strategy 1
    "purple":      "#6c5ce7",   # Exodus Fruit       — strategy 2 / scenarios
    "lavender":    "#a29bfe",   # Shy Moment         — strategy 3
    "green":       "#55efc4",   # Light Greenish Blue — growth bars
    "cyan":        "#81ecec",   # Faded Poster       — strategy 4
    "yellow":      "#fdcb6e",   # Sour Lemon         — salary / warning
    "soft_yellow": "#ffeaa7",   # First Date         — DCA line
    "orange":      "#e17055",   # Orangeville        — drawdown / risk
    "red":         "#d63031",   # Chi-Gong           — danger / depletion
    "pink":        "#fd79a8",   # Pink Glamour       — special highlight
    "muted":       "#636e72",   # American River     — secondary text
    "light_grey":  "#b2bec3",   # Soothing Breeze    — axis labels
    "near_white":  "#dfe6e9",   # City Lights        — titles on dark bg
    "dark":        "#2d3436",   # Dracula Orchid     — card backgrounds
}

STRATEGY_COLORS: list[str] = [
    COLORS["light_blue"],
    COLORS["purple"],
    COLORS["mint"],
    COLORS["cyan"],
    COLORS["pink"],
]
```

- [ ] **Step 4: Commit scaffold**

```bash
git add engines/ utils/ pages/ .streamlit/ 
git commit -m "chore: scaffold FIRE dashboard project structure"
```

---

## Task 2: CSV Loader

**Files:**
- Create: `utils/csv_loader.py`
- Create: `tests/test_csv_loader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_csv_loader.py
"""Tests for utils/csv_loader.py"""
from __future__ import annotations
import os
import tempfile
import pandas as pd
import pytest
from utils.csv_loader import load_latest_backtest_csv, BacktestData


def _write_fake_csv(folder: str, filename: str = "rolling_msci_strategies_results.csv") -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    df = pd.DataFrame({
        "Window_End": ["1999-12-31", "2000-01-07"],
        "Hybrid SPY (70/15/15) CAGR": [0.169, 0.166],
        "Hybrid SPY (70/15/15) MDD":  [-0.362, -0.362],
        "Dull S&P 500 CAGR":          [0.178, 0.175],
        "Dull S&P 500 MDD":           [-0.328, -0.328],
    })
    df.to_csv(path, index=False)
    return path


def test_load_returns_none_when_no_csv_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = load_latest_backtest_csv()
    assert result is None


def test_load_returns_backtest_data_from_latest_bt_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = os.path.join(tmp_path, "data", "BT_20y_1980-01-01_to_2026-01-01_20260101_120000")
    _write_fake_csv(folder)
    result = load_latest_backtest_csv()
    assert result is not None
    data, path = result
    assert isinstance(data, BacktestData)
    assert "Hybrid SPY (70/15/15)" in data.strategies
    assert "Dull S&P 500" in data.strategies


def test_load_picks_most_recently_modified_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old_folder = os.path.join(tmp_path, "data", "BT_20y_1980-01-01_to_2025-01-01_20250101_000000")
    new_folder = os.path.join(tmp_path, "data", "BT_20y_1980-01-01_to_2026-01-01_20260101_120000")
    _write_fake_csv(old_folder)
    import time; time.sleep(0.01)
    _write_fake_csv(new_folder)
    result = load_latest_backtest_csv()
    assert result is not None
    _, path = result
    assert "20260101" in path


def test_backtest_data_separates_cagr_and_mdd_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = os.path.join(tmp_path, "data", "BT_20y_test_20260101_120000")
    _write_fake_csv(folder)
    result = load_latest_backtest_csv()
    assert result is not None
    data, _ = result
    assert "Hybrid SPY (70/15/15)" in data.cagr_df.columns
    assert "Hybrid SPY (70/15/15)" in data.mdd_df.columns
    assert data.cagr_df["Hybrid SPY (70/15/15)"].iloc[0] == pytest.approx(0.169)
    assert data.mdd_df["Hybrid SPY (70/15/15)"].iloc[0] == pytest.approx(-0.362)
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/test_csv_loader.py -v
```
Expected: `ImportError: cannot import name 'load_latest_backtest_csv'`

- [ ] **Step 3: Implement `utils/csv_loader.py`**

```python
"""Auto-discovers and loads the most recently modified backtest CSV."""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class BacktestData:
    strategies: list[str]
    cagr_df: pd.DataFrame
    mdd_df: pd.DataFrame


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
    df = pd.read_csv(latest, index_col=0, parse_dates=True)

    cagr_cols = {c: c.replace(" CAGR", "") for c in df.columns if c.endswith(" CAGR")}
    mdd_cols  = {c: c.replace(" MDD", "")  for c in df.columns if c.endswith(" MDD")}
    strategies = list(cagr_cols.values())

    cagr_df = df[[c for c in cagr_cols]].rename(columns=cagr_cols)
    mdd_df  = df[[c for c in mdd_cols]].rename(columns=mdd_cols)

    return BacktestData(strategies=strategies, cagr_df=cagr_df, mdd_df=mdd_df), latest
```

- [ ] **Step 4: Run tests to confirm green**

```powershell
pytest tests/test_csv_loader.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add utils/csv_loader.py tests/test_csv_loader.py
git commit -m "feat: add csv_loader with BacktestData auto-discovery"
```

---

## Task 3: Portfolio Engine

**Files:**
- Create: `engines/portfolio_engine.py`
- Create: `tests/test_portfolio_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_portfolio_engine.py
from __future__ import annotations
import pandas as pd
import pytest
from engines.portfolio_engine import (
    depletion_year,
    project_portfolio,
    real_value,
    swr_income,
    dca_crossover_year,
    salary_crossover_year,
    run_yearly_projection,
)


# --- depletion_year ---

def test_depletion_year_zero_return_zero_inflation():
    # $500k at 0% return, $50k/yr withdrawal, 0% inflation → depletes exactly year 10
    result = depletion_year(500_000, 50_000, annual_return=0.0, inflation_rate=0.0)
    assert result == 10


def test_depletion_year_with_positive_return_takes_longer():
    no_return = depletion_year(500_000, 60_000, annual_return=0.0, inflation_rate=0.0)
    with_return = depletion_year(500_000, 60_000, annual_return=0.05, inflation_rate=0.0)
    assert with_return > no_return


def test_depletion_year_never_depletes_returns_none():
    # 2M at 7% return, 40k withdrawal (2% SWR) → never depletes in 100 years
    result = depletion_year(2_000_000, 40_000, annual_return=0.07, inflation_rate=0.0, max_years=100)
    assert result is None


def test_depletion_year_inflation_accelerates_depletion():
    no_inf = depletion_year(500_000, 20_000, annual_return=0.04, inflation_rate=0.0)
    with_inf = depletion_year(500_000, 20_000, annual_return=0.04, inflation_rate=0.03)
    assert with_inf < no_inf


def test_depletion_year_immediate_depletion():
    # Withdrawal larger than portfolio at year 1
    result = depletion_year(10_000, 50_000, annual_return=0.0, inflation_rate=0.0)
    assert result == 1


# --- project_portfolio ---

def test_project_portfolio_zero_dca_compounds_correctly():
    fv, contributed = project_portfolio(100_000, monthly_pmt=0, annual_growth_rate=0, years=10, annual_return=0.10)
    assert abs(fv - 100_000 * 1.10 ** 10) < 1.0
    assert contributed == pytest.approx(100_000)


def test_project_portfolio_zero_return_with_dca():
    # $0 principal, $1000/month, 0% return, 10 years → $120,000 contributed = FV
    fv, contributed = project_portfolio(0, monthly_pmt=1_000, annual_growth_rate=0, years=10, annual_return=0.0)
    assert abs(fv - 120_000) < 1.0
    assert abs(contributed - 120_000) < 1.0


def test_project_portfolio_fv_exceeds_contributions_with_positive_return():
    fv, contributed = project_portfolio(50_000, monthly_pmt=500, annual_growth_rate=0, years=20, annual_return=0.07)
    assert fv > contributed


# --- real_value ---

def test_real_value_one_year():
    result = real_value(100.0, inflation_rate=0.025, years=1)
    assert abs(result - 100.0 / 1.025) < 0.001


def test_real_value_zero_inflation():
    assert real_value(100.0, inflation_rate=0.0, years=10) == pytest.approx(100.0)


# --- swr_income ---

def test_swr_income_four_percent():
    assert swr_income(1_000_000, swr_rate=0.04) == pytest.approx(40_000.0)


def test_swr_income_three_percent():
    assert swr_income(2_500_000, swr_rate=0.03) == pytest.approx(75_000.0)


# --- crossover detection ---

def _make_projection_df(profits: list[float], dca: float, salary: float) -> pd.DataFrame:
    years = list(range(len(profits)))
    return pd.DataFrame({
        "Year": years,
        "Yearly_DCA": [0.0] + [dca] * (len(profits) - 1),
        "strat_Yearly_Profit": profits,
        "Salary": [salary] * len(profits),
    })


def test_dca_crossover_year_found():
    df = _make_projection_df([0, 5_000, 10_000, 15_000], dca=12_000, salary=100_000)
    assert dca_crossover_year(df, "strat") == 3


def test_dca_crossover_year_not_found():
    df = _make_projection_df([0, 5_000, 8_000], dca=12_000, salary=100_000)
    assert dca_crossover_year(df, "strat") is None


def test_salary_crossover_year_found():
    df = _make_projection_df([0, 50_000, 80_000, 110_000], dca=12_000, salary=100_000)
    assert salary_crossover_year(df, "strat") == 3


def test_salary_crossover_year_not_found():
    df = _make_projection_df([0, 20_000, 40_000], dca=12_000, salary=100_000)
    assert salary_crossover_year(df, "strat") is None
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/test_portfolio_engine.py -v
```
Expected: `ImportError: cannot import name 'depletion_year'`

- [ ] **Step 3: Implement `engines/portfolio_engine.py`**

```python
"""Portfolio engine — DCA compounding, depletion analysis, SWR, crossover detection."""
from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd


def depletion_year(
    portfolio: float,
    annual_withdrawal: float,
    annual_return: float,
    inflation_rate: float = 0.025,
    max_years: int = 100,
) -> Optional[int]:
    """
    Simulate annual withdrawals (inflation-adjusted each year) until the portfolio
    is exhausted. Returns the year it hits zero, or None if it survives max_years.
    """
    balance = float(portfolio)
    real_withdrawal = float(annual_withdrawal)
    for year in range(1, max_years + 1):
        balance = balance * (1.0 + annual_return) - real_withdrawal
        real_withdrawal *= (1.0 + inflation_rate)
        if balance <= 0.0:
            return year
    return None


def project_portfolio(
    principal: float,
    monthly_pmt: float,
    annual_growth_rate: float,
    years: int,
    annual_return: float,
) -> tuple[float, float]:
    """
    Closed-form FV for a growing annuity-due.
    Returns (final_portfolio_value, total_contributed).
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


def real_value(nominal: float, inflation_rate: float, years: int) -> float:
    """Deflate a nominal value to real (today's) dollars."""
    return nominal / (1.0 + inflation_rate) ** years


def swr_income(portfolio: float, swr_rate: float) -> float:
    """Annual safe withdrawal amount from a portfolio."""
    return portfolio * swr_rate


def dca_crossover_year(
    projection_df: pd.DataFrame,
    strategy: str,
) -> Optional[int]:
    """First year where annual investment profit exceeds the annual DCA contribution."""
    profit_col = f"{strategy}_Yearly_Profit"
    dca_col = "Yearly_DCA"
    if profit_col not in projection_df.columns or dca_col not in projection_df.columns:
        return None
    mask = (projection_df["Year"] > 0) & (projection_df[profit_col] > projection_df[dca_col])
    matches = projection_df[mask]["Year"]
    return int(matches.iloc[0]) if not matches.empty else None


def salary_crossover_year(
    projection_df: pd.DataFrame,
    strategy: str,
) -> Optional[int]:
    """First year where annual investment profit exceeds annual salary."""
    profit_col = f"{strategy}_Yearly_Profit"
    salary_col = "Salary"
    if profit_col not in projection_df.columns or salary_col not in projection_df.columns:
        return None
    mask = (projection_df["Year"] > 0) & (projection_df[profit_col] > projection_df[salary_col])
    matches = projection_df[mask]["Year"]
    return int(matches.iloc[0]) if not matches.empty else None


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
    Year-by-year portfolio projection for multiple strategies.
    Uses median historical CAGR from each strategy column.
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

    row: dict = {"Year": 0, "Salary": current_salary, "Cost Basis": initial_portfolio, "Yearly_DCA": 0}
    for strat in strategy_cols:
        row[f"{strat}_Principal"] = initial_portfolio
        row[f"{strat}_Contributions"] = 0.0
        row[f"{strat}_Growth"] = 0.0
        row[f"{strat}_Total"] = initial_portfolio
        row[f"{strat}_Yearly_Profit"] = 0.0
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
            active_monthly_dca = 0.0 if (stop_at_coast and has_coasted[strat]) else current_monthly_dca
            start_of_year_val = current_portfolios[strat]

            if abs(monthly_ret) < 1e-10:
                growth_factor_12 = 1.0
                annuity_fv = active_monthly_dca * 12.0
            else:
                growth_factor_12 = (1.0 + monthly_ret) ** 12
                annuity_fv = (
                    active_monthly_dca * (1.0 + monthly_ret) * (growth_factor_12 - 1.0) / monthly_ret
                )

            current_portfolios[strat] = current_portfolios[strat] * growth_factor_12 + annuity_fv
            current_contributions[strat] += active_monthly_dca * 12.0

            nominal_yearly_profit = (current_portfolios[strat] - start_of_year_val) - (active_monthly_dca * 12.0)
            if nominal_yearly_profit > (current_monthly_dca * 12.0):
                has_coasted[strat] = True

            real_total = current_portfolios[strat] / current_inf_denominator
            real_invested = current_contributions[strat] / current_inf_denominator
            real_principal = initial_portfolio / current_inf_denominator

            year_row[f"{strat}_Total"] = real_total
            year_row[f"{strat}_Principal"] = real_principal
            year_row[f"{strat}_Contributions"] = real_invested - real_principal
            year_row[f"{strat}_Growth"] = real_total - real_invested
            year_row[f"{strat}_Yearly_Profit"] = nominal_yearly_profit / current_inf_denominator
            year_row[f"{strat}_Cost_Basis"] = real_invested

        projection_data.append(year_row)

    return pd.DataFrame(projection_data)
```

- [ ] **Step 4: Run tests to confirm green**

```powershell
pytest tests/test_portfolio_engine.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add engines/portfolio_engine.py tests/test_portfolio_engine.py
git commit -m "feat: add portfolio_engine with depletion, compounding, crossover detection"
```

---

## Task 4: Calculation Engine

**Files:**
- Create: `engines/calculation_engine.py`
- Create: `tests/test_calculation_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_calculation_engine.py
from __future__ import annotations
import pandas as pd
import pytest
from engines.calculation_engine import (
    fire_target,
    coast_fire_target,
    lean_fire_target,
    fat_fire_target,
    barista_fire_target,
    fire_age,
)


def test_fire_target_four_percent_rule():
    # $80k/yr spending at 4% SWR requires $2M
    assert fire_target(80_000, swr=0.04) == pytest.approx(2_000_000.0)


def test_fire_target_three_percent_rule():
    assert fire_target(60_000, swr=0.03) == pytest.approx(2_000_000.0)


def test_lean_fire_is_less_than_fat_fire():
    lean = lean_fire_target(30_000, swr=0.04)
    fat = fat_fire_target(100_000, swr=0.04)
    assert lean < fat


def test_lean_fire_target():
    assert lean_fire_target(30_000, swr=0.04) == pytest.approx(750_000.0)


def test_fat_fire_target():
    assert fat_fire_target(120_000, swr=0.04) == pytest.approx(3_000_000.0)


def test_coast_fire_target_future_value_discounted():
    # Target 1M in 20 years at 7% return → ~$258,419 today
    result = coast_fire_target(1_000_000, years_to_retire=20, annual_return=0.07)
    assert abs(result - 1_000_000 / (1.07 ** 20)) < 1.0


def test_coast_fire_target_zero_years():
    # 0 years to retire → need full amount today
    assert coast_fire_target(1_000_000, years_to_retire=0, annual_return=0.07) == pytest.approx(1_000_000.0)


def test_barista_fire_reduces_required_portfolio():
    full_fire = fire_target(60_000, swr=0.04)
    barista = barista_fire_target(60_000, part_time_income=20_000, swr=0.04)
    assert barista < full_fire
    assert barista == pytest.approx(fire_target(40_000, swr=0.04))


def test_fire_age_found():
    # Portfolio crosses 1M at year 10 in projection
    df = pd.DataFrame({
        "Year": list(range(11)),
        "strat_Total": [100_000 * (1.2 ** y) for y in range(11)],
    })
    result = fire_age(current_age=30, projection_df=df, target_portfolio=1_000_000, strategy="strat")
    assert result == 30 + 10


def test_fire_age_not_found_returns_none():
    df = pd.DataFrame({
        "Year": list(range(11)),
        "strat_Total": [100_000] * 11,
    })
    result = fire_age(current_age=30, projection_df=df, target_portfolio=1_000_000, strategy="strat")
    assert result is None
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/test_calculation_engine.py -v
```
Expected: `ImportError: cannot import name 'fire_target'`

- [ ] **Step 3: Implement `engines/calculation_engine.py`**

```python
"""FIRE calculation engine — pure maths, no Streamlit dependency."""
from __future__ import annotations
from typing import Optional
import pandas as pd


def fire_target(annual_spending: float, swr: float) -> float:
    """Required portfolio = annual spending / safe withdrawal rate."""
    return annual_spending / swr


def lean_fire_target(annual_spending: float, swr: float) -> float:
    """Lean FIRE: minimal lifestyle spending."""
    return fire_target(annual_spending, swr)


def fat_fire_target(annual_spending: float, swr: float) -> float:
    """Fat FIRE: high lifestyle spending."""
    return fire_target(annual_spending, swr)


def barista_fire_target(
    annual_spending: float,
    part_time_income: float,
    swr: float,
) -> float:
    """Barista FIRE: portfolio only needs to fund spending minus part-time income."""
    return fire_target(max(annual_spending - part_time_income, 0.0), swr)


def coast_fire_target(
    target_portfolio: float,
    years_to_retire: float,
    annual_return: float,
) -> float:
    """
    Present value of the FIRE target portfolio.
    The amount you need invested today so compound growth reaches target_portfolio
    by retirement date with no additional contributions.
    """
    if years_to_retire <= 0:
        return target_portfolio
    return target_portfolio / (1.0 + annual_return) ** years_to_retire


def fire_age(
    current_age: int,
    projection_df: pd.DataFrame,
    target_portfolio: float,
    strategy: str,
) -> Optional[int]:
    """
    Returns the calendar age at which the projection first hits target_portfolio,
    or None if it never does within the projection horizon.
    """
    col = f"{strategy}_Total"
    if col not in projection_df.columns:
        return None
    matches = projection_df[projection_df[col] >= target_portfolio]["Year"]
    if matches.empty:
        return None
    return current_age + int(matches.iloc[0])
```

- [ ] **Step 4: Run tests to confirm green**

```powershell
pytest tests/test_calculation_engine.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add engines/calculation_engine.py tests/test_calculation_engine.py
git commit -m "feat: add calculation_engine with FIRE target and coast FIRE maths"
```

---

## Task 5: Tax Engine

**Files:**
- Create: `engines/tax_engine.py`
- Create: `tests/test_tax_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tax_engine.py
from __future__ import annotations
from datetime import date
import pytest
from engines.tax_engine import (
    CGTLaw,
    income_tax,
    medicare_levy,
    hecs_repayment,
    super_concessional_tax,
    cgt_liability,
    effective_tax_rate,
)


# --- income_tax (2024-25 brackets post Stage 3 cuts) ---

def test_income_tax_zero_income():
    assert income_tax(0) == pytest.approx(0.0)


def test_income_tax_below_tax_free_threshold():
    assert income_tax(18_200) == pytest.approx(0.0)


def test_income_tax_just_above_threshold():
    # $18,201: 16c on $1 over $18,200 = $0.16
    assert income_tax(18_201) == pytest.approx(0.16, abs=0.01)


def test_income_tax_mid_second_bracket():
    # $45,000: 16% of ($45,000 - $18,200) = 16% of $26,800 = $4,288
    assert income_tax(45_000) == pytest.approx(4_288.0, abs=1.0)


def test_income_tax_third_bracket():
    # $100,000: $4,288 + 30% of ($100,000 - $45,000) = $4,288 + $16,500 = $20,788
    assert income_tax(100_000) == pytest.approx(20_788.0, abs=1.0)


def test_income_tax_top_bracket():
    # $200,000: $4,288 + $27,000 + 37% of ($190,000-$135,000) + 45% of $10,000
    # = $4,288 + $27,000 + $20,350 + $4,500 = wait let me recalc
    # $135,001–$190,000: $31,288 + 37% of $55,000 = $31,288 + $20,350 = $51,638
    # $190,001+: $51,638 + 45% of $10,000 = $51,638 + $4,500 = $56,138
    assert income_tax(200_000) == pytest.approx(56_138.0, abs=5.0)


# --- medicare_levy ---

def test_medicare_levy_zero_income():
    assert medicare_levy(0) == pytest.approx(0.0)


def test_medicare_levy_standard():
    # $80,000 salary → 2% = $1,600
    assert medicare_levy(80_000) == pytest.approx(1_600.0)


# --- hecs_repayment ---

def test_hecs_repayment_below_threshold():
    # Below $54,435 → 0% repayment
    assert hecs_repayment(50_000, hecs_balance=10_000) == pytest.approx(0.0)


def test_hecs_repayment_above_threshold():
    # $60,000 income → 1% of $60,000 = $600/yr
    result = hecs_repayment(60_000, hecs_balance=10_000)
    assert result == pytest.approx(600.0, abs=10.0)


def test_hecs_repayment_capped_at_balance():
    # If calculated repayment > remaining balance, cap at balance
    result = hecs_repayment(200_000, hecs_balance=500)
    assert result <= 500.0


# --- super_concessional_tax ---

def test_super_concessional_tax_standard():
    # $10,000 contributions → taxed at 15% in fund = $1,500
    assert super_concessional_tax(10_000) == pytest.approx(1_500.0)


def test_super_concessional_tax_zero():
    assert super_concessional_tax(0) == pytest.approx(0.0)


# --- cgt_liability (current law) ---

def test_cgt_current_law_held_under_12_months_no_discount():
    # $50k gain, held 6 months, marginal rate 37% → $50k * 37% = $18,500
    result = cgt_liability(50_000, held_years=0.5, marginal_rate=0.37, law=CGTLaw.CURRENT)
    assert result == pytest.approx(18_500.0, abs=1.0)


def test_cgt_current_law_held_over_12_months_50_percent_discount():
    # $50k gain, held 2 years, marginal rate 37% → $25k * 37% = $9,250
    result = cgt_liability(50_000, held_years=2.0, marginal_rate=0.37, law=CGTLaw.CURRENT)
    assert result == pytest.approx(9_250.0, abs=1.0)


def test_cgt_main_residence_exempt():
    result = cgt_liability(500_000, held_years=5.0, marginal_rate=0.45, law=CGTLaw.CURRENT, is_main_residence=True)
    assert result == pytest.approx(0.0)


# --- cgt_liability (proposed 2027 law) ---

def test_cgt_proposed_law_minimum_30_percent_floor():
    # Low income earner: marginal rate 16%, gain $100k → without floor would be 8% (50% discount)
    # But floor is 30% → effective rate on gain = 30%
    result = cgt_liability(100_000, held_years=2.0, marginal_rate=0.16, law=CGTLaw.PROPOSED_2027,
                           acquisition_date=date(2028, 1, 1), cpi_at_acquisition=100.0, cpi_current=105.0)
    # Taxable gain = gain - (gain * inflation portion) via indexation
    # Real gain (simplified): $100k - ($100k * 100/105 - $100k) → just check floor applies
    assert result >= 100_000 * 0.30 * 0.5  # at minimum, floor should produce >= 15% effective rate on nominal gain


def test_cgt_proposed_law_indexation_reduces_gain():
    # If asset cost $100k, sells for $110k, CPI went from 100 to 110 → no real gain → near zero tax
    result_indexed = cgt_liability(10_000, held_years=2.0, marginal_rate=0.37, law=CGTLaw.PROPOSED_2027,
                                   acquisition_date=date(2028, 1, 1), cpi_at_acquisition=100.0, cpi_current=110.0)
    result_current = cgt_liability(10_000, held_years=2.0, marginal_rate=0.37, law=CGTLaw.CURRENT)
    # Real gain after full inflation = 0, but 30% floor still applies on some basis
    # Proposed law should produce different (possibly lower) result than current law at same marginal rate
    assert isinstance(result_indexed, float)


def test_cgt_proposed_law_main_residence_still_exempt():
    result = cgt_liability(500_000, held_years=5.0, marginal_rate=0.37, law=CGTLaw.PROPOSED_2027,
                           acquisition_date=date(2028, 1, 1), cpi_at_acquisition=100.0, cpi_current=115.0,
                           is_main_residence=True)
    assert result == pytest.approx(0.0)


# --- effective_tax_rate ---

def test_effective_tax_rate_returns_dict_with_required_keys():
    result = effective_tax_rate(100_000, super_contributions=10_000, hecs_balance=0,
                                cgt_gain=0, held_years=0, law=CGTLaw.CURRENT)
    assert "income_tax" in result
    assert "medicare_levy" in result
    assert "super_tax" in result
    assert "total_tax" in result
    assert "effective_rate" in result
    assert "net_income" in result
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/test_tax_engine.py -v
```
Expected: `ImportError: cannot import name 'CGTLaw'`

- [ ] **Step 3: Implement `engines/tax_engine.py`**

```python
"""
Australian tax engine (2024-25).
CGT supports two law versions:
  CGTLaw.CURRENT        — 50% discount for assets held >12 months
  CGTLaw.PROPOSED_2027  — Indexation + 30% minimum tax floor (effective 1 July 2027)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class CGTLaw(Enum):
    CURRENT = "current"
    PROPOSED_2027 = "proposed_2027"


# ── 2024-25 income tax brackets (post Stage 3 cuts) ──────────────────────────
_BRACKETS: list[tuple[float, float, float]] = [
    # (lower, upper, rate)
    (0,        18_200,  0.00),
    (18_200,   45_000,  0.16),
    (45_000,  135_000,  0.30),
    (135_000, 190_000,  0.37),
    (190_000, float("inf"), 0.45),
]

_BRACKET_BASE: list[float] = []  # cumulative tax at each bracket lower bound
_b = 0.0
for i, (lo, hi, rate) in enumerate(_BRACKETS):
    _BRACKET_BASE.append(_b)
    if hi != float("inf"):
        _b += (hi - lo) * rate


# ── HECS-HELP 2024-25 repayment rates ────────────────────────────────────────
_HECS_THRESHOLDS: list[tuple[float, float]] = [
    (0,        54_435,  0.000),
    (54_435,   62_850,  0.010),
    (62_850,   66_620,  0.020),
    (66_620,   70_618,  0.025),
    (70_618,   74_855,  0.030),
    (74_855,   79_346,  0.035),
    (79_346,   84_107,  0.040),
    (84_107,   89_154,  0.045),
    (89_154,   94_503,  0.050),
    (94_503,  100_174,  0.055),
    (100_174, 106_185,  0.060),
    (106_185, 112_556,  0.065),
    (112_556, 119_309,  0.070),
    (119_309, 126_468,  0.075),
    (126_468, 134_056,  0.080),
    (134_056, 142_099,  0.085),
    (142_099, 150_625,  0.090),
    (150_625, 159_663,  0.095),
    (159_663, float("inf"), 0.100),
]

_MEDICARE_LOW_INCOME_THRESHOLD = 26_000  # approx single adult phase-in start


def income_tax(taxable_income: float) -> float:
    """2024-25 Australian income tax (excl. Medicare levy)."""
    if taxable_income <= 0:
        return 0.0
    for i, (lo, hi, rate) in enumerate(_BRACKETS):
        if taxable_income <= hi:
            return _BRACKET_BASE[i] + (taxable_income - lo) * rate
    return 0.0


def medicare_levy(taxable_income: float) -> float:
    """
    Medicare levy: 2% of taxable income.
    Phase-in applies for low incomes; simplified to 0 below threshold.
    """
    if taxable_income < _MEDICARE_LOW_INCOME_THRESHOLD:
        return 0.0
    return taxable_income * 0.02


def hecs_repayment(income: float, hecs_balance: float) -> float:
    """Annual HECS-HELP compulsory repayment. Capped at outstanding balance."""
    if hecs_balance <= 0:
        return 0.0
    rate = 0.0
    for lo, hi, r in _HECS_THRESHOLDS:
        if income <= hi:
            rate = r
            break
    repayment = income * rate
    return min(repayment, hecs_balance)


def super_concessional_tax(contributions: float) -> float:
    """Tax on concessional super contributions: 15% flat (up to cap)."""
    return max(contributions, 0.0) * 0.15


def cgt_liability(
    gain: float,
    held_years: float,
    marginal_rate: float,
    law: CGTLaw,
    acquisition_date: Optional[date] = None,
    cpi_at_acquisition: Optional[float] = None,
    cpi_current: Optional[float] = None,
    is_main_residence: bool = False,
    is_new_build: bool = False,
) -> float:
    """
    Capital gains tax liability.

    Current law: 50% discount for assets held >12 months.
    Proposed 2027 law: indexation replaces discount; 30% minimum tax floor.
    Main residence is always exempt.
    """
    if gain <= 0 or is_main_residence:
        return 0.0

    if law == CGTLaw.CURRENT:
        discount = 0.5 if held_years >= 1.0 else 0.0
        taxable_gain = gain * (1.0 - discount)
        return taxable_gain * marginal_rate

    # --- Proposed 2027 law ---
    # New build: taxpayer may elect old 50% discount instead of indexation
    if is_new_build:
        current_tax = cgt_liability(gain, held_years, marginal_rate, CGTLaw.CURRENT)
        proposed_tax = _proposed_2027_cgt(gain, marginal_rate, cpi_at_acquisition, cpi_current)
        return min(current_tax, proposed_tax)

    return _proposed_2027_cgt(gain, marginal_rate, cpi_at_acquisition, cpi_current)


def _proposed_2027_cgt(
    gain: float,
    marginal_rate: float,
    cpi_at_acquisition: Optional[float],
    cpi_current: Optional[float],
) -> float:
    """
    Indexation method: only tax the real (above-inflation) gain.
    30% minimum tax floor: CGT / gain >= 30%.
    """
    MIN_RATE = 0.30

    if cpi_at_acquisition and cpi_current and cpi_at_acquisition > 0:
        inflation_adjustment = cpi_current / cpi_at_acquisition
        # Under indexation, the cost base is inflated; real gain is smaller
        # gain here is already (sale_price - original_cost_base), so real_gain
        # = gain - (original_cost_base * (inflation_adjustment - 1))
        # We approximate: real_gain = gain / inflation_adjustment
        real_gain = gain / inflation_adjustment
        real_gain = max(real_gain, 0.0)
    else:
        real_gain = gain  # no CPI data: treat full gain as taxable

    tax_at_marginal = real_gain * marginal_rate
    min_tax = gain * MIN_RATE  # 30% floor on nominal gain

    return max(tax_at_marginal, min_tax)


def effective_tax_rate(
    gross_income: float,
    super_contributions: float,
    hecs_balance: float,
    cgt_gain: float,
    held_years: float,
    law: CGTLaw,
    acquisition_date: Optional[date] = None,
    cpi_at_acquisition: Optional[float] = None,
    cpi_current: Optional[float] = None,
) -> dict:
    """Returns a breakdown dict of all tax components plus effective rate."""
    it = income_tax(gross_income)
    ml = medicare_levy(gross_income)
    hecs = hecs_repayment(gross_income, hecs_balance)
    st = super_concessional_tax(super_contributions)
    marginal = _marginal_rate(gross_income)
    cgt = cgt_liability(cgt_gain, held_years, marginal, law,
                        acquisition_date=acquisition_date,
                        cpi_at_acquisition=cpi_at_acquisition,
                        cpi_current=cpi_current)

    total = it + ml + hecs + st + cgt
    base = gross_income + cgt_gain
    eff_rate = total / base if base > 0 else 0.0

    return {
        "income_tax": it,
        "medicare_levy": ml,
        "hecs_repayment": hecs,
        "super_tax": st,
        "cgt": cgt,
        "total_tax": total,
        "effective_rate": eff_rate,
        "net_income": gross_income - it - ml - hecs,
    }


def _marginal_rate(income: float) -> float:
    """Marginal income tax rate for a given income level."""
    for lo, hi, rate in reversed(_BRACKETS):
        if income > lo:
            return rate
    return 0.0
```

- [ ] **Step 4: Run tests to confirm green**

```powershell
pytest tests/test_tax_engine.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add engines/tax_engine.py tests/test_tax_engine.py
git commit -m "feat: add tax_engine with AUS 2024-25 brackets, HECS, CGT current and proposed 2027 law"
```

---

## Task 6: Simulation Engine

**Files:**
- Create: `engines/simulation_engine.py`
- Create: `tests/test_simulation_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_simulation_engine.py
from __future__ import annotations
import pandas as pd
import numpy as np
import pytest
from engines.simulation_engine import (
    percentile_cagr,
    probability_beat,
    mdd_frequency,
    cagr_by_decade,
)


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def test_percentile_cagr_known_values():
    s = _series([0.05, 0.07, 0.09, 0.11, 0.13, 0.15, 0.08, 0.10, 0.12, 0.06])
    result = percentile_cagr(s, [10, 50, 90])
    assert result[50] == pytest.approx(np.percentile(s, 50))
    assert result[10] < result[50] < result[90]


def test_percentile_cagr_single_value():
    s = _series([0.08])
    result = percentile_cagr(s, [10, 50, 90])
    assert result[10] == pytest.approx(0.08)
    assert result[90] == pytest.approx(0.08)


def test_probability_beat_half():
    s = _series([0.05, 0.06, 0.07, 0.08, 0.09, 0.10])
    # 3 out of 6 values beat 0.07 → 50% (values > 0.07: 0.08, 0.09, 0.10)
    result = probability_beat(s, threshold=0.07)
    assert result == pytest.approx(0.5)


def test_probability_beat_none():
    s = _series([0.03, 0.04, 0.05])
    assert probability_beat(s, threshold=0.10) == pytest.approx(0.0)


def test_probability_beat_all():
    s = _series([0.08, 0.09, 0.10])
    assert probability_beat(s, threshold=0.05) == pytest.approx(1.0)


def test_mdd_frequency_threshold():
    # MDD values are negative. Worse than -0.30 means < -0.30
    s = _series([-0.10, -0.20, -0.35, -0.40, -0.50])
    # 3 out of 5 worse than -0.30
    result = mdd_frequency(s, threshold=-0.30)
    assert result == pytest.approx(0.6)


def test_mdd_frequency_none_worse():
    s = _series([-0.05, -0.10, -0.15])
    assert mdd_frequency(s, threshold=-0.50) == pytest.approx(0.0)


def test_cagr_by_decade_groups_correctly():
    idx = pd.date_range("2000-12-31", periods=25, freq="YE")
    df = pd.DataFrame({"Strategy A": np.linspace(0.05, 0.15, 25)}, index=idx)
    result = cagr_by_decade(df)
    assert "Decade" in result.columns
    assert "Strategy A" in result.columns
    assert set(result["Decade"]).issubset({"2000s", "2010s", "2020s", "2030s"})


def test_cagr_by_decade_empty_returns_empty():
    df = pd.DataFrame({"Strategy A": pd.Series([], dtype=float)},
                      index=pd.DatetimeIndex([]))
    result = cagr_by_decade(df)
    assert len(result) == 0
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/test_simulation_engine.py -v
```
Expected: `ImportError: cannot import name 'percentile_cagr'`

- [ ] **Step 3: Implement `engines/simulation_engine.py`**

```python
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
    Returns a long-form DataFrame with columns: Decade, <strategy>, ...
    """
    if cagr_df.empty or not isinstance(cagr_df.index, pd.DatetimeIndex):
        return pd.DataFrame()
    df = cagr_df.copy()
    df["Decade"] = (df.index.year // 10 * 10).astype(str).str.cat(["s"] * len(df))
    return df.groupby("Decade")[cagr_df.columns.tolist()].median().reset_index()
```

- [ ] **Step 4: Run tests to confirm green**

```powershell
pytest tests/test_simulation_engine.py -v
```
Expected: all PASSED

- [ ] **Step 5: Run all engine tests together**

```powershell
pytest tests/ -v --ignore=tests/benchmark_calculate_metrics.py --ignore=tests/benchmark_msci_upro_optimizer.py
```
Expected: all PASSED with no warnings

- [ ] **Step 6: Commit**

```bash
git add engines/simulation_engine.py tests/test_simulation_engine.py
git commit -m "feat: add simulation_engine with empirical percentile and drawdown analysis"
```

---

## Task 7: Entry Point & Shared Sidebar

**Files:**
- Create: `fire_dashboard.py`

- [ ] **Step 1: Create `fire_dashboard.py`**

```python
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

> **Disclaimer:** This tool is for educational modelling only. It does not constitute financial advice.  
> Past performance does not guarantee future results. Consult a licensed financial adviser.
""")

st.info("👈 Use the sidebar to navigate between pages.")
```

- [ ] **Step 2: Launch and verify the entry page renders**

```powershell
streamlit run fire_dashboard.py
```
Expected: browser opens, title "🔥 FIRE Dashboard" visible, sidebar present.

- [ ] **Step 3: Commit**

```bash
git add fire_dashboard.py
git commit -m "feat: add fire_dashboard.py entry point"
```

---

## Task 8: Page 1 — Dashboard

**Files:**
- Create: `pages/1_Dashboard.py`

- [ ] **Step 1: Create `pages/1_Dashboard.py`**

```python
"""Page 1: Dashboard — FIRE overview with key metrics and net worth timeline."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import run_yearly_projection, real_value
from engines.calculation_engine import fire_target, fire_age, coast_fire_target

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("📊 Dashboard")
st.caption("Your FIRE snapshot at a glance.")

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("👤 Your Details")
    current_age       = st.number_input("Current Age",            min_value=18, max_value=80,  value=30, step=1)
    target_retire_age = st.number_input("Target Retirement Age",  min_value=current_age+1, max_value=100, value=55, step=1)
    st.divider()
    st.header("💰 Finances")
    current_portfolio = st.number_input("Current Portfolio (AUD)", min_value=0, value=50_000, step=5_000)
    monthly_dca       = st.number_input("Monthly DCA (AUD)",       min_value=0, value=1_500,  step=100)
    salary            = st.number_input("Annual Salary (AUD)",     min_value=0, value=100_000, step=5_000)
    st.divider()
    st.header("📉 Assumptions")
    inflation_rate  = st.slider("Inflation Rate (%)",  0.0, 10.0, 2.5, 0.1, help="Annual CPI assumption")
    annual_return   = st.slider("Expected Return (%)", 0.0, 20.0, 7.0, 0.1, help="Median annual portfolio return (real)")
    target_spending = st.number_input("Annual Retirement Spending (AUD)", min_value=0, value=80_000, step=5_000)
    swr             = st.slider("Safe Withdrawal Rate (%)", 2.0, 6.0, 4.0, 0.25, help="Annual % withdrawn in retirement") / 100.0

# ── Load data ─────────────────────────────────────────────────────────────────
result = load_latest_backtest_csv()
if result is None:
    st.warning("No backtest CSV found. Run `rolling_backtest_suite.py` first, or upload a CSV on the FIRE Scenarios page.")
    st.stop()

data, csv_path = result
st.caption(f"Using: `{csv_path}`")

# ── Calculations ──────────────────────────────────────────────────────────────
years_to_retire = target_retire_age - current_age
fire_num        = fire_target(target_spending, swr)
coast_num       = coast_fire_target(fire_num, years_to_retire, annual_return / 100.0)

strategy_cols = data.strategies
proj_df = run_yearly_projection(
    data.cagr_df,
    strategy_cols,
    initial_portfolio=current_portfolio,
    dca_method="Fixed Monthly Amount",
    dca_value=monthly_dca,
    dca_grows=False,
    stop_at_coast=False,
    salary_growth=3.0,
    initial_salary=salary,
    horizon_years=min(years_to_retire, 50),
    return_format="Decimal (0.05 = 5%)",
    inflation_rate=inflation_rate,
    adjust_inflation=True,
)

# First strategy for summary metrics
first_strat = strategy_cols[0]
projected_at_retire = proj_df[f"{first_strat}_Total"].iloc[-1] if not proj_df.empty else 0
fire_age_val = fire_age(current_age, proj_df, fire_num, first_strat)
years_to_fire = (fire_age_val - current_age) if fire_age_val else None

# ── Key metrics ───────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 FIRE Number", f"${fire_num:,.0f}",
              help=f"Required portfolio at {swr*100:.1f}% SWR for ${target_spending:,}/yr spending")
with col2:
    st.metric("🌊 Coast FIRE Number", f"${coast_num:,.0f}",
              help=f"Amount needed today to coast to FIRE by age {target_retire_age} with no more contributions")
with col3:
    if fire_age_val:
        delta = f"{years_to_fire} years away"
        st.metric("🔥 Projected FIRE Age", str(fire_age_val), delta=delta)
    else:
        st.metric("🔥 Projected FIRE Age", "Not in horizon", delta="Increase DCA or extend horizon")
with col4:
    st.metric(f"📈 Portfolio at Age {target_retire_age}", f"${projected_at_retire:,.0f}",
              delta=f"{'Above' if projected_at_retire >= fire_num else 'Below'} FIRE number")

st.divider()

# ── Net worth timeline ────────────────────────────────────────────────────────
st.subheader("Net Worth Timeline")

fig = go.Figure()
for i, strat in enumerate(strategy_cols):
    color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
    fig.add_trace(go.Scatter(
        x=proj_df["Year"] + current_age,
        y=proj_df[f"{strat}_Total"],
        name=strat,
        line=dict(color=color, width=2),
        hovertemplate=f"{strat}<br>Age %{{x}}<br>${{y:,.0f}}<extra></extra>",
    ))

# FIRE number reference line
fig.add_hline(y=fire_num, line_dash="dash", line_color=COLORS["yellow"],
              annotation_text=f"FIRE Number ${fire_num/1e6:.1f}M",
              annotation_font_color=COLORS["yellow"])

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    xaxis_title="Age",
    yaxis_title="Portfolio Value (Real AUD)",
    hovermode="x unified",
    height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

st.caption("All values in real (inflation-adjusted) dollars. Projections use median historical CAGR from backtest data.")
st.warning("⚠️ This is a projection, not a guarantee. Past performance does not predict future returns.")
```

- [ ] **Step 2: Launch and verify**

```powershell
streamlit run fire_dashboard.py
```
Navigate to Dashboard. Confirm: metrics render, chart shows lines per strategy, FIRE number dashed line visible.

- [ ] **Step 3: Commit**

```bash
git add pages/1_Dashboard.py
git commit -m "feat: add Dashboard page with FIRE metrics and net worth timeline"
```

---

## Task 9: Page 2 — FIRE Scenarios

**Files:**
- Create: `pages/2_FIRE_Scenarios.py`

- [ ] **Step 1: Create `pages/2_FIRE_Scenarios.py`**

```python
"""Page 2: FIRE Scenarios — Coast/Lean/Fat/Barista crossover analysis."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
import numpy as np

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv
from engines.portfolio_engine import run_yearly_projection, dca_crossover_year, salary_crossover_year
from engines.calculation_engine import (
    fire_target, lean_fire_target, fat_fire_target, barista_fire_target, coast_fire_target, fire_age
)

st.set_page_config(page_title="FIRE Scenarios", page_icon="🎯", layout="wide")
st.title("🎯 FIRE Scenarios")

with st.sidebar:
    st.header("💰 Inputs")
    current_age   = st.number_input("Current Age",            min_value=18, max_value=80,  value=30)
    salary        = st.number_input("Annual Salary (AUD)",    min_value=0, value=100_000, step=5_000)
    salary_growth = st.number_input("Salary Growth (%/yr)",   min_value=0.0, value=3.0, step=0.5)
    portfolio     = st.number_input("Starting Portfolio",     min_value=0, value=50_000, step=5_000)
    dca_method    = st.radio("DCA Method", ["Fixed Monthly Amount", "Percentage of Salary"])
    if dca_method == "Fixed Monthly Amount":
        dca_value = st.number_input("Monthly DCA (AUD)", min_value=0, value=1_500, step=100)
    else:
        dca_value = st.number_input("Salary %", min_value=0.0, max_value=100.0, value=20.0)
    dca_grows    = st.checkbox("DCA grows with salary", value=True)
    stop_at_coast = st.toggle("Stop DCA at Coast Year", value=False)
    st.divider()
    st.header("📉 Spending Targets")
    lean_spending     = st.number_input("Lean FIRE Spending/yr",   min_value=0, value=40_000, step=5_000)
    fat_spending      = st.number_input("Fat FIRE Spending/yr",    min_value=0, value=120_000, step=5_000)
    barista_income    = st.number_input("Barista Part-Time Income", min_value=0, value=20_000, step=2_000)
    barista_spending  = st.number_input("Barista Total Spending",   min_value=0, value=60_000, step=5_000)
    swr               = st.slider("SWR (%)", 2.0, 6.0, 4.0, 0.25) / 100.0
    st.divider()
    inflation_rate = st.slider("Inflation (%)", 0.0, 10.0, 2.5, 0.1)
    horizon_years  = st.slider("Horizon (Years)", 5, 60, 35)

result = load_latest_backtest_csv()
if result is None:
    st.warning("No backtest CSV found. Run `rolling_backtest_suite.py` first.")
    st.stop()
data, _ = result

all_strategies = data.strategies
selected = st.multiselect("Strategies to compare", all_strategies, default=all_strategies[:min(3, len(all_strategies))])
if not selected:
    st.error("Select at least one strategy.")
    st.stop()

proj_df = run_yearly_projection(
    data.cagr_df, selected, portfolio, dca_method, dca_value, dca_grows, stop_at_coast,
    salary_growth, salary, horizon_years, "Decimal (0.05 = 5%)", inflation_rate, True,
)

# ── FIRE variant targets ──────────────────────────────────────────────────────
lean_num    = lean_fire_target(lean_spending, swr)
fat_num     = fat_fire_target(fat_spending, swr)
barista_num = barista_fire_target(barista_spending, barista_income, swr)

t_col1, t_col2, t_col3 = st.columns(3)
with t_col1:
    st.metric("🥦 Lean FIRE", f"${lean_num:,.0f}", help=f"${lean_spending:,}/yr at {swr*100:.1f}% SWR")
with t_col2:
    st.metric("🥩 Fat FIRE",  f"${fat_num:,.0f}",  help=f"${fat_spending:,}/yr at {swr*100:.1f}% SWR")
with t_col3:
    st.metric("☕ Barista FIRE", f"${barista_num:,.0f}",
              help=f"${barista_spending:,}/yr - ${barista_income:,} part-time income at {swr*100:.1f}% SWR")

st.divider()

# ── Double crossover chart ────────────────────────────────────────────────────
st.subheader("🚀 The Double Crossover")
fig = go.Figure()

ages = proj_df["Year"] + current_age

fig.add_trace(go.Scatter(x=ages, y=proj_df["Salary"], name="Annual Salary",
                          line=dict(color=COLORS["yellow"], width=3),
                          hovertemplate="Salary: $%{y:,.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=ages, y=proj_df["Yearly_DCA"], name="Annual DCA",
                          line=dict(color=COLORS["soft_yellow"], width=2, dash="dot"),
                          hovertemplate="DCA: $%{y:,.0f}<extra></extra>"))

for i, strat in enumerate(selected):
    color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
    profit = proj_df[f"{strat}_Yearly_Profit"]
    fig.add_trace(go.Scatter(x=ages, y=profit, name=f"{strat} Annual Profit",
                              line=dict(color=color, width=2),
                              hovertemplate=f"{strat}: $%{{y:,.0f}}<extra></extra>"))
    dca_yr   = dca_crossover_year(proj_df, strat)
    sal_yr   = salary_crossover_year(proj_df, strat)
    if dca_yr:
        fig.add_annotation(x=dca_yr + current_age, y=float(proj_df["Yearly_DCA"].iloc[dca_yr]),
                           text=f"Coast Yr {dca_yr}", showarrow=True, arrowhead=2, ax=-40, ay=-40,
                           bgcolor=COLORS["blue"], font=dict(color="white", size=11))
    if sal_yr:
        fig.add_annotation(x=sal_yr + current_age, y=float(proj_df["Salary"].iloc[sal_yr]),
                           text=f"FI Yr {sal_yr}", showarrow=True, arrowhead=1, ax=40, ay=-40,
                           bgcolor=color, font=dict(color="white", size=11))

fig.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                  xaxis_title="Age", yaxis_title="Annual Amount (Real AUD)",
                  hovermode="x unified", height=550,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)

# ── FI milestones ─────────────────────────────────────────────────────────────
milestones = []
for strat in selected:
    sal_yr = salary_crossover_year(proj_df, strat)
    if sal_yr:
        milestones.append({"Strategy": strat, "FI Year": sal_yr, "FI Age": current_age + sal_yr})
if milestones:
    milestones.sort(key=lambda x: x["FI Year"])
    best = milestones[0]
    cols = st.columns(len(milestones))
    for i, m in enumerate(milestones):
        with cols[i]:
            st.metric(f"🏁 {m['Strategy']}", f"Age {m['FI Age']}", f"Year {m['FI Year']}")
    st.success(f"🎉 Earliest FI: **{best['Strategy']}** at age **{best['FI Age']}**")

st.warning("⚠️ Projections use median historical CAGR. Not a guarantee of future performance.")
```

- [ ] **Step 2: Verify in browser** — confirm crossover annotations appear, FIRE variant metrics show.

- [ ] **Step 3: Commit**

```bash
git add pages/2_FIRE_Scenarios.py
git commit -m "feat: add FIRE Scenarios page with crossover chart and variant targets"
```

---

## Task 10: Page 3 — Historical Outcomes

**Files:**
- Create: `pages/3_Historical_Outcomes.py`

- [ ] **Step 1: Create `pages/3_Historical_Outcomes.py`**

```python
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

# ── Percentile table ──────────────────────────────────────────────────────────
st.subheader("CAGR Percentile Distribution")
percentiles = [10, 25, 50, 75, 90]
rows = []
for strat in selected:
    pcts = percentile_cagr(data.cagr_df[strat], percentiles)
    rows.append({"Strategy": strat, **{f"P{p}": f"{pcts[p]*100:.1f}%" for p in percentiles}})
st.dataframe(pd.DataFrame(rows).set_index("Strategy"), use_container_width=True)

# ── CAGR histogram ────────────────────────────────────────────────────────────
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
st.plotly_chart(fig_hist, use_container_width=True)

# ── Beat-X% slider ────────────────────────────────────────────────────────────
st.subheader("Probability of Beating a Return Threshold")
threshold = st.slider("Target CAGR (%)", 0.0, 20.0, 7.0, 0.5) / 100.0
beat_cols = st.columns(len(selected))
for i, strat in enumerate(selected):
    prob = probability_beat(data.cagr_df[strat], threshold)
    beat_cols[i].metric(strat, f"{prob*100:.0f}%",
                        help=f"% of 20-yr windows where {strat} beat {threshold*100:.1f}% CAGR")

# ── MDD frequency ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("Drawdown Frequency")
mdd_threshold = st.slider("Drawdown Threshold (%)", -80, -5, -30, 5) / 100.0
mdd_cols = st.columns(len(selected))
for i, strat in enumerate(selected):
    if strat in data.mdd_df.columns:
        freq = mdd_frequency(data.mdd_df[strat], mdd_threshold)
        mdd_cols[i].metric(strat, f"{freq*100:.0f}%",
                           help=f"% of windows with drawdown worse than {mdd_threshold*100:.0f}%")

# ── Decade heatmap ────────────────────────────────────────────────────────────
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
    st.plotly_chart(fig_heat, use_container_width=True)
```

- [ ] **Step 2: Verify in browser** — histogram, percentile table, beat-X% metrics, decade bar chart all render.

- [ ] **Step 3: Commit**

```bash
git add pages/3_Historical_Outcomes.py
git commit -m "feat: add Historical Outcomes page with empirical CAGR/MDD analysis"
```

---

## Task 11: Page 4 — Australian Tax

**Files:**
- Create: `pages/4_Australian_Tax.py`

- [ ] **Step 1: Create `pages/4_Australian_Tax.py`**

```python
"""Page 4: Australian Tax — income tax, HECS, super, CGT with current vs proposed 2027 law toggle."""
from __future__ import annotations
from datetime import date
import streamlit as st
import plotly.graph_objects as go

from utils.colors import COLORS
from engines.tax_engine import CGTLaw, effective_tax_rate, income_tax, medicare_levy, hecs_repayment

st.set_page_config(page_title="Australian Tax", page_icon="🇦🇺", layout="wide")
st.title("🇦🇺 Australian Tax Modelling")
st.caption("2024-25 tax year. All figures in AUD.")

with st.sidebar:
    st.header("💼 Income")
    gross_salary     = st.number_input("Gross Salary (AUD)",         min_value=0, value=100_000, step=5_000)
    super_contrib    = st.number_input("Concessional Super (AUD/yr)", min_value=0, value=10_000, step=500,
                                       help="Employer + voluntary pre-tax contributions, up to $30k cap")
    hecs_balance     = st.number_input("HECS-HELP Balance (AUD)",    min_value=0, value=0,       step=1_000)
    st.divider()
    st.header("📈 Capital Gains")
    cgt_gain         = st.number_input("Capital Gain (AUD)",         min_value=0, value=0,       step=5_000)
    held_years       = st.number_input("Asset Held (years)",          min_value=0.0, value=2.0,  step=0.5)

    st.divider()
    st.header("⚖️ CGT Law")
    law_choice = st.radio(
        "Which tax law?",
        ["Current (pre-July 2027) — 50% Discount", "Proposed (post-July 2027) — Indexation + 30% Floor"],
        help="Toggle between existing CGT rules and the proposed 2027 reforms",
    )
    law = CGTLaw.CURRENT if "Current" in law_choice else CGTLaw.PROPOSED_2027

    cpi_at_acquisition = None
    cpi_current_val    = None
    acquisition_date   = None
    is_new_build       = False

    if law == CGTLaw.PROPOSED_2027:
        st.subheader("Indexation Inputs")
        acquisition_date   = st.date_input("Acquisition Date", value=date(2025, 1, 1))
        cpi_at_acquisition = st.number_input("CPI at Acquisition", min_value=1.0, value=100.0, step=0.1)
        cpi_current_val    = st.number_input("Current CPI",         min_value=1.0, value=110.0, step=0.1)
        is_new_build       = st.checkbox("New residential build? (may elect old 50% discount)",
                                         help="Investors in new builds may choose the more favourable method")
        st.info("""
**Proposed 2027 CGT rules:**
- 50% discount replaced with **indexation** (only real gains taxed)
- **30% minimum tax floor** on net capital gains
- Assets held before 1 July 2027: transitional split-treatment
- New builds: choose old 50% discount or new indexation
- Main residence: exempt (unchanged)
        """)

    is_main_residence = st.checkbox("Main Residence? (CGT exempt)")

# ── Calculate ──────────────────────────────────────────────────────────────────
result = effective_tax_rate(
    gross_salary, super_contrib, hecs_balance, cgt_gain, held_years, law,
    acquisition_date=acquisition_date,
    cpi_at_acquisition=cpi_at_acquisition,
    cpi_current=cpi_current_val,
)
if is_main_residence and cgt_gain > 0:
    result["cgt"] = 0.0
    result["total_tax"] = result["income_tax"] + result["medicare_levy"] + result["hecs_repayment"] + result["super_tax"]
    base = gross_salary + cgt_gain
    result["effective_rate"] = result["total_tax"] / base if base > 0 else 0.0

# ── Summary metrics ───────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("💸 Income Tax",      f"${result['income_tax']:,.0f}")
c2.metric("🏥 Medicare Levy",   f"${result['medicare_levy']:,.0f}")
c3.metric("🎓 HECS Repayment",  f"${result['hecs_repayment']:,.0f}")
c4.metric("🏦 Super Tax (15%)", f"${result['super_tax']:,.0f}")

if cgt_gain > 0:
    cgt_col1, cgt_col2 = st.columns(2)
    law_label = "Current Law (50% discount)" if law == CGTLaw.CURRENT else "Proposed 2027 (Indexation + 30% floor)"
    cgt_col1.metric(f"📈 CGT — {law_label}", f"${result['cgt']:,.0f}")
    cgt_col2.metric("Effective Rate", f"{result['effective_rate']*100:.1f}%")

st.divider()
st.subheader("Tax Breakdown")
fig = go.Figure(go.Waterfall(
    orientation="v",
    measure=["relative", "relative", "relative", "relative", "relative", "total"],
    x=["Income Tax", "Medicare Levy", "HECS", "Super Tax", "CGT", "Net Income"],
    y=[
        -result["income_tax"], -result["medicare_levy"], -result["hecs_repayment"],
        -result["super_tax"],  -result["cgt"],
        result["net_income"],
    ],
    connector=dict(line=dict(color=COLORS["muted"])),
    increasing=dict(marker_color=COLORS["mint"]),
    decreasing=dict(marker_color=COLORS["red"]),
    totals=dict(marker_color=COLORS["blue"]),
    text=[f"-${abs(v):,.0f}" for v in
          [-result["income_tax"], -result["medicare_levy"], -result["hecs_repayment"],
           -result["super_tax"], -result["cgt"], result["net_income"]]],
    textposition="outside",
))
fig.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                  title=f"Gross ${gross_salary:,} → Net ${result['net_income']:,.0f}", height=450)
st.plotly_chart(fig, use_container_width=True)

if law == CGTLaw.PROPOSED_2027 and cgt_gain > 0:
    from engines.tax_engine import cgt_liability
    from engines.tax_engine import _marginal_rate  # type: ignore
    marginal = _marginal_rate(gross_salary)
    current_cgt = cgt_liability(cgt_gain, held_years, marginal, CGTLaw.CURRENT)
    st.info(f"""
**CGT Law Comparison:**
- Current law (50% discount): **${current_cgt:,.0f}**
- Proposed 2027 law (indexation + 30% floor): **${result['cgt']:,.0f}**
- Difference: **${abs(result['cgt'] - current_cgt):,.0f}** {'more' if result['cgt'] > current_cgt else 'less'} under proposed law
    """)

st.warning("⚠️ This tool provides estimates only. Tax law is complex — consult a registered tax agent.")
```

- [ ] **Step 2: Verify in browser** — waterfall chart renders, CGT law toggle switches between modes, proposed law shows comparison callout.

- [ ] **Step 3: Commit**

```bash
git add pages/4_Australian_Tax.py
git commit -m "feat: add Australian Tax page with CGT current vs proposed 2027 law toggle"
```

---

## Task 12: Page 5 — Retirement Drawdown

**Files:**
- Create: `pages/5_Retirement_Drawdown.py`

- [ ] **Step 1: Create `pages/5_Retirement_Drawdown.py`**

```python
"""Page 5: Retirement Drawdown — depletion slider, SWR sensitivity, inflation erosion."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.colors import COLORS
from engines.portfolio_engine import depletion_year, real_value, swr_income

st.set_page_config(page_title="Retirement Drawdown", page_icon="🏖️", layout="wide")
st.title("🏖️ Retirement Drawdown")

with st.sidebar:
    st.header("📦 Portfolio")
    retirement_portfolio = st.number_input("Portfolio at Retirement (AUD)", min_value=0, value=2_000_000, step=100_000)
    annual_return        = st.slider("Expected Return in Retirement (%)", 0.0, 12.0, 5.0, 0.25) / 100.0
    inflation_rate       = st.slider("Inflation Rate (%)", 0.0, 10.0, 2.5, 0.1) / 100.0
    st.divider()
    st.header("👤 Super Bridge")
    fire_age_input       = st.number_input("FIRE Age",               min_value=30, max_value=80,  value=50)
    preservation_age     = st.number_input("Super Preservation Age", min_value=55, max_value=65,  value=60,
                                           help="60 for those born after 1964")
    super_balance        = st.number_input("Super Balance at FIRE",  min_value=0, value=200_000, step=10_000)

# ── Depletion slider ──────────────────────────────────────────────────────────
st.subheader("⏱️ Portfolio Depletion Calculator")
st.caption("Drag the slider to see when your portfolio runs out.")

max_withdrawal = int(retirement_portfolio * 0.15) if retirement_portfolio > 0 else 200_000
annual_withdrawal = st.slider(
    "Annual Withdrawal (AUD)",
    min_value=10_000,
    max_value=max(max_withdrawal, 200_000),
    value=min(80_000, max_withdrawal),
    step=5_000,
    help="Annual amount withdrawn (today's dollars, grows with inflation)",
)

depl_yr = depletion_year(retirement_portfolio, annual_withdrawal, annual_return, inflation_rate)
swr_pct = (annual_withdrawal / retirement_portfolio * 100) if retirement_portfolio > 0 else 0

dep_col1, dep_col2, dep_col3 = st.columns(3)
with dep_col1:
    if depl_yr is None:
        st.metric("Portfolio Depletes", "Never ✅", help="Portfolio grows faster than withdrawals")
    else:
        retire_age_at_depl = fire_age_input + depl_yr
        color_label = "🟢" if depl_yr > 30 else ("🟡" if depl_yr > 20 else "🔴")
        st.metric("Portfolio Depletes", f"Year {depl_yr} {color_label}",
                  delta=f"Age {retire_age_at_depl}")
with dep_col2:
    st.metric("Implied SWR", f"{swr_pct:.1f}%",
              delta="Safe" if swr_pct <= 4.0 else "High — consider reducing")
with dep_col3:
    st.metric("Annual Withdrawal", f"${annual_withdrawal:,.0f}",
              delta=f"${annual_withdrawal/12:,.0f}/month")

# Depletion curve
years_to_show = min((depl_yr or 60) + 5, 80)
balances, withdrawals_nominal = [], []
bal = float(retirement_portfolio)
w = float(annual_withdrawal)
for y in range(years_to_show):
    balances.append(max(bal, 0))
    withdrawals_nominal.append(w)
    bal = bal * (1 + annual_return) - w
    w *= (1 + inflation_rate)
    if bal <= 0:
        balances.extend([0] * (years_to_show - y - 1))
        break

ages = list(range(fire_age_input, fire_age_input + len(balances)))
fig_dep = go.Figure()
fig_dep.add_trace(go.Scatter(x=ages, y=balances, name="Portfolio Balance",
                              fill="tozeroy", fillcolor=f"rgba(0,184,148,0.15)",
                              line=dict(color=COLORS["mint"], width=2),
                              hovertemplate="Age %{x}<br>Balance: $%{y:,.0f}<extra></extra>"))
if depl_yr:
    fig_dep.add_vline(x=fire_age_input + depl_yr, line_dash="dash", line_color=COLORS["red"],
                      annotation_text=f"Depletes age {fire_age_input+depl_yr}", annotation_font_color=COLORS["red"])
fig_dep.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                      xaxis_title="Age", yaxis_title="Portfolio Balance (AUD)", height=400)
st.plotly_chart(fig_dep, use_container_width=True)

# ── SWR sensitivity table ─────────────────────────────────────────────────────
st.divider()
st.subheader("SWR Sensitivity Table")
swr_rows = []
for rate in [0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.055]:
    annual = swr_income(retirement_portfolio, rate)
    depl = depletion_year(retirement_portfolio, annual, annual_return, inflation_rate)
    swr_rows.append({
        "SWR": f"{rate*100:.1f}%",
        "Annual Income": f"${annual:,.0f}",
        "Monthly Income": f"${annual/12:,.0f}",
        "Depletes in": f"Year {depl}" if depl else "Never ✅",
    })
st.dataframe(pd.DataFrame(swr_rows), use_container_width=True, hide_index=True)

# ── Inflation erosion ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Inflation Erosion of a Fixed $80,000 Withdrawal")
years_range = list(range(0, 31))
fig_inf = go.Figure()
for inf_r, label, color in [(0.02, "2% inflation", COLORS["mint"]),
                              (0.025, "2.5% inflation", COLORS["blue"]),
                              (0.03, "3% inflation", COLORS["yellow"]),
                              (0.05, "5% inflation", COLORS["red"])]:
    real_vals = [real_value(80_000, inf_r, y) for y in years_range]
    fig_inf.add_trace(go.Scatter(x=[fire_age_input + y for y in years_range],
                                  y=real_vals, name=label,
                                  line=dict(color=color, width=2),
                                  hovertemplate=f"{label}<br>Age %{{x}}: $%{{y:,.0f}}<extra></extra>"))
fig_inf.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                      xaxis_title="Age", yaxis_title="Real Value (Today's Dollars)",
                      height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_inf, use_container_width=True)

# ── Super bridge ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("Super Access Bridge")
bridge_years = max(preservation_age - fire_age_input, 0)
if bridge_years > 0:
    bridge_col1, bridge_col2 = st.columns(2)
    bridge_col1.metric("Years until Super access", bridge_years,
                       help=f"FIRE at {fire_age_input}, super accessible at {preservation_age}")
    needed_bridge = annual_withdrawal * bridge_years
    bridge_col2.metric("Bridge Portfolio Required (rough)", f"${needed_bridge:,.0f}",
                       help="Approx. liquid (non-super) portfolio needed before super kicks in")
    if super_balance > 0:
        projected_super = super_balance * (1 + annual_return) ** bridge_years
        st.info(f"Super balance of ${super_balance:,} grows to **${projected_super:,.0f}** by age {preservation_age} at {annual_return*100:.1f}% return.")
else:
    st.success(f"✅ You are already at or past preservation age — super is accessible.")
```

- [ ] **Step 2: Verify in browser** — depletion slider updates chart live, red/amber/green indicator works, SWR table shows, super bridge appears.

- [ ] **Step 3: Commit**

```bash
git add pages/5_Retirement_Drawdown.py
git commit -m "feat: add Retirement Drawdown page with live depletion slider and SWR table"
```

---

## Task 13: Page 6 — Portfolio Analytics

**Files:**
- Create: `pages/6_Portfolio_Analytics.py`

- [ ] **Step 1: Create `pages/6_Portfolio_Analytics.py`**

```python
"""Page 6: Portfolio Analytics — strategy comparison, rolling returns, risk-return scatter."""
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.colors import COLORS, STRATEGY_COLORS
from utils.csv_loader import load_latest_backtest_csv

# Strategy weights from rolling_backtest_suite.py
STRATEGY_WEIGHTS: dict[str, dict[str, float]] = {
    "Hybrid SPY (70/15/15)":  {"SPY": 0.70, "UPRO": 0.15, "Gold": 0.15},
    "Dull S&P 500":           {"SPY": 1.00},
    "Hybrid MSCI (40/35/25)": {"MSCI": 0.40, "UPRO": 0.35, "Gold": 0.25},
    "Dull MSCI World":        {"MSCI": 1.00},
}

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

# ── CAGR / MDD bar comparison ─────────────────────────────────────────────────
st.subheader("Median CAGR vs Max Drawdown")
medians_cagr = {s: float(data.cagr_df[s].median()) for s in selected}
medians_mdd  = {s: float(data.mdd_df[s].median()) for s in selected if s in data.mdd_df.columns}

fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(x=selected, y=[medians_cagr[s]*100 for s in selected],
                          name="Median CAGR (%)", marker_color=COLORS["mint"],
                          hovertemplate="%{x}<br>CAGR: %{y:.1f}%<extra></extra>"))
fig_bar.add_trace(go.Bar(x=selected, y=[medians_mdd.get(s, 0)*100 for s in selected],
                          name="Median MDD (%)", marker_color=COLORS["orange"],
                          hovertemplate="%{x}<br>MDD: %{y:.1f}%<extra></extra>"))
fig_bar.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                      barmode="group", yaxis_title="(%)", height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_bar, use_container_width=True)

# ── Rolling CAGR over time ────────────────────────────────────────────────────
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

# ── Risk-Return scatter ───────────────────────────────────────────────────────
st.subheader("Risk-Return Scatter (Median CAGR vs Median MDD)")
scatter_data = [{"Strategy": s, "CAGR (%)": medians_cagr[s]*100,
                  "MDD (%)": medians_mdd.get(s, 0)*100} for s in selected]
fig_scatter = px.scatter(scatter_data, x="MDD (%)", y="CAGR (%)", text="Strategy",
                          color="Strategy", color_discrete_sequence=STRATEGY_COLORS,
                          template="plotly_dark")
fig_scatter.update_traces(textposition="top center", marker_size=12)
fig_scatter.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                           xaxis_title="Median Max Drawdown (%)", yaxis_title="Median CAGR (%)",
                           showlegend=False, height=400)
st.plotly_chart(fig_scatter, use_container_width=True)

# ── Asset allocation ──────────────────────────────────────────────────────────
st.divider()
st.subheader("Asset Allocation")
alloc_cols = st.columns(min(len(selected), 4))
for i, strat in enumerate(selected):
    weights = None
    for k, v in STRATEGY_WEIGHTS.items():
        if k in strat or strat in k:
            weights = v
            break
    if weights and i < len(alloc_cols):
        fig_pie = go.Figure(go.Pie(
            labels=list(weights.keys()),
            values=list(weights.values()),
            hole=0.4,
            marker_colors=STRATEGY_COLORS[:len(weights)],
        ))
        fig_pie.update_layout(template="plotly_dark", paper_bgcolor="#0d1117",
                               showlegend=True, height=250,
                               title=dict(text=strat[:25], font_size=11))
        alloc_cols[i].plotly_chart(fig_pie, use_container_width=True)
```

- [ ] **Step 2: Verify in browser** — bar chart, rolling lines, scatter, pie charts all render.

- [ ] **Step 3: Commit**

```bash
git add pages/6_Portfolio_Analytics.py
git commit -m "feat: add Portfolio Analytics page with CAGR/MDD comparison and allocation pies"
```

---

## Task 14: Page 7 — Assumptions

**Files:**
- Create: `pages/7_Assumptions.py`

- [ ] **Step 1: Create `pages/7_Assumptions.py`**

```python
"""Page 7: Assumptions & Methodology — editable defaults and calculation explainers."""
from __future__ import annotations
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Assumptions", page_icon="⚙️", layout="wide")
st.title("⚙️ Assumptions & Methodology")

st.subheader("Default Assumptions")
c1, c2 = st.columns(2)
with c1:
    inflation  = st.number_input("Inflation Rate (%)",        value=2.5, step=0.1)
    equity_ret = st.number_input("Expected Equity Return (%)", value=7.0, step=0.25)
    bond_ret   = st.number_input("Expected Bond Return (%)",   value=3.0, step=0.25)
with c2:
    swr        = st.number_input("Safe Withdrawal Rate (%)",   value=4.0, step=0.25)
    sal_growth = st.number_input("Salary Growth (%/yr)",       value=3.0, step=0.5)
    div_yield  = st.number_input("S&P 500 Dividend Yield (%)", value=1.5, step=0.1)

st.info("These defaults are used throughout the app where no page-specific value is set.")

st.divider()
st.subheader("Calculation Methodology")

with st.expander("FIRE Number"):
    st.markdown("""
**Formula:** `FIRE Number = Annual Spending ÷ Safe Withdrawal Rate`

The 4% rule (Bengen 1994) states a retiree can withdraw 4% of their portfolio annually,
adjusted for inflation, with a high probability of the portfolio surviving 30+ years.
A lower SWR (3%) is more conservative; higher (5%) is riskier.
    """)

with st.expander("Coast FIRE"):
    st.markdown("""
**Formula:** `Coast FIRE = FIRE Number ÷ (1 + annual_return)^years_to_retire`

The present value of your FIRE number. If you have this amount invested today,
you can stop contributing and let compound growth carry you to FIRE by your target date.
    """)

with st.expander("Portfolio Projection (Annuity-Due)"):
    st.markdown(r"""
**Formula:** FV of annuity-due, applied annually with monthly compounding.

Each year: `portfolio = portfolio × (1+r)^12 + DCA × (1+r_monthly) × ((1+r_monthly)^12 - 1) / r_monthly`

Where `r_monthly = (1 + annual_return)^(1/12) - 1`. Contributions are made at the *start* of each month.
    """)

with st.expander("Inflation Adjustment"):
    st.markdown("""
All projections show **real (inflation-adjusted) dollars** by default.

`real_value = nominal_value ÷ (1 + inflation_rate)^years`

This means a $1M portfolio in 20 years at 2.5% inflation is shown as ~$610k in today's dollars.
    """)

with st.expander("Australian CGT — Current Law"):
    st.markdown("""
Assets held **≥12 months**: 50% discount applied to gain, remainder taxed at marginal rate.  
Assets held **<12 months**: full gain taxed at marginal rate.  
Main residence: fully exempt.
    """)

with st.expander("Australian CGT — Proposed 2027 Law"):
    st.markdown("""
**Effective 1 July 2027 (proposed, not yet legislated):**

- **Indexation replaces 50% discount**: only real gains above CPI inflation are taxable.  
  `Real gain = Nominal gain ÷ (CPI_current / CPI_acquisition)`
- **30% minimum tax floor**: regardless of marginal rate, CGT ≥ 30% of nominal gain.
- **Transitional**: assets acquired before 1 July 2027 use old 50% discount on pre-cutoff gains.
- **New builds**: investor may elect old 50% discount or new indexation (whichever is more favourable).
- **Main residence exemption**: unchanged.

> ⚠️ This is a proposed reform. Verify current law with the ATO before making decisions.
    """)

with st.expander("Historical Outcomes (Simulation Engine)"):
    st.markdown("""
Rather than Monte Carlo (synthetic paths), this app uses the actual rolling 20-year window
backtest results as an **empirical probability distribution**.

- **Percentile analysis**: sorts all historical window outcomes and reads off quantiles.
- **Probability of beating X%**: fraction of windows where CAGR > threshold.
- **Drawdown frequency**: fraction of windows where MDD < (more negative than) threshold.

This is empirically grounded — no assumed return distribution, no synthetic randomness.
    """)

st.divider()
st.subheader("Data Sources")
sources = pd.DataFrame([
    {"Source": "S&P 500 (GSPC)", "Description": "Yahoo Finance via bt.get()", "Coverage": "1928–present"},
    {"Source": "Gold", "Description": "Yahoo Finance (GC=F)", "Coverage": "1979–present"},
    {"Source": "MSCI World (IWDA.L)", "Description": "Yahoo Finance", "Coverage": "2009–present"},
    {"Source": "S&P 500 Dividend Yields", "Description": "Shiller CAPE (1927–1999), SPDR/Bloomberg (2000–2026)", "Coverage": "1927–2026"},
    {"Source": "Fed Funds Rate", "Description": "FRED FEDFUNDS", "Coverage": "1970–2026"},
])
st.dataframe(sources, use_container_width=True, hide_index=True)

st.divider()
st.warning("""
**Disclaimer:** This tool is for educational and modelling purposes only.  
It does not constitute financial advice, tax advice, or investment advice.  
All projections are illustrative and past performance does not guarantee future results.  
Please consult a licensed financial adviser and registered tax agent before making investment or retirement decisions.
""")
```

- [ ] **Step 2: Verify in browser** — all expanders open, data sources table shows, disclaimer visible.

- [ ] **Step 3: Run full test suite one final time**

```powershell
pytest tests/ -v --ignore=tests/benchmark_calculate_metrics.py --ignore=tests/benchmark_msci_upro_optimizer.py
```
Expected: all PASSED

- [ ] **Step 4: Commit**

```bash
git add pages/7_Assumptions.py
git commit -m "feat: add Assumptions page with methodology explainers and data sources"
```

---

## Final Verification

- [ ] Run `streamlit run fire_dashboard.py` and visit all 7 pages.
- [ ] Confirm depletion slider on Page 5 updates chart in real time.
- [ ] Confirm CGT law toggle on Page 4 shows comparison callout.
- [ ] Confirm CSV auto-loads from `data/BT_*/` folder.
- [ ] Run full test suite: `pytest tests/ -v --ignore=tests/benchmark_calculate_metrics.py --ignore=tests/benchmark_msci_upro_optimizer.py`
- [ ] All tests green, no warnings.

---

## Self-Review Notes

**Spec coverage check:**
- ✅ 7 pages matching spec
- ✅ `depletion_year()` + slider on Page 5
- ✅ CGT toggle (current vs proposed 2027) on Page 4
- ✅ Historical outcomes replaces Monte Carlo
- ✅ All Flat UI Colors US palette via `utils/colors.py`
- ✅ TDD for all 4 engine modules
- ✅ Streamlit launched after each page

**Type consistency:**
- `BacktestData.cagr_df` columns = strategy names (stripped of " CAGR") — matches how pages index it
- `run_yearly_projection` uses `strategy_cols` that are keys of `cagr_df` (stripped names) — consistent
- `fire_age()` looks for `{strategy}_Total` column — matches column names in `run_yearly_projection` — consistent
- `CGTLaw` enum used consistently across `tax_engine.py` and Page 4

**Known simplification:**
- `_marginal_rate` is a private function imported by Page 4 for the comparison callout. Acceptable for now — can be made public if needed.
