"""
Benchmark: vectorised calculate_metrics vs. the original O(n) loop.

Run from the workspace root:
    python tests/benchmark_calculate_metrics.py
"""
from __future__ import annotations

import sys
import os
import timeit

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rolling_backtest_suite import _calculate_metrics_loop, calculate_metrics

WEIGHTS = {"spy": 0.70, "upro": 0.15, "gold": 0.15}
REPEATS = 200


def _make_prices(n: int = 252 * 30, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("1987-01-01", periods=n)
    rets = rng.normal(0.0003, 0.01, (n, 3))
    return pd.DataFrame(
        np.cumprod(1.0 + rets, axis=0) * 100.0,
        index=dates,
        columns=["spy", "upro", "gold"],
    )


def main() -> None:
    print("=" * 60)
    print("Benchmark: calculate_metrics  (30-year window, 200 runs)")
    print("=" * 60)

    for window_years in [10, 20, 30]:
        n = window_years * 252
        df = _make_prices(n=n)

        t_loop = timeit.timeit(
            lambda: _calculate_metrics_loop(df, WEIGHTS),
            number=REPEATS,
        )
        t_vec = timeit.timeit(
            lambda: calculate_metrics(df, True, WEIGHTS),
            number=REPEATS,
        )

        speedup = t_loop / t_vec
        print(
            f"  {window_years:2d}y window ({n:5d} days) | "
            f"loop: {t_loop / REPEATS * 1000:.2f} ms/call  "
            f"vec: {t_vec / REPEATS * 1000:.2f} ms/call  "
            f"speedup: {speedup:.1f}×"
        )

    print()
    print("Note: speedup scales with window length because the loop overhead")
    print("is O(n) while the vectorised version iterates only over ~n/63")
    print("rebalance periods.")


if __name__ == "__main__":
    main()
