"""
Test suite for the Dodgey Investing backtesting codebase.

Covers:
  - calculate_metrics: edge cases, mathematical correctness, vectorised parity
  - BacktestExporter: folder creation, CSV export, race-condition safety
  - mock_data_generator: date correctness, reproducibility
  - strategy_evaluator helpers: parse_date, calculate_scenario_fv
"""
from __future__ import annotations

import os
import tempfile
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backtest_export import BacktestExporter
from rolling_backtest_suite import (
    _FED_FUNDS_ANNUAL,
    _calculate_metrics_loop,
    calculate_metrics,
    load_and_prep_upro,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(
    n: int = 252 * 5,
    seed: int = 42,
    cols: list[str] | None = None,
) -> pd.DataFrame:
    """Generate deterministic price data indexed by business dates."""
    if cols is None:
        cols = ["spy", "upro", "gold"]
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-01", periods=n)
    rets = rng.normal(0.0003, 0.01, (n, len(cols)))
    prices = np.cumprod(1.0 + rets, axis=0) * 100.0
    return pd.DataFrame(prices, index=dates, columns=cols)


WEIGHTS = {"spy": 0.70, "upro": 0.15, "gold": 0.15}


# ---------------------------------------------------------------------------
# calculate_metrics — non-rebalanced
# ---------------------------------------------------------------------------

class TestCalculateMetricsNonRebalanced:
    def test_flat_price_zero_cagr_and_mdd(self):
        """A flat price series should produce CAGR = 0 and MDD = 0."""
        dates = pd.bdate_range("2000-01-01", periods=252 * 5)
        prices = pd.DataFrame({"spy": np.full(len(dates), 100.0)}, index=dates)
        cagr, mdd = calculate_metrics(prices)
        assert abs(cagr) < 1e-9
        assert abs(mdd) < 1e-9

    def test_monotone_rising_no_drawdown(self):
        """A strictly increasing price series must have MDD = 0."""
        dates = pd.bdate_range("2000-01-01", periods=252 * 3)
        prices = pd.DataFrame(
            {"spy": np.linspace(100.0, 300.0, len(dates))}, index=dates
        )
        _, mdd = calculate_metrics(prices)
        assert mdd == pytest.approx(0.0, abs=1e-9)

    def test_halving_price_mdd_near_minus_half(self):
        """A series that falls to half its peak should show MDD ≈ -50%."""
        dates = pd.bdate_range("2000-01-01", periods=252 * 2)
        n = len(dates)
        vals = np.concatenate(
            [np.linspace(100.0, 200.0, n // 2), np.linspace(200.0, 100.0, n - n // 2)]
        )
        prices = pd.DataFrame({"spy": vals}, index=dates)
        _, mdd = calculate_metrics(prices)
        assert mdd == pytest.approx(-0.5, abs=0.01)

    def test_insufficient_data_returns_zeros(self):
        """A single-row slice should return (0, 0) without crashing."""
        dates = pd.bdate_range("2000-01-01", periods=1)
        prices = pd.DataFrame({"spy": [100.0]}, index=dates)
        cagr, mdd = calculate_metrics(prices)
        assert cagr == 0.0
        assert mdd == 0.0

    def test_known_doubling_cagr(self):
        """
        A price that doubles over 252 business days should yield CAGR > 0.
        252 business days ≈ 352 calendar days (< 365.25), so CAGR > 100%.
        We verify that the calculation correctly annualises above 1.0 (100%).
        """
        dates = pd.bdate_range("2000-01-01", periods=252)
        prices = pd.DataFrame({"spy": np.linspace(100.0, 200.0, 252)}, index=dates)
        cagr, _ = calculate_metrics(prices)
        n_calendar_days = (dates[-1] - dates[0]).days
        expected = 2.0 ** (365.25 / n_calendar_days) - 1.0
        assert cagr == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# calculate_metrics — rebalanced (vectorised vs reference loop)
# ---------------------------------------------------------------------------

class TestCalculateMetricsRebalanced:
    def test_raises_without_weights(self):
        df = _make_price_df(n=252)
        with pytest.raises(ValueError, match="weights"):
            calculate_metrics(df, is_rebalanced=True, weights=None)

    def test_portfolio_value_stays_positive(self):
        """Portfolio value must remain > 0 regardless of market moves."""
        df = _make_price_df(n=252 * 30, seed=7)
        cagr, mdd = calculate_metrics(df, True, WEIGHTS)
        assert cagr > -1.0
        assert -1.0 <= mdd <= 0.0

    @pytest.mark.parametrize("n_days", [63, 252, 252 * 5, 252 * 10])
    def test_vectorised_matches_loop_reference(self, n_days: int):
        """
        The vectorised O(n/63) implementation must agree with the explicit
        O(n) loop to floating-point precision for a range of window lengths.
        """
        df = _make_price_df(n=n_days, seed=99)
        cagr_v, mdd_v = calculate_metrics(df, True, WEIGHTS)
        cagr_r, mdd_r = _calculate_metrics_loop(df, WEIGHTS)
        assert cagr_v == pytest.approx(cagr_r, abs=1e-10), (
            f"CAGR mismatch at n={n_days}: vec={cagr_v:.8f}, loop={cagr_r:.8f}"
        )
        assert mdd_v == pytest.approx(mdd_r, abs=1e-10), (
            f"MDD mismatch at n={n_days}: vec={mdd_v:.8f}, loop={mdd_r:.8f}"
        )

    def test_100pct_weight_single_asset_equals_non_rebalanced(self):
        """
        A rebalanced portfolio 100% in one asset should give the same CAGR
        as the non-rebalanced single-asset calculation.
        """
        df = _make_price_df(n=252 * 3, seed=1)
        cagr_rb, _ = calculate_metrics(df, True, {"spy": 1.0, "upro": 0.0, "gold": 0.0})
        cagr_nr, _ = calculate_metrics(df[["spy"]])
        assert cagr_rb == pytest.approx(cagr_nr, abs=1e-8)

    def test_weights_must_be_respected_at_rebalance(self):
        """
        If two assets are perfectly identical, a mixed portfolio must have
        the same CAGR as either asset alone (no free lunch from rebalancing).
        """
        dates = pd.bdate_range("2000-01-01", periods=252 * 5)
        rng = np.random.default_rng(0)
        rets = rng.normal(0.0004, 0.012, len(dates))
        base = np.cumprod(1.0 + rets) * 100.0
        df = pd.DataFrame({"a": base, "b": base}, index=dates)
        cagr_mixed, _ = calculate_metrics(df, True, {"a": 0.5, "b": 0.5})
        cagr_single, _ = calculate_metrics(df[["a"]])
        assert cagr_mixed == pytest.approx(cagr_single, abs=1e-8)


# ---------------------------------------------------------------------------
# BacktestExporter
# ---------------------------------------------------------------------------

class TestBacktestExporter:
    def test_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                exp = BacktestExporter(10, "2000-01-01", "2010-01-01")
                assert exp.folder_name is not None
                assert os.path.isdir(exp.folder_name)
            finally:
                os.chdir(orig_cwd)

    def test_export_dataframe_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                exp = BacktestExporter(5, "2015-01-01", "2020-01-01")
                df = pd.DataFrame({"CAGR": [0.07, 0.09], "MDD": [-0.15, -0.20]})
                exp.export_dataframe(df, "test_output.csv")
                csv_path = os.path.join(exp.folder_name, "test_output.csv")
                assert os.path.isfile(csv_path)
                loaded = pd.read_csv(csv_path)
                assert len(loaded) == 2
            finally:
                os.chdir(orig_cwd)

    def test_no_save_skips_folder_creation(self):
        """save_outputs=False must not touch the filesystem."""
        exp = BacktestExporter(10, "2000-01-01", "2010-01-01", save_outputs=False)
        assert exp.folder_name is None

    def test_idempotent_folder_creation(self):
        """Calling _create_folder twice must not raise (exist_ok=True)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                exp = BacktestExporter(10, "2000-01-01", "2010-01-01")
                exp._create_folder()  # second call — must not raise
            finally:
                os.chdir(orig_cwd)

    def test_folder_name_contains_years_and_dates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                exp = BacktestExporter(25, "1987-01-01", "2026-01-01")
                assert "25y" in exp.folder_name
                assert "1987-01-01" in exp.folder_name
            finally:
                os.chdir(orig_cwd)


# ---------------------------------------------------------------------------
# mock_data_generator
# ---------------------------------------------------------------------------

class TestMockDataGenerator:
    def test_output_row_count(self):
        from mock_data_generator import generate_mock_data
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "mock.csv")
            df = generate_mock_data(filename=path, periods=120)
            assert len(df) == 120

    def test_date_column_is_month_start(self):
        """All generated dates must fall on the 1st of the month."""
        from mock_data_generator import generate_mock_data
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "mock.csv")
            df = generate_mock_data(filename=path, periods=24)
            assert (pd.to_datetime(df["Date"]).dt.day == 1).all()

    def test_dates_monotonically_increasing(self):
        from mock_data_generator import generate_mock_data
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "mock.csv")
            df = generate_mock_data(filename=path, periods=36)
            assert pd.to_datetime(df["Date"]).is_monotonic_increasing

    def test_no_missing_months(self):
        """36 months of data should span exactly 36 unique months."""
        from mock_data_generator import generate_mock_data
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "mock.csv")
            df = generate_mock_data(filename=path, periods=36)
            dates = pd.to_datetime(df["Date"])
            month_keys = dates.dt.to_period("M")
            assert len(month_keys.unique()) == 36

    def test_reproducible_with_same_seed(self):
        from mock_data_generator import generate_mock_data
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.csv")
            p2 = os.path.join(tmpdir, "b.csv")
            df1 = generate_mock_data(filename=p1, periods=50, seed=7)
            df2 = generate_mock_data(filename=p2, periods=50, seed=7)
            pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_produce_different_data(self):
        from mock_data_generator import generate_mock_data
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.csv")
            p2 = os.path.join(tmpdir, "b.csv")
            df1 = generate_mock_data(filename=p1, periods=50, seed=1)
            df2 = generate_mock_data(filename=p2, periods=50, seed=2)
            assert not df1["Aggressive Growth"].equals(df2["Aggressive Growth"])


# ---------------------------------------------------------------------------
# load_and_prep_upro — dynamic financing cost
# ---------------------------------------------------------------------------

class TestUproFinancingCost:
    """
    Verify that the UPRO proxy correctly penalises high-rate regimes and
    rewards ZIRP periods relative to a flat-cost assumption.
    """

    def _make_flat_gspc(self, year_start: int, n_days: int = 252) -> dict:
        """
        Synthetic GSPC with a constant +0.04% daily return (≈ 10% CAGR).
        Using a flat return isolates the cost model from return noise.
        """
        dates = pd.bdate_range(f"{year_start}-01-02", periods=n_days)
        daily_r = 0.0004
        prices = (1.0 + daily_r) ** np.arange(n_days) * 100.0
        return {"gspc": pd.Series(prices, index=dates)}

    def test_high_rate_year_more_expensive_than_zirp(self):
        """
        UPRO CAGR in a high-rate year (2023, ~5.3% fed funds) should be
        materially lower than in a ZIRP year (2013, ~0.1%) given identical
        underlying returns.
        """
        data_zirp = self._make_flat_gspc(2013)
        data_high = self._make_flat_gspc(2023)

        upro_zirp = load_and_prep_upro(data_zirp)
        upro_high = load_and_prep_upro(data_high)

        # Both start at ~100; compare end values
        assert upro_zirp.iloc[-1] > upro_high.iloc[-1], (
            f"ZIRP end={upro_zirp.iloc[-1]:.4f}, high-rate end={upro_high.iloc[-1]:.4f}"
        )

    def test_cost_differential_matches_rate_spread(self):
        """
        The difference in final UPRO value between ZIRP and high-rate should
        be consistent with the difference in (L-1)×r_f cost over the period.
        """
        n = 252
        data_zirp = self._make_flat_gspc(2013, n)
        data_high = self._make_flat_gspc(2023, n)

        rf_zirp = _FED_FUNDS_ANNUAL[2013]
        rf_high = _FED_FUNDS_ANNUAL[2023]
        spread = 0.003
        L = 3.0
        expected_extra_annual_cost = (L - 1) * (rf_high - rf_zirp)

        upro_zirp = load_and_prep_upro(data_zirp)
        upro_high = load_and_prep_upro(data_high)

        # Approximate ratio of end values over 1 year
        ratio = upro_high.iloc[-1] / upro_zirp.iloc[-1]
        approx_extra_drag = 1.0 - ratio
        # The drag should be in the right ballpark (within 50% of expected)
        assert abs(approx_extra_drag - expected_extra_annual_cost) < expected_extra_annual_cost * 0.5

    def test_upro_prices_always_positive(self):
        """UPRO proxy must never go negative or zero."""
        for year in [1990, 2009, 2020, 2023]:
            data = self._make_flat_gspc(year, 252)
            upro = load_and_prep_upro(data)
            assert (upro > 0).all(), f"Negative UPRO price in year {year}"

    def test_lookup_table_coverage(self):
        """Every year from 1987 (START_DATE) to 2026 must be in the table."""
        for year in range(1987, 2027):
            assert year in _FED_FUNDS_ANNUAL, f"Year {year} missing from _FED_FUNDS_ANNUAL"


# ---------------------------------------------------------------------------
# strategy_evaluator helpers (non-Streamlit functions)
# ---------------------------------------------------------------------------

class TestParseDate:
    def setup_method(self):
        from strategy_evaluator import parse_date
        self.parse_date = parse_date

    def test_valid_timestamp_string(self):
        result = self.parse_date("2020-06-15")
        assert result is not None
        assert result.year == 2020

    def test_numeric_year_string(self):
        result = self.parse_date("2015")
        assert result is not None
        assert result.year == 2015

    def test_invalid_returns_none(self):
        result = self.parse_date("not_a_date")
        assert result is None

    def test_none_input_returns_none(self):
        result = self.parse_date(None)
        assert result is None


class TestCalculateScenarioFv:
    def setup_method(self):
        from strategy_evaluator import calculate_scenario_fv
        self.fv = calculate_scenario_fv

    def test_zero_return_is_pure_sum(self):
        """With 0% return, portfolio = principal + all contributions."""
        principal = 10_000.0
        monthly = 500.0
        years = 10
        total, contributed = self.fv(principal, monthly, 0.0, years, 0.0)
        expected_contributions = monthly * 12 * years
        assert contributed == pytest.approx(principal + expected_contributions, rel=1e-6)

    def test_positive_return_exceeds_contributions(self):
        """With positive return the portfolio must exceed total contributed."""
        total, contributed = self.fv(10_000, 500, 3.0, 20, 0.07)
        assert total > contributed

    def test_higher_return_gives_higher_value(self):
        """Holding everything else equal, a higher return → higher FV."""
        total_low, _ = self.fv(10_000, 500, 0.0, 20, 0.05)
        total_high, _ = self.fv(10_000, 500, 0.0, 20, 0.10)
        assert total_high > total_low

    def test_growing_dca_exceeds_flat_dca(self):
        """A DCA that grows with salary should produce a higher FV."""
        total_flat, _ = self.fv(10_000, 500, 0.0, 20, 0.07)
        total_grow, _ = self.fv(10_000, 500, 5.0, 20, 0.07)
        assert total_grow > total_flat
