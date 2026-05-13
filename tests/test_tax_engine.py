# tests/test_tax_engine.py
from __future__ import annotations
from datetime import date
import pytest
from engines.tax_engine import (
    CGTLaw,
    income_tax,
    medicare_levy,
    medicare_levy_surcharge,
    division_293_tax,
    hecs_repayment,
    super_concessional_tax,
    cgt_liability,
    effective_tax_rate,
    lito,
    net_income_tax,
    gross_withdrawal_for_net_spend,
)


# ── income_tax (2024-25 brackets post Stage 3 cuts) ───────────────────────────

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


# ── medicare_levy (2024-25 with phase-in / shading zone) ──────────────────────

def test_medicare_levy_zero_income():
    assert medicare_levy(0) == pytest.approx(0.0)


def test_medicare_levy_below_threshold():
    assert medicare_levy(25_999) == pytest.approx(0.0)


def test_medicare_levy_at_threshold_zero():
    # Exactly at $26,000: phase-in = 10% × ($26,000 − $26,000) = $0
    assert medicare_levy(26_000) == pytest.approx(0.0)


def test_medicare_levy_phase_in_zone():
    # $28,000: shading zone → 10% × ($28,000 − $26,000) = $200
    assert medicare_levy(28_000) == pytest.approx(200.0)


def test_medicare_levy_shade_out_boundary():
    # $32,500 exactly — both formulas give $650; code uses full 2%
    assert medicare_levy(32_500) == pytest.approx(650.0)


def test_medicare_levy_above_shade_out():
    # $80,000: full 2% = $1,600
    assert medicare_levy(80_000) == pytest.approx(1_600.0)


def test_medicare_levy_no_cliff_at_threshold():
    # Marginal levy at threshold should be ≤ $0.10 per $1 of extra income (shade rate)
    levy_at_26000 = medicare_levy(26_000)
    levy_at_26001 = medicare_levy(26_001)
    assert levy_at_26001 - levy_at_26000 <= 0.11   # 10c per $1 in shading zone


def test_medicare_levy_standard():
    # Pre-existing test preserved: $80k → $1,600
    assert medicare_levy(80_000) == pytest.approx(1_600.0)


# ── medicare_levy_surcharge ────────────────────────────────────────────────────

def test_mls_below_threshold():
    # Below $93,000 → 0%
    assert medicare_levy_surcharge(90_000) == pytest.approx(0.0)


def test_mls_at_threshold():
    # $93,000 → still 0% (≤ threshold)
    assert medicare_levy_surcharge(93_000) == pytest.approx(0.0)


def test_mls_first_tier():
    # $100,000 with no cover → 1.0% = $1,000
    assert medicare_levy_surcharge(100_000) == pytest.approx(1_000.0)


def test_mls_second_tier():
    # $120,000 with no cover → 1.25% = $1,500
    assert medicare_levy_surcharge(120_000) == pytest.approx(1_500.0)


def test_mls_third_tier():
    # $150,000 with no cover → 1.5% = $2,250
    assert medicare_levy_surcharge(150_000) == pytest.approx(2_250.0)


def test_mls_private_cover_exempt():
    # $300,000 but has private hospital cover → $0
    assert medicare_levy_surcharge(300_000, has_private_hospital_cover=True) == pytest.approx(0.0)


def test_mls_default_no_cover():
    # Default: no private cover → positive MLS at high income
    assert medicare_levy_surcharge(100_000) > 0.0


# ── division_293_tax ──────────────────────────────────────────────────────────

def test_division_293_below_threshold():
    # $200k income + $15k contributions = $215k < $250k → no div 293
    assert division_293_tax(200_000, 15_000) == pytest.approx(0.0)


def test_division_293_at_threshold():
    # $240k + $10k = $250k exactly → no div 293
    assert division_293_tax(240_000, 10_000) == pytest.approx(0.0)


def test_division_293_above_threshold():
    # $240k income + $27,500 contributions = $267,500 > $250k
    # taxable = min(27,500, 267,500 − 250,000) = min(27,500, 17,500) = 17,500
    # tax = 17,500 × 15% = $2,625
    assert division_293_tax(240_000, 27_500) == pytest.approx(2_625.0)


def test_division_293_capped_at_contributions():
    # $260k income + $10k contributions = $270k > $250k
    # taxable = min(10,000, 270,000 − 250,000) = min(10,000, 20,000) = 10,000
    # tax = 10,000 × 15% = $1,500
    assert division_293_tax(260_000, 10_000) == pytest.approx(1_500.0)


def test_division_293_zero_contributions():
    assert division_293_tax(300_000, 0) == pytest.approx(0.0)


# ── hecs_repayment ────────────────────────────────────────────────────────────

def test_hecs_repayment_below_threshold():
    assert hecs_repayment(50_000, hecs_balance=10_000) == pytest.approx(0.0)


def test_hecs_repayment_above_threshold():
    # $60,000 income → 1% = $600/yr
    result = hecs_repayment(60_000, hecs_balance=10_000)
    assert result == pytest.approx(600.0, abs=10.0)


def test_hecs_repayment_capped_at_balance():
    result = hecs_repayment(200_000, hecs_balance=500)
    assert result <= 500.0


# ── super_concessional_tax ────────────────────────────────────────────────────

def test_super_concessional_tax_standard():
    assert super_concessional_tax(10_000) == pytest.approx(1_500.0)


def test_super_concessional_tax_zero():
    assert super_concessional_tax(0) == pytest.approx(0.0)


# ── cgt_liability (current law) ───────────────────────────────────────────────

def test_cgt_current_law_held_under_12_months_no_discount():
    result = cgt_liability(50_000, held_years=0.5, marginal_rate=0.37, law=CGTLaw.CURRENT)
    assert result == pytest.approx(18_500.0, abs=1.0)


def test_cgt_current_law_held_over_12_months_50_percent_discount():
    result = cgt_liability(50_000, held_years=2.0, marginal_rate=0.37, law=CGTLaw.CURRENT)
    assert result == pytest.approx(9_250.0, abs=1.0)


def test_cgt_main_residence_exempt():
    result = cgt_liability(500_000, held_years=5.0, marginal_rate=0.45, law=CGTLaw.CURRENT,
                            is_main_residence=True)
    assert result == pytest.approx(0.0)


# ── cgt_liability (proposed 2027 law) ────────────────────────────────────────

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


# ── effective_tax_rate ────────────────────────────────────────────────────────

def test_effective_tax_rate_returns_dict_with_required_keys():
    result = effective_tax_rate(100_000, super_contributions=10_000, hecs_balance=0,
                                cgt_gain=0, held_years=0, law=CGTLaw.CURRENT)
    for key in ("income_tax", "medicare_levy", "medicare_levy_surcharge", "hecs_repayment",
                "super_tax", "division_293_tax", "cgt", "total_tax", "effective_rate", "net_income"):
        assert key in result, f"Missing key: {key}"


def test_effective_tax_rate_zero_income():
    result = effective_tax_rate(0, super_contributions=0, hecs_balance=0,
                                cgt_gain=0, held_years=0, law=CGTLaw.CURRENT)
    assert result["total_tax"] == pytest.approx(0.0)
    assert result["effective_rate"] == pytest.approx(0.0)


def test_effective_tax_rate_applies_lito():
    # At $40,000 income, LITO reduces net income tax below gross income tax
    result = effective_tax_rate(40_000, 0, 0, 0, 0, CGTLaw.CURRENT)
    assert result["income_tax"] < income_tax(40_000)


def test_effective_tax_rate_lito_not_negative():
    # Very low income: LITO should prevent negative income tax
    result = effective_tax_rate(15_000, 0, 0, 0, 0, CGTLaw.CURRENT)
    assert result["income_tax"] >= 0.0


def test_effective_tax_rate_cgt_uses_stacked_marginal_rate():
    # Two scenarios with same gain but different ordinary income levels.
    # At higher ordinary income, the CGT portion is taxed at a higher marginal rate.
    result_lower = effective_tax_rate(130_000, 0, 0, 50_000, 2.0, CGTLaw.CURRENT)
    result_higher = effective_tax_rate(190_000, 0, 0, 50_000, 2.0, CGTLaw.CURRENT)
    # $190k has higher stacked marginal rate (45%) than $130k (37%) → higher CGT
    assert result_higher["cgt"] > result_lower["cgt"]


def test_effective_tax_rate_main_residence_exempts_cgt():
    result = effective_tax_rate(120_000, 0, 0, 500_000, 5.0, CGTLaw.CURRENT,
                                is_main_residence=True)
    assert result["cgt"] == pytest.approx(0.0)


def test_effective_tax_rate_includes_mls_without_cover():
    # $120k income without private hospital cover → MLS of 1.25% = $1,500
    result_no_cover  = effective_tax_rate(120_000, 0, 0, 0, 0, CGTLaw.CURRENT,
                                          has_private_hospital_cover=False)
    result_with_cover = effective_tax_rate(120_000, 0, 0, 0, 0, CGTLaw.CURRENT,
                                           has_private_hospital_cover=True)
    assert result_no_cover["medicare_levy_surcharge"] == pytest.approx(1_500.0)
    assert result_with_cover["medicare_levy_surcharge"] == pytest.approx(0.0)
    assert result_no_cover["total_tax"] > result_with_cover["total_tax"]


def test_effective_tax_rate_division_293_triggers():
    # $240k salary + $27,500 contributions → Division 293 kicks in
    result = effective_tax_rate(240_000, super_contributions=27_500, hecs_balance=0,
                                cgt_gain=0, held_years=0, law=CGTLaw.CURRENT)
    assert result["division_293_tax"] > 0.0


def test_effective_tax_rate_division_293_absent_below_threshold():
    result = effective_tax_rate(100_000, super_contributions=10_000, hecs_balance=0,
                                cgt_gain=0, held_years=0, law=CGTLaw.CURRENT)
    assert result["division_293_tax"] == pytest.approx(0.0)


# ── lito ──────────────────────────────────────────────────────────────────────

def test_lito_low_income_full_offset():
    assert lito(30_000) == pytest.approx(700.0)


def test_lito_phase_out_first_band():
    # $40,000: $700 − (40,000 − 37,500) × 0.05 = $700 − $125 = $575
    assert lito(40_000) == pytest.approx(575.0, abs=1.0)


def test_lito_phase_out_second_band():
    # $55,000: $325 − (55,000 − 45,000) × 0.015 = $325 − $150 = $175
    assert lito(55_000) == pytest.approx(175.0, abs=1.0)


def test_lito_zero_above_threshold():
    assert lito(70_000) == pytest.approx(0.0)


def test_net_income_tax_zero_at_low_income():
    # Below tax threshold, income_tax is 0, LITO is 700 → clamped to 0
    assert net_income_tax(15_000) == pytest.approx(0.0)


def test_net_income_tax_lower_than_gross_tax():
    # At $50k, income tax is $6,288 but LITO reduces it
    assert net_income_tax(50_000) < income_tax(50_000)


# ── gross_withdrawal_for_net_spend ────────────────────────────────────────────

def test_gross_withdrawal_roundtrip():
    # Solve for gross then verify net is $60k (backward-compatible, existing_income=0)
    target = 60_000.0
    gross = gross_withdrawal_for_net_spend(target)
    actual_net = gross - net_income_tax(gross) - medicare_levy(gross) - hecs_repayment(gross, 0)
    assert abs(actual_net - target) < 1.0


def test_gross_withdrawal_always_gte_net():
    gross = gross_withdrawal_for_net_spend(80_000)
    assert gross >= 80_000


def test_gross_withdrawal_zero():
    assert gross_withdrawal_for_net_spend(0) == pytest.approx(0.0)


def test_gross_withdrawal_with_existing_income_is_higher():
    # With existing part-time income, the withdrawal is taxed at a higher marginal rate
    # and so requires a higher gross to deliver the same net
    gross_standalone = gross_withdrawal_for_net_spend(40_000, existing_income=0)
    gross_with_income = gross_withdrawal_for_net_spend(40_000, existing_income=20_000)
    assert gross_with_income > gross_standalone


def test_gross_withdrawal_existing_income_roundtrip():
    # Verify that the net take-home on the MARGINAL withdrawal equals the target
    target   = 40_000.0
    existing = 20_000.0
    gross = gross_withdrawal_for_net_spend(target, existing_income=existing)
    combined     = existing + gross
    tax_combined = net_income_tax(combined) + medicare_levy(combined) + hecs_repayment(combined, 0)
    tax_existing = net_income_tax(existing) + medicare_levy(existing) + hecs_repayment(existing, 0)
    actual_net   = gross - (tax_combined - tax_existing)
    assert abs(actual_net - target) < 1.0


def test_gross_withdrawal_existing_income_high_bracket():
    # With large existing income, withdrawal is in 45% bracket
    # Net should still converge to target
    target   = 30_000.0
    existing = 200_000.0
    gross = gross_withdrawal_for_net_spend(target, existing_income=existing)
    combined     = existing + gross
    tax_combined = net_income_tax(combined) + medicare_levy(combined) + hecs_repayment(combined, 0)
    tax_existing = net_income_tax(existing) + medicare_levy(existing) + hecs_repayment(existing, 0)
    actual_net   = gross - (tax_combined - tax_existing)
    assert abs(actual_net - target) < 1.0
