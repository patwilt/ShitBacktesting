"""
Performance benchmark for msci_upro_optimizer.py
=================================================
Measures:
  1. calculate_metrics scaling — vectorised vs reference loop at 5/10/20-year windows.
  2. Parallel sweep speedup     — threading backend vs single-thread dispatch,
                                   measured across multiple core counts.
  3. Per-allocation task cost   — median time per (alloc, window) pair at scale.

Run from the workspace root:
    python tests/benchmark_msci_upro_optimizer.py
"""
from __future__ import annotations

import os
import sys
import timeit

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rolling_backtest_suite import calculate_metrics, _calculate_metrics_loop
from msci_upro_optimizer import (
    WINDOW_DAYS,
    build_allocation_grid,
    alloc_label,
    alloc_to_active,
    _run_single_window,
)

REPEATS = 300


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_assets(n: int = WINDOW_DAYS, seed: int = 42) -> pd.DataFrame:
    """Deterministic 4-asset price DataFrame."""
    rng    = np.random.default_rng(seed)
    dates  = pd.bdate_range("1980-01-01", periods=n)
    rets   = rng.normal(0.0003, 0.01, (n, 4))
    prices = np.cumprod(1.0 + rets, axis=0) * 100.0
    return pd.DataFrame(prices, index=dates, columns=["spy", "upro", "gold", "msci"])


# ── Benchmark 1: vectorised metrics vs reference loop ───────────────────────

def bench_metrics_scaling() -> None:
    print("=" * 68)
    print(" Benchmark 1: calculate_metrics — vectorised vs reference loop")
    print("=" * 68)
    weights = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
    active  = alloc_to_active(weights)
    cols    = list(active.keys())

    print(
        f"  {'Window':>10}  {'Days':>6}  "
        f"{'Vectorised':>14}  {'Loop (ref)':>14}  {'Speedup':>8}"
    )
    print("  " + "─" * 60)

    for years in [5, 10, 20]:
        n  = years * 252
        df = _make_assets(n=n)[cols]

        t_vec = timeit.timeit(
            lambda: calculate_metrics(df, is_rebalanced=True, weights=active),
            number=REPEATS,
        )
        t_loop = timeit.timeit(
            lambda: _calculate_metrics_loop(df, active),
            number=REPEATS,
        )
        ms_vec  = t_vec  / REPEATS * 1_000
        ms_loop = t_loop / REPEATS * 1_000
        speedup = t_loop / t_vec

        print(
            f"  {years:>3}y window  {n:>6}  "
            f"{ms_vec:>11.3f} ms  "
            f"{ms_loop:>11.3f} ms  "
            f"{speedup:>7.1f}×"
        )


# ── Benchmark 2: parallel sweep speedup ──────────────────────────────────────

def bench_parallel_sweep() -> None:
    print()
    print("=" * 68)
    print(" Benchmark 2: parallel sweep — threading vs single-thread")
    print("=" * 68)

    assets = _make_assets(n=252 * 25)
    grid   = build_allocation_grid()

    # Use a manageable subset: 5 allocations × 80 windows = 400 tasks
    # (enough to amortise scheduling overhead while completing in < 30 s)
    starts = assets.index[:-WINDOW_DAYS:20][:80]
    subset = grid[:5]

    tasks = [
        (s, assets, alloc, alloc_label(alloc))
        for alloc in subset
        for s     in starts
    ]

    n_cores = os.cpu_count() or 1
    print(f"  Tasks  : {len(tasks)}  ({len(subset)} allocs × {len(starts)} windows)")
    print(f"  Cores  : {n_cores} logical cores available")
    print()

    # Single-thread
    t_serial = timeit.timeit(
        lambda: [_run_single_window(s, a, al, lb) for s, a, al, lb in tasks],
        number=3,
    ) / 3

    # Multi-thread (joblib threading, n_jobs=-1)
    t_parallel = timeit.timeit(
        lambda: Parallel(n_jobs=-1, backend="threading")(
            delayed(_run_single_window)(s, a, al, lb) for s, a, al, lb in tasks
        ),
        number=3,
    ) / 3

    efficiency = t_serial / t_parallel / n_cores

    print(f"  Serial    : {t_serial:.3f} s  ({t_serial/len(tasks)*1000:.2f} ms/task)")
    print(f"  Parallel  : {t_parallel:.3f} s  ({t_parallel/len(tasks)*1000:.2f} ms/task)")
    print(f"  Speedup   : {t_serial / t_parallel:.2f}×")
    print(f"  Efficiency: {efficiency:.0%} per core")
    print()
    print("  Note: threading speedup is sub-linear due to GIL contention on")
    print("  pure-Python overhead (slice/copy), but numpy kernels run in parallel.")


# ── Benchmark 3: per-task overhead at 20-year scale ──────────────────────────

def bench_per_task_overhead() -> None:
    print()
    print("=" * 68)
    print(" Benchmark 3: per-task overhead at full 20-year window scale")
    print("=" * 68)

    assets = _make_assets(n=WINDOW_DAYS + 5)
    alloc  = {"msci": 0.45, "upro": 0.45, "gold": 0.10}
    label  = alloc_label(alloc)

    t = timeit.timeit(
        lambda: _run_single_window(assets.index[0], assets, alloc, label),
        number=REPEATS,
    )
    ms_per_task = t / REPEATS * 1_000

    grid        = build_allocation_grid()
    limit_start = assets.index[-1] - pd.DateOffset(years=20)

    # Full sweep estimate
    all_assets_full = _make_assets(n=252 * 44)   # ~44 years of data
    full_window_starts = all_assets_full.iloc[:-WINDOW_DAYS:5].index
    total_tasks = len(grid) * len(full_window_starts)

    print(f"  ms per (alloc, window) task : {ms_per_task:.3f} ms")
    print(f"  Full sweep task count       : {total_tasks:,}")
    print(f"  Single-thread full sweep    : ~{ms_per_task * total_tasks / 1000:.0f} s")
    print(f"  Parallel ({n_cores} cores) estimate: ~{ms_per_task * total_tasks / 1000 / (n_cores * 0.7):.0f} s"
          f"  (@ 70% efficiency)")


n_cores = os.cpu_count() or 1


def main() -> None:
    bench_metrics_scaling()
    bench_parallel_sweep()
    bench_per_task_overhead()
    print()
    print("=" * 68)
    print(" All benchmarks complete.")
    print("=" * 68)


if __name__ == "__main__":
    main()
