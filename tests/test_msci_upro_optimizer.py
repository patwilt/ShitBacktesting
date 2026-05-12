"""
TDD test suite for msci_upro_optimizer.py
==========================================
Design principle: tests are INDEPENDENT of the module-level SWEEP_ASSETS setting.
Every call to build_allocation_grid() passes an explicit sweep_assets list so that
changing the default config never silently breaks the suite.

Covers:
  - build_allocation_grid  : count, sums, gold constraint, monotonicity (2-asset)
  - build_allocation_grid  : count, sums, extremes, gold variation      (3-asset)
  - alloc_to_active        : zero-weight filtering, sum invariant        (both modes)
  - alloc_label            : format contract for all three weights
  - _run_single_window     : None on short data, output schema, look-ahead
                             bias guard, edge allocations, 3-asset alloc
  - compute_allocation_stats: feasibility, breach counting, aggregation  (2-asset)
                              + 3-asset sort order and gold_pct column
  - find_optimal           : feasible path, infeasible fallback, label contract
  - MDD constraint boundary: exactly at −70%, one tick below
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from msci_upro_optimizer import (
    GOLD_FIXED,
    ALLOC_STEP,
    MDD_CONSTRAINT,
    ROLLING_WINDOW_YEARS,
    WINDOW_DAYS,
    alloc_label,
    alloc_to_active,
    build_allocation_grid,
    compute_allocation_stats,
    find_optimal,
    _run_single_window,
)

# Explicit sweep-mode constants used throughout — never rely on SWEEP_ASSETS default.
_2A = ["msci", "upro"]         # 2-asset: gold fixed
_3A = ["msci", "upro", "gold"] # 3-asset: gold swept


# ── shared fixtures ───────────────────────────────────────────────────────────

def _make_assets(n: int = 252 * 21, seed: int = 42) -> pd.DataFrame:
    """Deterministic 4-asset price DataFrame indexed by business days."""
    rng    = np.random.default_rng(seed)
    dates  = pd.bdate_range("1980-01-01", periods=n)
    rets   = rng.normal(0.0003, 0.01, (n, 4))
    prices = np.cumprod(1.0 + rets, axis=0) * 100.0
    return pd.DataFrame(prices, index=dates, columns=["spy", "upro", "gold", "msci"])


def _make_results(n_windows: int = 10, seed: int = 0,
                  sweep_assets: list[str] | None = None) -> pd.DataFrame:
    """
    Synthetic results DataFrame for a given sweep mode.

    Defaults to 2-asset (_2A) so tests that don't specify a mode are not
    affected by the module-level SWEEP_ASSETS setting.
    """
    if sweep_assets is None:
        sweep_assets = _2A
    rng  = np.random.default_rng(seed)
    grid = build_allocation_grid(sweep_assets)
    rows: list[dict] = []
    for alloc in grid:
        cagrs = rng.uniform(0.05, 0.15, n_windows)
        mdds  = rng.uniform(-0.60, -0.10, n_windows)   # all above −70%
        for i in range(n_windows):
            rows.append({
                "label":        alloc_label(alloc),
                "msci_pct":     alloc["msci"],
                "upro_pct":     alloc["upro"],
                "gold_pct":     alloc["gold"],
                "cagr":         float(cagrs[i]),
                "mdd":          float(mdds[i]),
                "spy_cagr":     float(rng.uniform(0.06, 0.10)),
                "spy_mdd":      -0.30,
                "window_start": pd.Timestamp("1980-01-01") + pd.DateOffset(years=i),
                "window_end":   pd.Timestamp("2000-01-01") + pd.DateOffset(years=i),
            })
    return pd.DataFrame(rows)


# ── TestBuildAllocationGrid (2-asset mode) ────────────────────────────────────

class TestBuildAllocationGrid:
    """All tests use explicit sweep_assets=_2A — independent of SWEEP_ASSETS."""

    def test_correct_count(self):
        """Grid length must be round((1 − gold) / step) + 1."""
        grid     = build_allocation_grid(_2A)
        expected = round((1.0 - GOLD_FIXED) / ALLOC_STEP) + 1
        assert len(grid) == expected

    def test_gold_fixed_in_every_entry(self):
        """Every allocation must have gold == GOLD_FIXED."""
        for alloc in build_allocation_grid(_2A):
            assert alloc["gold"] == pytest.approx(GOLD_FIXED, abs=1e-9)

    def test_weights_sum_to_one(self):
        for alloc in build_allocation_grid(_2A):
            total = alloc["msci"] + alloc["upro"] + alloc["gold"]
            assert total == pytest.approx(1.0, abs=1e-9), f"Sum = {total} for {alloc}"

    def test_no_negative_weights(self):
        for alloc in build_allocation_grid(_2A):
            assert alloc["msci"] >= 0.0
            assert alloc["upro"] >= 0.0

    def test_first_entry_zero_msci(self):
        """First entry: MSCI = 0%, UPRO = 1 − gold."""
        first = build_allocation_grid(_2A)[0]
        assert first["msci"] == pytest.approx(0.0,              abs=1e-9)
        assert first["upro"] == pytest.approx(1.0 - GOLD_FIXED, abs=1e-9)

    def test_last_entry_zero_upro(self):
        """Last entry: UPRO = 0%, MSCI = 1 − gold."""
        last = build_allocation_grid(_2A)[-1]
        assert last["upro"] == pytest.approx(0.0,              abs=1e-9)
        assert last["msci"] == pytest.approx(1.0 - GOLD_FIXED, abs=1e-9)

    def test_msci_monotone_increasing(self):
        vals = [a["msci"] for a in build_allocation_grid(_2A)]
        assert vals == sorted(vals)

    def test_upro_monotone_decreasing(self):
        vals = [a["upro"] for a in build_allocation_grid(_2A)]
        assert vals == sorted(vals, reverse=True)

    def test_step_size_is_alloc_step(self):
        """Consecutive MSCI weights must differ by exactly ALLOC_STEP."""
        msci_vals = [a["msci"] for a in build_allocation_grid(_2A)]
        diffs = [round(msci_vals[i+1] - msci_vals[i], 9) for i in range(len(msci_vals) - 1)]
        assert all(abs(d - ALLOC_STEP) < 1e-9 for d in diffs)

    def test_gold_single_unique_value(self):
        """In 2-asset mode, only one distinct gold value must exist."""
        grid = build_allocation_grid(_2A)
        assert len(set(a["gold"] for a in grid)) == 1

    def test_custom_gold_fixed(self):
        """Passing an explicit gold_fixed value must override GOLD_FIXED."""
        grid = build_allocation_grid(_2A, gold_fixed=0.15)
        assert all(a["gold"] == pytest.approx(0.15, abs=1e-9) for a in grid)
        assert all(abs(a["msci"] + a["upro"] + a["gold"] - 1.0) < 1e-9 for a in grid)


# ── TestBuildAllocationGrid3Asset ─────────────────────────────────────────────

class TestBuildAllocationGrid3Asset:
    """All tests use explicit sweep_assets=_3A — independent of SWEEP_ASSETS."""

    def test_correct_count_3asset(self):
        """
        With n=20 steps (5% resolution), combos = C(n+2, 2) = C(22, 2) = 231.
        """
        grid     = build_allocation_grid(_3A)
        n        = round(1.0 / ALLOC_STEP)
        expected = (n + 1) * (n + 2) // 2
        assert len(grid) == expected

    def test_weights_sum_to_one_3asset(self):
        for alloc in build_allocation_grid(_3A):
            total = alloc["msci"] + alloc["upro"] + alloc["gold"]
            assert total == pytest.approx(1.0, abs=1e-9), f"Sum={total} for {alloc}"

    def test_no_negative_weights_3asset(self):
        for alloc in build_allocation_grid(_3A):
            assert alloc["msci"] >= 0.0
            assert alloc["upro"] >= 0.0
            assert alloc["gold"] >= 0.0

    def test_contains_all_single_asset_extremes(self):
        """100% allocated to a single asset must appear in the 3-asset grid."""
        triples = {
            (round(a["msci"], 9), round(a["upro"], 9), round(a["gold"], 9))
            for a in build_allocation_grid(_3A)
        }
        assert (1.0, 0.0, 0.0) in triples
        assert (0.0, 1.0, 0.0) in triples
        assert (0.0, 0.0, 1.0) in triples

    def test_gold_varies_in_3asset_mode(self):
        """Gold must take multiple distinct values in 3-asset mode."""
        gold_vals = {a["gold"] for a in build_allocation_grid(_3A)}
        assert len(gold_vals) > 1

    def test_2asset_grid_gold_is_constant(self):
        """Explicit 2-asset grid must have exactly one distinct gold value."""
        grid = build_allocation_grid(_2A)
        assert len({a["gold"] for a in grid}) == 1

    def test_3asset_larger_than_2asset(self):
        """3-asset grid must be strictly larger than 2-asset."""
        assert len(build_allocation_grid(_3A)) > len(build_allocation_grid(_2A))

    def test_all_labels_unique_3asset(self):
        labels = [alloc_label(a) for a in build_allocation_grid(_3A)]
        assert len(labels) == len(set(labels))


# ── TestAllocToActive ─────────────────────────────────────────────────────────

class TestAllocToActive:
    def test_zero_upro_excluded(self):
        active = alloc_to_active({"msci": 0.90, "upro": 0.00, "gold": 0.10})
        assert "upro" not in active

    def test_zero_msci_excluded(self):
        active = alloc_to_active({"msci": 0.00, "upro": 0.90, "gold": 0.10})
        assert "msci" not in active

    def test_zero_gold_excluded_in_3asset(self):
        """When gold=0 (possible in 3-asset extremes), it must be filtered out."""
        active = alloc_to_active({"msci": 0.50, "upro": 0.50, "gold": 0.00})
        assert "gold" not in active

    def test_gold_present_when_nonzero(self):
        """Gold (any non-zero weight) must survive filtering."""
        active = alloc_to_active({"msci": 0.45, "upro": 0.45, "gold": 0.10})
        assert "gold" in active

    def test_gold_present_in_all_2asset_allocations(self):
        """In 2-asset mode, gold is always GOLD_FIXED > 0, so always active."""
        for alloc in build_allocation_grid(_2A):
            assert "gold" in alloc_to_active(alloc)

    def test_active_weights_sum_to_one_2asset(self):
        """Filtering zero-weight assets must not break the sum-to-1 property."""
        for alloc in build_allocation_grid(_2A):
            total = sum(alloc_to_active(alloc).values())
            assert total == pytest.approx(1.0, abs=1e-9)

    def test_active_weights_sum_to_one_3asset(self):
        """Sum-to-1 invariant must hold even when gold=0 is filtered in 3-asset."""
        for alloc in build_allocation_grid(_3A):
            total = sum(alloc_to_active(alloc).values())
            assert total == pytest.approx(1.0, abs=1e-9)

    def test_midpoint_alloc_all_three_assets_present(self):
        alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        active = alloc_to_active(alloc)
        assert set(active.keys()) == {"msci", "upro", "gold"}

    def test_returns_empty_only_if_all_weights_zero(self):
        """Only a fully-zero allocation should produce an empty active dict."""
        active = alloc_to_active({"msci": 0.0, "upro": 0.0, "gold": 0.0})
        assert active == {}


# ── TestAllocLabel ────────────────────────────────────────────────────────────

class TestAllocLabel:
    def test_all_three_components_shown(self):
        lbl = alloc_label({"msci": 0.45, "upro": 0.45, "gold": 0.10})
        assert "MSCI 45%" in lbl
        assert "UPRO 45%" in lbl
        assert "Gold 10%" in lbl

    def test_zero_upro_shown(self):
        lbl = alloc_label({"msci": 0.90, "upro": 0.00, "gold": 0.10})
        assert "UPRO 0%" in lbl

    def test_zero_msci_shown(self):
        lbl = alloc_label({"msci": 0.00, "upro": 0.90, "gold": 0.10})
        assert "MSCI 0%" in lbl

    def test_varied_gold_shown(self):
        lbl = alloc_label({"msci": 0.30, "upro": 0.50, "gold": 0.20})
        assert "Gold 20%" in lbl

    def test_all_2asset_labels_unique(self):
        labels = [alloc_label(a) for a in build_allocation_grid(_2A)]
        assert len(labels) == len(set(labels))

    def test_all_3asset_labels_unique(self):
        labels = [alloc_label(a) for a in build_allocation_grid(_3A)]
        assert len(labels) == len(set(labels))

    def test_label_is_string(self):
        assert isinstance(alloc_label({"msci": 0.3, "upro": 0.6, "gold": 0.1}), str)


# ── TestRunSingleWindow ───────────────────────────────────────────────────────

class TestRunSingleWindow:
    def test_returns_none_on_short_data(self):
        """Window with < 80% of target days must return None."""
        assets = _make_assets(n=100)
        alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        result = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert result is None

    def test_returns_dict_on_full_window(self):
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        result = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert result is not None
        assert isinstance(result, dict)

    def test_all_required_keys_present(self):
        assets   = _make_assets(n=252 * 21)
        alloc    = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        result   = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        required = {"label", "msci_pct", "upro_pct", "gold_pct",
                    "window_start", "window_end", "cagr", "mdd", "spy_cagr", "spy_mdd"}
        assert required == set(result.keys())

    def test_gold_pct_matches_allocation(self):
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.30, "upro": 0.60, "gold": 0.10}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert r["gold_pct"] == pytest.approx(0.10, abs=1e-9)

    def test_mdd_in_valid_range(self):
        """MDD must be in [−1, 0]."""
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert -1.0 <= r["mdd"] <= 0.0

    def test_spy_mdd_in_valid_range(self):
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert -1.0 <= r["spy_mdd"] <= 0.0

    def test_zero_upro_allocation_runs(self):
        """Pure MSCI + Gold (2-asset portfolio) must complete without error."""
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.90, "upro": 0.00, "gold": 0.10}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert r is not None
        assert r["cagr"] > -1.0

    def test_zero_msci_allocation_runs(self):
        """Pure UPRO + Gold (2-asset portfolio) must complete without error."""
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.00, "upro": 0.90, "gold": 0.10}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert r is not None
        assert r["cagr"] > -1.0

    def test_zero_gold_3asset_allocation_runs(self):
        """3-asset allocation with gold=0 must complete — gold is filtered by alloc_to_active."""
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.50, "upro": 0.50, "gold": 0.00}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert r is not None
        assert r["gold_pct"] == pytest.approx(0.00, abs=1e-9)

    def test_label_preserved_in_output(self):
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.30, "upro": 0.60, "gold": 0.10}
        lbl    = alloc_label(alloc)
        r      = _run_single_window(assets.index[0], assets, alloc, lbl)
        assert r["label"] == lbl

    def test_all_allocation_percentages_preserved(self):
        """msci_pct, upro_pct, gold_pct must all match the input alloc dict."""
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.30, "upro": 0.60, "gold": 0.10}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert r["msci_pct"] == pytest.approx(0.30, abs=1e-9)
        assert r["upro_pct"] == pytest.approx(0.60, abs=1e-9)
        assert r["gold_pct"] == pytest.approx(0.10, abs=1e-9)

    def test_no_lookahead_bias(self):
        """
        Corrupting data after the window end must not change the result.
        Verifies that only assets.loc[start_date : end_date] is consumed.
        """
        assets = _make_assets(n=252 * 25)
        alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        lbl    = alloc_label(alloc)

        r1 = _run_single_window(assets.index[0], assets, alloc, lbl)

        end_date  = assets.index[0] + pd.DateOffset(years=ROLLING_WINDOW_YEARS)
        end_pos   = assets.index.searchsorted(end_date, side="right")
        corrupted = assets.copy()
        corrupted.iloc[end_pos:] *= 1_000.0     # annihilate post-window data

        r2 = _run_single_window(corrupted.index[0], corrupted, alloc, lbl)

        assert r1["cagr"] == pytest.approx(r2["cagr"], abs=1e-8)
        assert r1["mdd"]  == pytest.approx(r2["mdd"],  abs=1e-8)

    def test_window_end_strictly_after_start(self):
        assets = _make_assets(n=252 * 21)
        alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
        r      = _run_single_window(assets.index[0], assets, alloc, alloc_label(alloc))
        assert r["window_end"] > r["window_start"]


# ── TestComputeAllocationStats (2-asset mode) ─────────────────────────────────

class TestComputeAllocationStats:
    """Uses _make_results(_2A) — independent of SWEEP_ASSETS."""

    def test_one_row_per_allocation(self):
        results = _make_results(sweep_assets=_2A)
        stats   = compute_allocation_stats(results)
        assert len(stats) == len(build_allocation_grid(_2A))

    def test_gold_pct_column_present(self):
        stats = compute_allocation_stats(_make_results(sweep_assets=_2A))
        assert "gold_pct" in stats.columns

    def test_gold_pct_constant_in_2asset_stats(self):
        """In 2-asset results, gold_pct must be the same for every row."""
        stats = compute_allocation_stats(_make_results(sweep_assets=_2A))
        assert stats["gold_pct"].nunique() == 1
        assert stats["gold_pct"].iloc[0] == pytest.approx(GOLD_FIXED, abs=1e-9)

    def test_feasible_when_all_mdd_above_constraint(self):
        """All MDD values safely above −70% → all rows feasible."""
        grid = build_allocation_grid(_2A)
        rows = [
            {
                "label": alloc_label(a), "msci_pct": a["msci"],
                "upro_pct": a["upro"], "gold_pct": a["gold"],
                "cagr": 0.10, "mdd": -0.50,
                "spy_cagr": 0.08, "spy_mdd": -0.30,
                "window_start": pd.Timestamp("1980-01-01"),
                "window_end":   pd.Timestamp("2000-01-01"),
            }
            for a in grid
        ]
        stats = compute_allocation_stats(pd.DataFrame(rows))
        assert stats["feasible"].all()

    def test_infeasible_when_any_mdd_below_constraint(self):
        """Any MDD crossing −70% must flip feasible to False."""
        grid = build_allocation_grid(_2A)
        rows = [
            {
                "label": alloc_label(a), "msci_pct": a["msci"],
                "upro_pct": a["upro"], "gold_pct": a["gold"],
                "cagr": 0.10, "mdd": -0.75,
                "spy_cagr": 0.08, "spy_mdd": -0.30,
                "window_start": pd.Timestamp("1980-01-01"),
                "window_end":   pd.Timestamp("2000-01-01"),
            }
            for a in grid
        ]
        stats = compute_allocation_stats(pd.DataFrame(rows))
        assert not stats["feasible"].any()

    def test_mdd_breach_count_correct(self):
        """mdd_breaches must count windows where mdd < MDD_CONSTRAINT exactly."""
        alloc = build_allocation_grid(_2A)[5]
        rows  = [
            {
                "label": alloc_label(alloc), "msci_pct": alloc["msci"],
                "upro_pct": alloc["upro"], "gold_pct": alloc["gold"],
                "cagr": 0.10, "mdd": mdd_val,
                "spy_cagr": 0.08, "spy_mdd": -0.30,
                "window_start": pd.Timestamp("1980-01-01") + pd.DateOffset(years=i),
                "window_end":   pd.Timestamp("2000-01-01") + pd.DateOffset(years=i),
            }
            # -0.40 OK, -0.72 BREACH, -0.55 OK, -0.80 BREACH, -0.65 OK → 2 breaches
            for i, mdd_val in enumerate([-0.40, -0.72, -0.55, -0.80, -0.65])
        ]
        stats = compute_allocation_stats(pd.DataFrame(rows))
        assert int(stats.iloc[0]["mdd_breaches"]) == 2

    def test_outperformance_rate_in_unit_interval(self):
        stats = compute_allocation_stats(_make_results(sweep_assets=_2A))
        assert (stats["outperformance_rate"] >= 0.0).all()
        assert (stats["outperformance_rate"] <= 1.0).all()

    def test_worst_cagr_le_median_cagr(self):
        stats = compute_allocation_stats(_make_results(sweep_assets=_2A))
        assert (stats["worst_cagr"] <= stats["median_cagr"] + 1e-12).all()

    def test_worst_mdd_le_median_mdd(self):
        """Most-negative MDD (worst) must be ≤ median MDD."""
        stats = compute_allocation_stats(_make_results(sweep_assets=_2A))
        assert (stats["worst_mdd"] <= stats["median_mdd"] + 1e-12).all()

    def test_sorted_ascending_by_msci_in_2asset(self):
        """In 2-asset mode, stats are sorted by msci_pct ascending."""
        stats = compute_allocation_stats(_make_results(sweep_assets=_2A))
        vals  = stats["msci_pct"].tolist()
        assert vals == sorted(vals)

    def test_n_windows_equals_input_count(self):
        n     = 7
        stats = compute_allocation_stats(_make_results(n_windows=n, sweep_assets=_2A))
        assert (stats["n_windows"] == n).all()

    def test_cagr_p25_le_median_le_p75(self):
        stats = compute_allocation_stats(_make_results(sweep_assets=_2A))
        assert (stats["cagr_p25"] <= stats["median_cagr"] + 1e-12).all()
        assert (stats["median_cagr"] <= stats["cagr_p75"] + 1e-12).all()

    def test_cagr_vs_spy_equals_median_minus_spy(self):
        """cagr_vs_spy must equal median_cagr − spy_median_cagr exactly."""
        stats    = compute_allocation_stats(_make_results(sweep_assets=_2A))
        expected = stats["median_cagr"] - stats["spy_median_cagr"]
        pd.testing.assert_series_equal(
            stats["cagr_vs_spy"].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False, atol=1e-12,
        )


# ── TestComputeAllocationStats3Asset ─────────────────────────────────────────

class TestComputeAllocationStats3Asset:
    """3-asset mode specific behaviour for compute_allocation_stats."""

    def test_one_row_per_3asset_allocation(self):
        results = _make_results(sweep_assets=_3A)
        stats   = compute_allocation_stats(results)
        assert len(stats) == len(build_allocation_grid(_3A))

    def test_gold_pct_varies_in_3asset_stats(self):
        """In 3-asset mode, gold_pct must take more than one distinct value."""
        stats = compute_allocation_stats(_make_results(sweep_assets=_3A))
        assert stats["gold_pct"].nunique() > 1

    def test_sorted_by_gold_then_msci_in_3asset(self):
        """
        3-asset stats must be sorted primarily by gold_pct, secondarily by msci_pct.
        """
        stats = compute_allocation_stats(_make_results(sweep_assets=_3A))
        gold_vals = stats["gold_pct"].tolist()
        assert gold_vals == sorted(gold_vals), "gold_pct is not sorted ascending"
        # Within each gold_pct level, msci_pct must be sorted ascending
        for gold_v in stats["gold_pct"].unique():
            subset = stats[stats["gold_pct"] == gold_v]["msci_pct"].tolist()
            assert subset == sorted(subset), (
                f"msci_pct not sorted within gold_pct={gold_v}"
            )

    def test_all_3asset_stats_have_gold_pct(self):
        stats = compute_allocation_stats(_make_results(sweep_assets=_3A))
        assert stats["gold_pct"].notna().all()


# ── TestFindOptimal ───────────────────────────────────────────────────────────

class TestFindOptimal:
    def _base_stats(self) -> pd.DataFrame:
        return pd.DataFrame({
            "label":               ["A", "B", "C"],
            "msci_pct":            [0.30, 0.50, 0.70],
            "upro_pct":            [0.60, 0.40, 0.20],
            "gold_pct":            [0.10, 0.10, 0.10],
            "n_windows":           [10, 10, 10],
            "median_cagr":         [0.10, 0.14, 0.12],
            "mean_cagr":           [0.10, 0.14, 0.12],
            "worst_cagr":          [0.05, 0.06, 0.04],
            "best_cagr":           [0.15, 0.20, 0.18],
            "cagr_p25":            [0.08, 0.10, 0.09],
            "cagr_p75":            [0.12, 0.16, 0.14],
            "worst_mdd":           [-0.40, -0.60, -0.80],  # C is infeasible
            "median_mdd":          [-0.30, -0.45, -0.60],
            "mdd_breaches":        [0, 0, 2],
            "feasible":            [True, True, False],
            "spy_median_cagr":     [0.09, 0.09, 0.09],
            "outperformance_rate": [0.70, 0.80, 0.90],
            "cagr_vs_spy":         [0.01, 0.05, 0.03],
        })

    def test_picks_feasible_with_highest_median_cagr(self):
        """Among feasible allocations, the one with highest median CAGR wins."""
        lbl, _ = find_optimal(self._base_stats())
        assert lbl == "B"

    def test_ignores_infeasible_allocations(self):
        """C has a higher outperformance_rate but breaches MDD — must be ignored."""
        lbl, _ = find_optimal(self._base_stats())
        assert lbl != "C"

    def test_fallback_to_least_breaches_when_all_infeasible(self):
        data = pd.DataFrame({
            "label":               ["A", "B"],
            "msci_pct":            [0.30, 0.50],
            "upro_pct":            [0.60, 0.40],
            "gold_pct":            [0.10, 0.10],
            "n_windows":           [10, 10],
            "median_cagr":         [0.10, 0.08],
            "mean_cagr":           [0.10, 0.08],
            "worst_cagr":          [0.05, 0.04],
            "best_cagr":           [0.15, 0.14],
            "cagr_p25":            [0.08, 0.06],
            "cagr_p75":            [0.12, 0.10],
            "worst_mdd":           [-0.80, -0.75],  # both infeasible
            "median_mdd":          [-0.60, -0.60],
            "mdd_breaches":        [3, 1],           # B has fewer breaches
            "feasible":            [False, False],
            "spy_median_cagr":     [0.09, 0.09],
            "outperformance_rate": [0.70, 0.60],
            "cagr_vs_spy":         [0.01, -0.01],
        })
        lbl, _ = find_optimal(data)
        assert lbl == "B"

    def test_among_equal_breach_fallback_picks_higher_median_cagr(self):
        """Tie on mdd_breaches → pick highest median CAGR."""
        data = pd.DataFrame({
            "label":               ["X", "Y"],
            "msci_pct":            [0.30, 0.50],
            "upro_pct":            [0.60, 0.40],
            "gold_pct":            [0.10, 0.10],
            "n_windows":           [10, 10],
            "median_cagr":         [0.09, 0.12],   # Y wins
            "mean_cagr":           [0.09, 0.12],
            "worst_cagr":          [0.05, 0.05],
            "best_cagr":           [0.15, 0.18],
            "cagr_p25":            [0.07, 0.09],
            "cagr_p75":            [0.11, 0.14],
            "worst_mdd":           [-0.80, -0.75],
            "median_mdd":          [-0.60, -0.60],
            "mdd_breaches":        [2, 2],          # equal breaches
            "feasible":            [False, False],
            "spy_median_cagr":     [0.09, 0.09],
            "outperformance_rate": [0.50, 0.60],
            "cagr_vs_spy":         [0.00, 0.03],
        })
        lbl, _ = find_optimal(data)
        assert lbl == "Y"

    def test_returned_row_label_matches_string(self):
        """The returned Series must carry the same label as the returned string."""
        results = _make_results(sweep_assets=_2A)
        stats   = compute_allocation_stats(results)
        lbl, row = find_optimal(stats)
        assert row["label"] == lbl

    def test_returns_series(self):
        results = _make_results(sweep_assets=_2A)
        stats   = compute_allocation_stats(results)
        _, row  = find_optimal(stats)
        assert isinstance(row, pd.Series)

    def test_optimal_is_feasible_when_feasible_exists(self):
        results = _make_results(sweep_assets=_2A)
        stats   = compute_allocation_stats(results)
        _, row  = find_optimal(stats)
        assert bool(row["feasible"]) is True

    def test_works_with_3asset_stats(self):
        """find_optimal must produce a valid result from 3-asset statistics too."""
        results = _make_results(sweep_assets=_3A)
        stats   = compute_allocation_stats(results)
        lbl, row = find_optimal(stats)
        assert isinstance(lbl, str)
        assert bool(row["feasible"]) is True


# ── TestMDDConstraintBoundary ─────────────────────────────────────────────────

class TestMDDConstraintBoundary:
    def _single_alloc_stats(self, mdd_val: float) -> pd.DataFrame:
        alloc = build_allocation_grid(_2A)[0]
        rows  = [{
            "label":        alloc_label(alloc),
            "msci_pct":     alloc["msci"],
            "upro_pct":     alloc["upro"],
            "gold_pct":     alloc["gold"],
            "cagr":         0.10,
            "mdd":          mdd_val,
            "spy_cagr":     0.08,
            "spy_mdd":      -0.30,
            "window_start": pd.Timestamp("1980-01-01"),
            "window_end":   pd.Timestamp("2000-01-01"),
        }]
        return compute_allocation_stats(pd.DataFrame(rows))

    def test_exactly_at_constraint_is_feasible(self):
        """MDD == MDD_CONSTRAINT (−0.70 exactly) must be feasible (≥ constraint)."""
        stats = self._single_alloc_stats(MDD_CONSTRAINT)
        assert bool(stats.iloc[0]["feasible"]) is True

    def test_one_epsilon_below_constraint_is_infeasible(self):
        """MDD = MDD_CONSTRAINT − ε must flip feasible to False."""
        stats = self._single_alloc_stats(MDD_CONSTRAINT - 1e-9)
        assert bool(stats.iloc[0]["feasible"]) is False

    def test_above_constraint_no_breach(self):
        """MDD = −0.50 (well above −70%) → mdd_breaches = 0."""
        stats = self._single_alloc_stats(-0.50)
        assert int(stats.iloc[0]["mdd_breaches"]) == 0

    def test_below_constraint_one_breach(self):
        """MDD = −0.75 → mdd_breaches = 1."""
        stats = self._single_alloc_stats(-0.75)
        assert int(stats.iloc[0]["mdd_breaches"]) == 1

    def test_worst_mdd_matches_input(self):
        """worst_mdd in stats must equal the single window's mdd value."""
        val   = -0.55
        stats = self._single_alloc_stats(val)
        assert stats.iloc[0]["worst_mdd"] == pytest.approx(val, abs=1e-12)
