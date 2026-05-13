"""
Australian tax engine (2024-25).
CGT supports two law versions:
  CGTLaw.CURRENT        — 50% discount for assets held >12 months
  CGTLaw.PROPOSED_2027  — Indexation + 30% minimum tax floor (effective 1 July 2027)
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional


class CGTLaw(Enum):
    CURRENT = "current"
    PROPOSED_2027 = "proposed_2027"


# ── 2024-25 income tax brackets (post Stage 3 cuts) ──────────────────────────
_BRACKETS: list[tuple[float, float, float]] = [
    (0,        18_200,  0.00),
    (18_200,   45_000,  0.16),
    (45_000,  135_000,  0.30),
    (135_000, 190_000,  0.37),
    (190_000, float("inf"), 0.45),
]

# Precompute cumulative tax at each bracket lower bound
_BRACKET_BASE: list[float] = []
_b = 0.0
for _lo, _hi, _rate in _BRACKETS:
    _BRACKET_BASE.append(_b)
    if _hi != float("inf"):
        _b += (_hi - _lo) * _rate


# ── HECS-HELP 2024-25 repayment rates ────────────────────────────────────────
_HECS_THRESHOLDS: list[tuple[float, float, float]] = [
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

_MEDICARE_LOW_INCOME_THRESHOLD = 26_000


def income_tax(taxable_income: float) -> float:
    """2024-25 Australian income tax (excl. Medicare levy)."""
    if taxable_income <= 0:
        return 0.0
    for i, (lo, hi, rate) in enumerate(_BRACKETS):
        if taxable_income <= hi:
            return _BRACKET_BASE[i] + (taxable_income - lo) * rate
    return 0.0


def medicare_levy(taxable_income: float) -> float:
    """Medicare levy: 2% of taxable income. Zero below low-income threshold."""
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
    """Tax on concessional super contributions: 15% flat."""
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
    cost_base: Optional[float] = None,
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
    if is_new_build:
        current_tax = cgt_liability(gain, held_years, marginal_rate, CGTLaw.CURRENT)
        proposed_tax = _proposed_2027_cgt(gain, marginal_rate, cpi_at_acquisition, cpi_current, cost_base)
        return min(current_tax, proposed_tax)

    return _proposed_2027_cgt(gain, marginal_rate, cpi_at_acquisition, cpi_current, cost_base)


def _proposed_2027_cgt(
    gain: float,
    marginal_rate_val: float,
    cpi_at_acquisition: Optional[float],
    cpi_current: Optional[float],
    cost_base: Optional[float] = None,
) -> float:
    """
    Indexation method: only real gain is taxed at marginal rate.
    30% minimum tax floor applies on the nominal gain.
    """
    MIN_RATE = 0.30

    if cpi_at_acquisition and cpi_current and cpi_at_acquisition > 0:
        cpi_ratio = cpi_current / cpi_at_acquisition
        if cost_base is not None and cost_base > 0:
            # Correct AUS indexation: inflate cost base, tax only the real gain
            indexed_cost_base = cost_base * cpi_ratio
            proceeds = cost_base + gain
            real_gain = max(proceeds - indexed_cost_base, 0.0)
        else:
            # Fallback when cost base unknown: deflate entire gain (conservative approximation)
            real_gain = max(gain / cpi_ratio, 0.0)
    else:
        real_gain = gain

    tax_at_marginal = real_gain * marginal_rate_val
    min_tax = gain * MIN_RATE  # 30% floor on nominal gain

    return max(tax_at_marginal, min_tax)


def marginal_rate(income: float) -> float:
    """Marginal income tax rate for a given income level."""
    for lo, hi, rate in reversed(_BRACKETS):
        if income > lo:
            return rate
    return 0.0


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
    marginal = marginal_rate(gross_income)
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


# ── Low Income Tax Offset (LITO) 2024-25 ──────────────────────────────────────
def lito(taxable_income: float) -> float:
    """
    Low Income Tax Offset — reduces net tax payable.
    2024-25 schedule:
      $0 – $37,500:     $700 flat
      $37,500 – $45,000: reduces by 5c per $1 over $37,500
      $45,000 – $66,667: reduces by 1.5c per $1 over $45,000
      > $66,667:         $0
    """
    if taxable_income <= 37_500:
        return 700.0
    if taxable_income <= 45_000:
        return max(700.0 - (taxable_income - 37_500) * 0.05, 0.0)
    if taxable_income <= 66_667:
        return max(325.0 - (taxable_income - 45_000) * 0.015, 0.0)
    return 0.0


def net_income_tax(taxable_income: float) -> float:
    """Income tax after applying LITO. Never negative."""
    return max(income_tax(taxable_income) - lito(taxable_income), 0.0)


def gross_withdrawal_for_net_spend(
    net_spend: float,
    hecs_balance: float = 0.0,
    max_iter: int = 60,
) -> float:
    """
    Binary search: find the gross portfolio withdrawal that yields exactly
    net_spend after income tax (net of LITO), Medicare levy, and HECS repayment.
    Assumes all drawdown is treated as ordinary income (conservative).
    """
    if net_spend <= 0:
        return 0.0
    lo, hi = net_spend, net_spend * 2.5
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        take_home = mid - net_income_tax(mid) - medicare_levy(mid) - hecs_repayment(mid, hecs_balance)
        if abs(take_home - net_spend) < 0.50:
            return mid
        if take_home < net_spend:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0
