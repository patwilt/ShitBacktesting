"""Kids & Family Cost Engine.

Computes year-by-year direct financial costs of raising children based on
Australian averages sourced from child.md assumptions. Also models income loss
from parental leave and the ongoing housing premium for a bigger home.

All costs are in today's (real) dollars.

Key phases per child:
  Age 0    — birth year: setup + parental leave income loss
  Age 0–4  — childcare phase: highest cashflow pressure
  Age 5–11 — primary school: moderate ongoing costs
  Age 12–17 — high school: teen costs (food, tech, activities, transport)

References: child.md assumptions for average Australian household.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Per-phase cost benchmarks (real AUD, today's dollars) ────────────────────

SETUP_COST_PER_CHILD = 7_500          # cot, pram, car seat, baby gear

# Age 0–4 childcare phase
CHILDCARE_EXTRAS_PER_YEAR = 4_500     # food, clothing, health on top of childcare

# Age 5–11 primary school phase
PRIMARY_SCHOOL_COSTS = {
    "public":    2_000,   # uniforms, excursions, P&C levies
    "catholic":  8_000,   # Catholic/independent primary
    "private":   None,    # user-specified (pf_kids_private_school_annual)
}
PRIMARY_GENERAL_PER_YEAR = 3_500      # food, clothing, activities

# Age 12–17 high school phase
HIGH_SCHOOL_COSTS = {
    "public":    3_500,   # higher fees, subject levies, device
    "catholic":  12_000,
    "private":   None,    # user-specified (pf_kids_private_highschool_annual)
}
HIGH_SCHOOL_GENERAL_PER_YEAR = 6_000  # food (teens eat!), tech, activities, transport


@dataclass
class KidsCostSeries:
    """Year-by-year cost breakdown for all children combined."""

    # Each list index = year from now (0 = this year, 1 = next, ...)
    setup: list[float] = field(default_factory=list)
    income_loss: list[float] = field(default_factory=list)
    childcare: list[float] = field(default_factory=list)
    school: list[float] = field(default_factory=list)
    general: list[float] = field(default_factory=list)
    housing: list[float] = field(default_factory=list)
    total: list[float] = field(default_factory=list)

    def total_lifetime(self) -> float:
        return sum(self.total)

    def peak_annual(self) -> float:
        return max(self.total) if self.total else 0.0

    def peak_year(self) -> int:
        if not self.total:
            return 0
        return self.total.index(max(self.total))

    def as_dict(self) -> dict[int, float]:
        """Return {year: total_cost} for years where cost > 0."""
        return {yr: c for yr, c in enumerate(self.total) if c > 0}


def compute_kids_costs(
    num_kids: int,
    birth_yrs_from_now: list[int],      # years from now each child is born
    schooling: str,                      # "public" | "catholic" | "private"
    private_school_annual: float,        # per child/yr, primary (if private)
    private_highschool_annual: float,    # per child/yr, high school (if private)
    childcare_annual_per_child: float,   # per child/yr ages 0–4 after CCS subsidy
    setup_cost_per_child: float,         # one-off at birth
    gross_income: float,                 # primary earner income (for leave loss)
    partner_gross_income: float,         # partner income (for leave loss)
    leave_weeks: int,                    # your parental leave weeks
    partner_leave_weeks: int,            # partner parental leave weeks
    leave_income_pct: float,             # % of salary received during leave (0–100)
    bigger_house_monthly_extra: float,   # extra housing cost/month for bigger home
    partner_career_break_years: int = 0, # full years partner stays off work AFTER parental leave
    horizon: int = 30,                   # years to project
) -> KidsCostSeries:
    """
    Compute the year-by-year financial cost of raising children.

    Returns a KidsCostSeries with lists indexed by year-from-now.
    All values are in real (today's) dollars.

    partner_career_break_years: years BEYOND parental leave where the partner earns nothing.
      - 0 (default): partner returns to work once parental leave ends.
      - 2: partner stays off for 2 additional full years — full annual income lost each year.
    The income loss for those years is added on top of the birth-year parental leave cost.
    """
    series = KidsCostSeries(
        setup=[0.0] * horizon,
        income_loss=[0.0] * horizon,
        childcare=[0.0] * horizon,
        school=[0.0] * horizon,
        general=[0.0] * horizon,
        housing=[0.0] * horizon,
        total=[0.0] * horizon,
    )

    leave_fraction = leave_income_pct / 100.0
    your_weekly_income    = gross_income / 52.0
    partner_weekly_income = partner_gross_income / 52.0

    your_leave_loss    = your_weekly_income    * leave_weeks    * (1.0 - leave_fraction)
    partner_leave_loss = partner_weekly_income * partner_leave_weeks * (1.0 - leave_fraction)

    # Primary school cost per child
    if schooling == "private":
        primary_school_cost = float(private_school_annual)
        highschool_cost     = float(private_highschool_annual)
    else:
        primary_school_cost = float(PRIMARY_SCHOOL_COSTS.get(schooling, 2_000))
        highschool_cost     = float(HIGH_SCHOOL_COSTS.get(schooling, 3_500))

    birth_yrs = birth_yrs_from_now[:num_kids]

    # ── Partner career break: applied once, starting from the FIRST child's birth ──
    # Years 1 → partner_career_break_years (after first birth) = full annual income lost.
    if partner_career_break_years > 0 and birth_yrs and partner_gross_income > 0:
        first_birth = min(b for b in birth_yrs if b < horizon)
        for cb_yr in range(1, partner_career_break_years + 1):
            yr = first_birth + cb_yr
            if yr < horizon:
                series.income_loss[yr] += partner_gross_income

    for birth_yr in birth_yrs:
        if birth_yr < 0 or birth_yr >= horizon:
            continue

        for age in range(18):
            yr = birth_yr + age
            if yr >= horizon:
                break

            # ── Setup (birth year only) ───────────────────────────────────────
            if age == 0:
                series.setup[yr]       += setup_cost_per_child
                series.income_loss[yr] += your_leave_loss + partner_leave_loss

            # ── Childcare (age 0–4) ───────────────────────────────────────────
            if age < 5:
                series.childcare[yr] += childcare_annual_per_child
                series.general[yr]   += CHILDCARE_EXTRAS_PER_YEAR

            # ── Primary school (age 5–11) ─────────────────────────────────────
            elif age < 12:
                series.school[yr]   += primary_school_cost
                series.general[yr]  += PRIMARY_GENERAL_PER_YEAR

            # ── High school (age 12–17) ───────────────────────────────────────
            else:
                series.school[yr]   += highschool_cost
                series.general[yr]  += HIGH_SCHOOL_GENERAL_PER_YEAR

    # ── Housing premium: extra monthly cost from first birth to last child age 18 ──
    if bigger_house_monthly_extra > 0 and birth_yrs:
        housing_start = min(birth_yrs)
        housing_end   = max(b + 18 for b in birth_yrs if b < horizon)
        housing_end   = min(housing_end, horizon)
        annual_housing_extra = bigger_house_monthly_extra * 12.0
        for yr in range(housing_start, housing_end):
            if yr < horizon:
                series.housing[yr] += annual_housing_extra

    # ── Compute totals ─────────────────────────────────────────────────────────
    for yr in range(horizon):
        series.total[yr] = (
            series.setup[yr]
            + series.income_loss[yr]
            + series.childcare[yr]
            + series.school[yr]
            + series.general[yr]
            + series.housing[yr]
        )

    return series


def kids_cost_label(schooling: str) -> str:
    labels = {"public": "Public School", "catholic": "Catholic/Independent", "private": "Private School"}
    return labels.get(schooling, schooling.title())


def phase_label(birth_yr: int, age: int) -> str:
    """Human-readable phase for a given child age."""
    if age == 0:
        return "Birth & Setup"
    elif age < 5:
        return "Childcare (0–4)"
    elif age < 12:
        return "Primary School (5–11)"
    else:
        return "High School (12–17)"
