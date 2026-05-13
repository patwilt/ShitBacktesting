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
    lito,
    net_income_tax,
    gross_withdrawal_for_net_spend,
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
    # $200,000: in top bracket (190k+)
    # $4,288 + $27,000 + $20,350 + $4,500 = $56,138
    assert income_tax(200_000) == pytest.approx(56_138.0, abs=5.0)


# --- medicare_levy ---

def test_medicare_levy_zero_income():
    assert medicare_levy(0) == pytest.approx(0.0)


def test_medicare_levy_standard():
    assert medicare_levy(80_000) == pytest.approx(1_600.0)


# --- hecs_repayment ---

def test_hecs_repayment_below_threshold():
    assert hecs_repayment(50_000, hecs_balance=10_000) == pytest.approx(0.0)


def test_hecs_repayment_above_threshold():
    # $60,000 income → 1% = $600/yr
    result = hecs_repayment(60_000, hecs_balance=10_000)
    assert result == pytest.approx(600.0, abs=10.0)


def test_hecs_repayment_capped_at_balance():
    result = hecs_repayment(200_000, hecs_balance=500)
    assert result <= 500.0


# --- super_concessional_tax ---

def test_super_concessional_tax_standard():
    assert super_concessional_tax(10_000) == pytest.approx(1_500.0)


def test_super_concessional_tax_zero():
    assert super_concessional_tax(0) == pytest.approx(0.0)


# --- cgt_liability (current law) ---

def test_cgt_current_law_held_under_12_months_no_discount():
    result = cgt_liability(50_000, held_years=0.5, marginal_rate=0.37, law=CGTLaw.CURRENT)
    assert result == pytest.approx(18_500.0, abs=1.0)


def test_cgt_current_law_held_over_12_months_50_percent_discount():
    result = cgt_liability(50_000, held_years=2.0, marginal_rate=0.37, law=CGTLaw.CURRENT)
    assert result == pytest.approx(9_250.0, abs=1.0)


def test_cgt_main_residence_exempt():
    result = cgt_liability(500_000, held_years=5.0, marginal_rate=0.45, law=CGTLaw.CURRENT, is_main_residence=True)
    assert result == pytest.approx(0.0)


# --- cgt_liability (proposed 2027 law) ---

def test_cgt_proposed_law_minimum_30_percent_floor_applies():
    # Low marginal rate (16%), large gain → 30% floor kicks in
    result = cgt_liability(100_000, held_years=2.0, marginal_rate=0.16, law=CGTLaw.PROPOSED_2027,
                           acquisition_date=date(2028, 1, 1), cpi_at_acquisition=100.0, cpi_current=105.0)
    # 30% floor on nominal gain → minimum tax = $30,000
    assert result >= 30_000.0


def test_cgt_proposed_law_main_residence_still_exempt():
    result = cgt_liability(500_000, held_years=5.0, marginal_rate=0.37, law=CGTLaw.PROPOSED_2027,
                           acquisition_date=date(2028, 1, 1), cpi_at_acquisition=100.0, cpi_current=115.0,
                           is_main_residence=True)
    assert result == pytest.approx(0.0)


def test_cgt_proposed_law_is_a_float():
    result = cgt_liability(10_000, held_years=2.0, marginal_rate=0.37, law=CGTLaw.PROPOSED_2027,
                           acquisition_date=date(2028, 1, 1), cpi_at_acquisition=100.0, cpi_current=110.0)
    assert isinstance(result, float)


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


def test_effective_tax_rate_zero_income():
    result = effective_tax_rate(0, super_contributions=0, hecs_balance=0,
                                cgt_gain=0, held_years=0, law=CGTLaw.CURRENT)
    assert result["total_tax"] == pytest.approx(0.0)
    assert result["effective_rate"] == pytest.approx(0.0)


# --- lito ---

def test_lito_low_income_full_offset():
    assert lito(30_000) == pytest.approx(700.0)


def test_lito_phase_out_first_band():
    # $40,000: $700 - (40,000 - 37,500) * 0.05 = $700 - $125 = $575
    assert lito(40_000) == pytest.approx(575.0, abs=1.0)


def test_lito_phase_out_second_band():
    # $55,000: $325 - (55,000 - 45,000) * 0.015 = $325 - $150 = $175
    assert lito(55_000) == pytest.approx(175.0, abs=1.0)


def test_lito_zero_above_threshold():
    assert lito(70_000) == pytest.approx(0.0)


def test_net_income_tax_zero_at_low_income():
    # Below tax threshold, income_tax is 0, LITO is 700 → clamped to 0
    assert net_income_tax(15_000) == pytest.approx(0.0)


def test_net_income_tax_lower_than_gross_tax():
    # At $50k, income tax is $6,288 but LITO reduces it
    assert net_income_tax(50_000) < income_tax(50_000)


def test_gross_withdrawal_roundtrip():
    # If target net is $60k, solve for gross and verify net is $60k
    from engines.tax_engine import gross_withdrawal_for_net_spend, net_income_tax, medicare_levy, hecs_repayment
    target = 60_000.0
    gross = gross_withdrawal_for_net_spend(target)
    actual_net = gross - net_income_tax(gross) - medicare_levy(gross) - hecs_repayment(gross, 0)
    assert abs(actual_net - target) < 1.0


def test_gross_withdrawal_always_gte_net():
    gross = gross_withdrawal_for_net_spend(80_000)
    assert gross >= 80_000
