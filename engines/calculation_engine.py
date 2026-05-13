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
    Amount needed invested today so compound growth reaches target_portfolio
    by retirement with no additional contributions.
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


def preservation_age(birth_year: int) -> int:
    """
    Australian superannuation preservation age by birth year.
    From 1 July 1964 onwards the preservation age is 60.
    Earlier birth years have lower preservation ages (55–59).
    Source: ATO — Super preservation age.
    """
    if birth_year < 1960:
        return 55
    if birth_year < 1961:
        return 56
    if birth_year < 1962:
        return 57
    if birth_year < 1963:
        return 58
    if birth_year < 1964:
        return 59
    return 60
