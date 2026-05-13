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
