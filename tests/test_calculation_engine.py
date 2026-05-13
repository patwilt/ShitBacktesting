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
    # Target 1M in 20 years at 7% return → PV = 1,000,000 / (1.07^20)
    result = coast_fire_target(1_000_000, years_to_retire=20, annual_return=0.07)
    assert abs(result - 1_000_000 / (1.07 ** 20)) < 1.0


def test_coast_fire_target_zero_years():
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
        "strat_Total": [100_000 * (1.26 ** y) for y in range(11)],
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
