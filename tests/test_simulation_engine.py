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
    # Values strictly > 0.07: 0.08, 0.09, 0.10 → 3/6 = 50%
    result = probability_beat(s, threshold=0.07)
    assert result == pytest.approx(0.5)


def test_probability_beat_none():
    s = _series([0.03, 0.04, 0.05])
    assert probability_beat(s, threshold=0.10) == pytest.approx(0.0)


def test_probability_beat_all():
    s = _series([0.08, 0.09, 0.10])
    assert probability_beat(s, threshold=0.05) == pytest.approx(1.0)


def test_mdd_frequency_threshold():
    # MDD values are negative; worse than -0.30 means < -0.30
    s = _series([-0.10, -0.20, -0.35, -0.40, -0.50])
    # 3 out of 5 are < -0.30: -0.35, -0.40, -0.50
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
