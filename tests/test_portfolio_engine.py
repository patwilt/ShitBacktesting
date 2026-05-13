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
    # $20k withdrawal at 4% return is exactly break-even, so no_inf may be None.
    # Inflation causes the real withdrawal to grow, eventually depleting the portfolio.
    assert with_inf is not None
    assert no_inf is None or with_inf < no_inf


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


# --- run_yearly_projection smoke test ---

def test_run_yearly_projection_returns_dataframe_with_correct_shape():
    import pandas as pd
    cagr_data = pd.DataFrame({"My Strategy": [0.07, 0.08, 0.09, 0.10]})
    result = run_yearly_projection(
        df=cagr_data,
        strategy_cols=["My Strategy"],
        initial_portfolio=100_000,
        dca_method="Fixed Monthly Amount",
        dca_value=1_000,
        dca_grows=False,
        stop_at_coast=False,
        salary_growth=3.0,
        initial_salary=80_000,
        horizon_years=5,
        return_format="Decimal (0.05 = 5%)",
        inflation_rate=2.5,
        adjust_inflation=True,
    )
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 6  # year 0 + 5 years
    assert "My Strategy_Total" in result.columns
    assert "Salary" in result.columns


def test_run_yearly_projection_portfolio_grows_with_positive_return():
    import pandas as pd
    cagr_data = pd.DataFrame({"Strat": [0.10, 0.10, 0.10]})
    result = run_yearly_projection(
        df=cagr_data, strategy_cols=["Strat"], initial_portfolio=100_000,
        dca_method="Fixed Monthly Amount", dca_value=0, dca_grows=False,
        stop_at_coast=False, salary_growth=0.0, initial_salary=80_000,
        horizon_years=10, return_format="Decimal (0.05 = 5%)",
        inflation_rate=0.0, adjust_inflation=False,
    )
    # With 10% return and no DCA/inflation, portfolio should grow
    assert result["Strat_Total"].iloc[-1] > result["Strat_Total"].iloc[0]
