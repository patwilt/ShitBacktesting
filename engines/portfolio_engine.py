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
    Simulate annual withdrawals in real (inflation-adjusted) terms.
    Converts the nominal annual_return to a real return so the balance and
    withdrawal are both in today's AUD throughout — no need to grow the
    withdrawal by inflation year-on-year.
    Returns the year the portfolio hits zero, or None if it survives max_years.
    """
    balance = float(portfolio)
    real_return = (1.0 + annual_return) / (1.0 + inflation_rate) - 1.0
    for year in range(1, max_years + 1):
        balance = balance * (1.0 + real_return) - annual_withdrawal
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
