"""
MSCI / UPRO Ratio Optimizer — 10% Gold, MDD ≤ 70% Constraint
=============================================================
Answers: "What is the optimal MSCI:UPRO ratio when holding 10% gold
          across all 20-year periods since 1980, with MDD ≤ 70%?"

Configure SWEEP_ASSETS to control the search space:
  ["msci", "upro"]         → 2-asset sweep (gold fixed at GOLD_FIXED, 19 allocations)
  ["msci", "upro", "gold"] → 3-asset sweep (full grid, 231 allocations at 5% step)

Technical Blueprint
-------------------
2-asset: Grid over 19 MSCI/UPRO splits (5% steps, gold fixed).
3-asset: All combos where msci + upro + gold = 1.0 at ALLOC_STEP resolution.
         C(n+k-1, k-1) = C(22,2) = 231 allocations at 5% steps.
Complexity:  O(W × G × N/R)  — W ≈ 2,200 windows, G ∈ {19, 231}, N/R ≈ 80.
Parallelism: joblib threading backend — numpy/pandas release the GIL so
             multi-core execution is effective without serialisation cost.
Bias guard:  ffill-only alignment; windows skipped when < 80% data present.
Benchmark:   S&P 500 total-return (buy-and-hold, 1.5% div yield already in price).
"""
from __future__ import annotations

import os
import sys
import timeit
from typing import Optional

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from tqdm import tqdm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rolling_backtest_suite import calculate_metrics, load_market_data


# ==========================================
# CONFIGURATION
# ==========================================

START_DATE           = "1980-01-01"
ROLLING_WINDOW_YEARS = 25
WINDOW_DAYS          = ROLLING_WINDOW_YEARS * 252   # ≈ 5,040 trading days
ALLOC_STEP           = 0.05           # 5% grid steps
MDD_CONSTRAINT       = -0.70          # Must not exceed −70% drawdown
WINDOW_STEP_DAYS     = 1              # Roll 20-year window every 5 trading days

# ── Sweep control ─────────────────────────────────────────────────────────────
# List assets whose allocations will be swept across the grid.
#   ["msci", "upro"]         → Gold fixed at GOLD_FIXED  (19 allocations, fast)
#   ["msci", "upro", "gold"] → Full 3-asset grid          (231 allocations at 5%)
SWEEP_ASSETS = ["msci", "upro", "gold"]

# Fixed gold weight — only applied when "gold" is NOT in SWEEP_ASSETS.
GOLD_FIXED   = 0.10


# ==========================================
# ALLOCATION GRID
# ==========================================

def build_allocation_grid(
    sweep_assets: list[str] | None = None,
    gold_fixed:   float      | None = None,
) -> list[dict[str, float]]:
    """
    Generate all allocation combinations for the configured sweep.

    2-asset mode  (sweep_assets = ["msci", "upro"]):
        msci ∈ {0, step, …, 1 − gold_fixed}
        upro  = (1 − gold_fixed) − msci
        gold  = gold_fixed  (constant)
        Length = round((1 − gold) / step) + 1 = 19 at defaults.

    3-asset mode  (sweep_assets = ["msci", "upro", "gold"]):
        All non-negative integer combos (i, j, k) where i+j+k = n_steps,
        giving msci = i×step, upro = j×step, gold = k×step.
        Length = C(n_steps + 2, 2) = C(22, 2) = 231 at 5% step.

    Every dict has keys "msci", "upro", "gold" that sum to 1.0.
    """
    sweep  = sweep_assets if sweep_assets is not None else SWEEP_ASSETS
    g_fix  = gold_fixed   if gold_fixed   is not None else GOLD_FIXED
    n_tot  = round(1.0 / ALLOC_STEP)   # total steps across all assets

    if "gold" not in sweep:
        # ── 2-asset: gold is fixed ────────────────────────────────────────────
        non_gold = round(1.0 - g_fix, 10)
        n_steps  = round(non_gold / ALLOC_STEP)
        return [
            {
                "msci": round(i * ALLOC_STEP, 10),
                "upro": round(max(non_gold - i * ALLOC_STEP, 0.0), 10),
                "gold": g_fix,
            }
            for i in range(n_steps + 1)
        ]
    else:
        # ── 3-asset: enumerate all combos where msci + upro + gold = 1.0 ─────
        grid: list[dict[str, float]] = []
        for i in range(n_tot + 1):          # msci steps
            for j in range(n_tot + 1 - i):  # gold steps
                k = n_tot - i - j           # upro steps (always ≥ 0)
                grid.append({
                    "msci": round(i * ALLOC_STEP, 10),
                    "upro": round(k * ALLOC_STEP, 10),
                    "gold": round(j * ALLOC_STEP, 10),
                })
        return grid


def alloc_label(alloc: dict[str, float]) -> str:
    """Human-readable label always showing all three weights.

    e.g. 'MSCI 45% / UPRO 45% / Gold 10%'
    """
    return (
        f"MSCI {round(alloc['msci'] * 100)}% / "
        f"UPRO {round(alloc['upro'] * 100)}% / "
        f"Gold {round(alloc['gold'] * 100)}%"
    )


def alloc_to_active(alloc: dict[str, float]) -> dict[str, float]:
    """
    Filter out zero-weight assets to avoid pct_change noise in excluded columns.

    Remaining weights always sum to 1.0. At the extremes of the grid one of
    msci or upro may be 0; in 2-asset mode gold is always non-zero (0.10).
    """
    return {k: v for k, v in alloc.items() if v > 1e-9}


# ==========================================
# OPTIMIZATION ENGINE
# ==========================================

def _run_single_window(
    start_date: pd.Timestamp,
    assets:     pd.DataFrame,
    alloc:      dict[str, float],
    label:      str,
) -> Optional[dict]:
    """
    Compute CAGR and MDD for one (allocation, 20-year window) pair.

    Look-ahead guard: only assets.loc[start_date : end_date] is consumed;
    no future prices can enter the calculation.

    Skips (returns None) when the available data covers < 80% of the target
    window — prevents partial-window bias near data gaps or the series end.

    Complexity: O(N/R) ≈ O(80) vectorised rebalance periods per call.
    """
    end_date   = start_date + pd.DateOffset(years=ROLLING_WINDOW_YEARS)
    data_slice = assets.loc[start_date:end_date]

    if len(data_slice) < WINDOW_DAYS * 0.8:
        return None

    active = alloc_to_active(alloc)
    if not all(k in data_slice.columns for k in active):
        return None

    cagr,     mdd     = calculate_metrics(
        data_slice[list(active.keys())], is_rebalanced=True, weights=active
    )
    spy_cagr, spy_mdd = calculate_metrics(data_slice[["spy"]])

    return {
        "label":        label,
        "msci_pct":     alloc["msci"],
        "upro_pct":     alloc["upro"],
        "gold_pct":     alloc["gold"],
        "window_start": data_slice.index[0],
        "window_end":   data_slice.index[-1],
        "cagr":         cagr,
        "mdd":          mdd,
        "spy_cagr":     spy_cagr,
        "spy_mdd":      spy_mdd,
    }


def run_optimization(assets: pd.DataFrame) -> pd.DataFrame:
    """
    Sweep every (allocation, window) pair in parallel via joblib threading.

    Threading is used — not multiprocessing — because numpy/pandas release
    the GIL during array operations, giving genuine multi-core speedup
    without the overhead of pickling the assets DataFrame per worker.

    Returns
    -------
    DataFrame with one row per valid (allocation, window) pair.
    """
    grid          = build_allocation_grid()
    limit_start   = assets.index[-1] - pd.DateOffset(years=ROLLING_WINDOW_YEARS)
    window_starts = assets.loc[START_DATE:limit_start].index[::WINDOW_STEP_DAYS]

    tasks = [
        (s, assets, alloc, alloc_label(alloc))
        for alloc in grid
        for s     in window_starts
    ]

    print(f"  {len(grid)} allocations × {len(window_starts)} windows "
          f"= {len(tasks):,} tasks")

    raw = Parallel(n_jobs=-1, backend="threading")(
        delayed(_run_single_window)(s, a, al, lb)
        for s, a, al, lb in tqdm(tasks, desc="  Sweeping")
    )
    df = pd.DataFrame([r for r in raw if r is not None])
    df["window_end"]   = pd.to_datetime(df["window_end"])
    df["window_start"] = pd.to_datetime(df["window_start"])
    return df


# ==========================================
# STATISTICS & OPTIMALITY
# ==========================================

def compute_allocation_stats(results: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per-allocation statistics across all rolling windows.

    Feasibility rule: an allocation is *feasible* iff every window satisfies
        mdd >= MDD_CONSTRAINT  (i.e. worst-case drawdown ≤ 70%).

    Outperformance rate: fraction of windows where portfolio CAGR > S&P 500.
    MDD breaches: count of windows where mdd < MDD_CONSTRAINT.

    Returns
    -------
    DataFrame, one row per allocation, sorted ascending by msci_pct.
    """
    rows: list[dict] = []
    for label, g in results.groupby("label", sort=False):
        spy_med  = g["spy_cagr"].median()
        med_cagr = g["cagr"].median()
        rows.append({
            "label":               label,
            "msci_pct":            g["msci_pct"].iloc[0],
            "upro_pct":            g["upro_pct"].iloc[0],
            "gold_pct":            g["gold_pct"].iloc[0],
            "n_windows":           len(g),
            "median_cagr":         med_cagr,
            "mean_cagr":           g["cagr"].mean(),
            "worst_cagr":          g["cagr"].min(),
            "best_cagr":           g["cagr"].max(),
            "cagr_p25":            g["cagr"].quantile(0.25),
            "cagr_p75":            g["cagr"].quantile(0.75),
            "worst_mdd":           g["mdd"].min(),
            "median_mdd":          g["mdd"].median(),
            "mdd_breaches":        int((g["mdd"] < MDD_CONSTRAINT).sum()),
            "feasible":            bool((g["mdd"] >= MDD_CONSTRAINT).all()),
            "spy_median_cagr":     spy_med,
            "outperformance_rate": float((g["cagr"] > g["spy_cagr"]).mean()),
            "cagr_vs_spy":         med_cagr - spy_med,
        })
    is_3asset = results["gold_pct"].nunique() > 1
    sort_cols = ["gold_pct", "msci_pct"] if is_3asset else ["msci_pct"]
    return (
        pd.DataFrame(rows)
        .sort_values(sort_cols)
        .reset_index(drop=True)
    )


def find_optimal(stats: pd.DataFrame) -> tuple[str, pd.Series]:
    """
    Identify the best allocation.

    Primary criterion:  highest median CAGR among fully feasible allocations
                        (all windows pass MDD ≤ 70%).
    Fallback criterion: fewest MDD breaches, then highest median CAGR when
                        no allocation is fully feasible.

    Returns (label, stats_row_as_Series).
    """
    feasible = stats[stats["feasible"]]
    if not feasible.empty:
        best = feasible.sort_values("median_cagr", ascending=False).iloc[0]
    else:
        best = stats.sort_values(
            ["mdd_breaches", "median_cagr"], ascending=[True, False]
        ).iloc[0]
    return str(best["label"]), best


# ==========================================
# VISUALISATION
# ==========================================

_PAL = {
    "optimal":   "#00D4A0",
    "feasible":  "#4C9BE8",
    "infeasible":"#E84C4C",
    "spy":       "#FFB347",
    "iqr":       "rgba(76,155,232,0.18)",
    "opt_fill":  "rgba(0,212,160,0.10)",
    "bg":        "#0D1117",
    "panel":     "#161B22",
    "grid":      "#30363D",
    "text":      "#E6EDF3",
    "sub":       "#8B949E",
    "row_opt":   "#142b1e",
    "row_spy":   "#1e1e10",
}


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _dot_color(label: str, feasible: bool, optimal_label: str) -> str:
    if label == optimal_label:
        return _PAL["optimal"]
    return _PAL["feasible"] if feasible else _PAL["infeasible"]


def create_dashboard(
    results:       pd.DataFrame,
    stats:         pd.DataFrame,
    optimal_label: str,
    optimal_row:   pd.Series,
) -> go.Figure:
    """
    Five-panel interactive Plotly dashboard answering the core question.

    2-asset mode (gold fixed):
      Panel ①  CAGR Profile   — median + IQR + worst-case line vs MSCI%.
      Panel ②  MDD Profile    — worst drawdown bar chart + −70% constraint line.

    3-asset mode (gold swept):
      Panel ①  CAGR Heatmap   — median CAGR grid: x=MSCI%, y=Gold%.
      Panel ②  MDD Heatmap    — worst MDD grid:   x=MSCI%, y=Gold%.
      (UPRO = 100% − MSCI% − Gold% in both)

    Both modes share:
      Panel ③  Frontier       — median CAGR vs worst MDD scatter.
      Panel ④  Timeline       — rolling CAGR: optimal allocation vs S&P 500.
      Panel ⑤  Summary Table  — top feasible allocations + S&P 500 benchmark.
    """
    is_3asset = stats["gold_pct"].nunique() > 1

    p1_title = (
        "① Median CAGR — MSCI% vs Gold%  (UPRO fills remainder)"
        if is_3asset else
        "① CAGR Profile by MSCI Allocation"
    )
    p2_title = (
        "② Worst MDD — MSCI% vs Gold%  (✗ = breaches −70% constraint)"
        if is_3asset else
        "② Max Drawdown Profile by MSCI Allocation"
    )

    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            p1_title, p2_title,
            "③ Efficiency Frontier  (Median CAGR vs Worst MDD)",
            "④ Rolling 20-Year CAGR Timeline",
            "⑤ Top Allocations Summary",
            "",
        ),
        specs=[
            [{"type": "xy"},    {"type": "xy"}],
            [{"type": "xy"},    {"type": "xy"}],
            [{"type": "table", "colspan": 2}, None],
        ],
        row_heights=[0.30, 0.30, 0.40],
        vertical_spacing=0.11,
        horizontal_spacing=0.10,
    )

    spy_med_cagr  = stats["spy_median_cagr"].iloc[0] * 100
    labels        = stats["label"].tolist()
    feasible_mask = stats["feasible"].values

    dot_colors  = [_dot_color(lb, f, optimal_label) for lb, f in zip(labels, feasible_mask)]
    dot_sizes   = [14 if lb == optimal_label else 7  for lb in labels]
    dot_symbols = ["star" if lb == optimal_label else "circle" for lb in labels]
    border_w    = [2.5 if lb == optimal_label else 0 for lb in labels]
    # Always available — used by the shared Panel ③ scatter labels in both modes.
    msci_pcts   = stats["msci_pct"].values * 100

    if is_3asset:
        # ── 3-asset mode: heatmap panels ①② ───────────────────────────────────
        cagr_piv  = stats.pivot(index="gold_pct", columns="msci_pct", values="median_cagr")
        mdd_piv   = stats.pivot(index="gold_pct", columns="msci_pct", values="worst_mdd")
        upro_piv  = stats.pivot(index="gold_pct", columns="msci_pct", values="upro_pct")
        wcagr_piv = stats.pivot(index="gold_pct", columns="msci_pct", values="worst_cagr")

        x_vals = (cagr_piv.columns * 100).round().astype(int).tolist()
        y_vals = (cagr_piv.index   * 100).round().astype(int).tolist()

        # customdata for ①: [upro%, worst_cagr%, worst_mdd%]
        cd1 = np.stack([
            upro_piv.values  * 100,
            wcagr_piv.values * 100,
            mdd_piv.values   * 100,
        ], axis=-1)

        # Panel ①: CAGR heatmap
        fig.add_trace(go.Heatmap(
            x=x_vals, y=y_vals,
            z=cagr_piv.values * 100,
            customdata=cd1,
            colorscale="RdYlGn",
            colorbar=dict(title="Med CAGR%", x=0.44, xanchor="left",
                          thickness=12, len=0.27, ticksuffix="%"),
            hovertemplate=(
                "<b>MSCI %{x}% / UPRO %{customdata[0]:.0f}% / Gold %{y}%</b><br>"
                "Median CAGR : %{z:.2f}%<br>"
                "Worst CAGR  : %{customdata[1]:.2f}%<br>"
                "Worst MDD   : %{customdata[2]:.1f}%"
                "<extra></extra>"
            ),
            name="Median CAGR",
        ), row=1, col=1)

        # customdata for ②: [upro%, median_cagr%, worst_cagr%]
        cd2 = np.stack([
            upro_piv.values  * 100,
            cagr_piv.values  * 100,
            wcagr_piv.values * 100,
        ], axis=-1)

        # Panel ②: MDD heatmap (zmin=-90, zmax=0 anchors the colorscale)
        fig.add_trace(go.Heatmap(
            x=x_vals, y=y_vals,
            z=mdd_piv.values * 100,
            zmin=-90, zmax=0,
            customdata=cd2,
            colorscale="RdYlGn",
            colorbar=dict(title="Worst MDD%", x=1.01, xanchor="left",
                          thickness=12, len=0.27, ticksuffix="%"),
            hovertemplate=(
                "<b>MSCI %{x}% / UPRO %{customdata[0]:.0f}% / Gold %{y}%</b><br>"
                "Worst MDD   : %{z:.1f}%<br>"
                "Median CAGR : %{customdata[1]:.2f}%<br>"
                "Worst CAGR  : %{customdata[2]:.2f}%"
                "<extra></extra>"
            ),
            showlegend=False, name="Worst MDD",
        ), row=1, col=2)

        # X markers for infeasible cells on both heatmaps
        infeasible = stats[~stats["feasible"]]
        if len(infeasible) > 0:
            for r_idx, c_idx in [(1, 1), (1, 2)]:
                fig.add_trace(go.Scatter(
                    x=infeasible["msci_pct"] * 100,
                    y=infeasible["gold_pct"] * 100,
                    mode="markers",
                    marker=dict(symbol="x-thin", size=11,
                                color=_PAL["infeasible"],
                                line=dict(width=2.5)),
                    name="Infeasible (MDD > 70%)" if (r_idx, c_idx) == (1, 1) else None,
                    showlegend=(r_idx == 1 and c_idx == 1),
                    hoverinfo="skip",
                ), row=r_idx, col=c_idx)

        # Optimal star on both heatmaps
        opt_r = stats[stats["label"] == optimal_label].iloc[0]
        for r_idx, c_idx, show in [(1, 1, True), (1, 2, False)]:
            fig.add_trace(go.Scatter(
                x=[opt_r["msci_pct"] * 100],
                y=[opt_r["gold_pct"] * 100],
                mode="markers",
                marker=dict(symbol="star", size=18, color=_PAL["optimal"],
                            line=dict(width=2, color="white")),
                name="★ Optimal" if show else None,
                showlegend=show,
                hovertext=(
                    f"<b>★ OPTIMAL</b><br>{opt_r['label']}<br>"
                    f"Median CAGR: {opt_r['median_cagr']*100:.2f}%<br>"
                    f"Worst MDD: {opt_r['worst_mdd']*100:.1f}%"
                ) if show else None,
                hoverinfo="text" if show else "skip",
            ), row=r_idx, col=c_idx)

        # Axis labels for heatmap panels
        fig.update_xaxes(title_text="MSCI Allocation (%)", ticksuffix="%", row=1, col=1)
        fig.update_yaxes(title_text="Gold Allocation (%)", ticksuffix="%", row=1, col=1)
        fig.update_xaxes(
            title_text="MSCI Allocation (%)<br><sup>UPRO = 100% − MSCI% − Gold%</sup>",
            ticksuffix="%", row=1, col=2,
        )
        fig.update_yaxes(title_text="Gold Allocation (%)", ticksuffix="%", row=1, col=2)

    else:
        # ── 2-asset mode: line + bar panels ①② ────────────────────────────────
        hover_p1 = [
            (f"<b>{r['label']}</b><br>"
             f"Median CAGR : {r['median_cagr']*100:.2f}%<br>"
             f"IQR         : [{r['cagr_p25']*100:.1f}%, {r['cagr_p75']*100:.1f}%]<br>"
             f"Worst CAGR  : {r['worst_cagr']*100:.2f}%<br>"
             f"Feasible    : {'✓ YES' if r['feasible'] else '✗ NO'}")
            for _, r in stats.iterrows()
        ]

        # Panel ①: CAGR Profile
        fig.add_trace(go.Scatter(
            x=np.concatenate([msci_pcts, msci_pcts[::-1]]),
            y=np.concatenate([stats["cagr_p75"].values * 100,
                              stats["cagr_p25"].values[::-1] * 100]),
            fill="toself", fillcolor=_PAL["iqr"],
            line=dict(color="rgba(0,0,0,0)"),
            name="IQR (p25–p75)", legendgroup="iqr", showlegend=True,
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=msci_pcts, y=stats["worst_cagr"].values * 100,
            mode="lines",
            line=dict(color=_PAL["infeasible"], dash="dot", width=1.5),
            name="Worst-Case CAGR",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=msci_pcts, y=stats["median_cagr"].values * 100,
            mode="lines+markers",
            line=dict(color=_PAL["feasible"], width=2),
            marker=dict(size=dot_sizes, color=dot_colors, symbol=dot_symbols,
                        line=dict(width=border_w, color="white")),
            name="Median CAGR",
            hovertext=hover_p1, hoverinfo="text",
        ), row=1, col=1)

        fig.add_hline(
            y=spy_med_cagr,
            line=dict(color=_PAL["spy"], dash="dash", width=1.5),
            annotation_text=f"  S&P 500 median: {spy_med_cagr:.1f}%",
            annotation_font=dict(color=_PAL["spy"], size=9),
            row=1, col=1,
        )

        # Panel ②: MDD Profile
        hover_p2 = [
            (f"<b>{r['label']}</b><br>"
             f"Worst MDD  : {r['worst_mdd']*100:.1f}%<br>"
             f"Median MDD : {r['median_mdd']*100:.1f}%<br>"
             f"Breaches   : {int(r['mdd_breaches'])}")
            for _, r in stats.iterrows()
        ]

        fig.add_trace(go.Bar(
            x=msci_pcts,
            y=stats["worst_mdd"].values * 100,
            marker_color=dot_colors,
            name="Worst MDD", showlegend=False,
            hovertext=hover_p2, hoverinfo="text",
        ), row=1, col=2)

        fig.add_hline(
            y=-70,
            line=dict(color=_PAL["infeasible"], dash="dash", width=2),
            annotation_text="  Constraint: −70%",
            annotation_font=dict(color=_PAL["infeasible"], size=9),
            row=1, col=2,
        )

        fig.update_xaxes(title_text="MSCI Allocation (%)", row=1, col=1)
        fig.update_yaxes(title_text="20-Year CAGR (%)", row=1, col=1)
        fig.update_xaxes(
            title_text="MSCI Allocation (%)<br><sup>UPRO = 90% − MSCI%, Gold = 10%</sup>",
            row=1, col=2,
        )
        fig.update_yaxes(title_text="Worst MDD (%)", row=1, col=2)

    # ── Panel ③: Efficiency Frontier ──────────────────────────────────────────
    hover_p3 = [
        (f"<b>{r['label']}</b><br>"
         f"Median CAGR  : {r['median_cagr']*100:.2f}%<br>"
         f"Worst MDD    : {r['worst_mdd']*100:.1f}%<br>"
         f"Beats S&P    : {r['outperformance_rate']:.0%} of windows<br>"
         f"Feasible     : {'✓ YES' if r['feasible'] else '✗ NO'}")
        for _, r in stats.iterrows()
    ]

    fig.add_trace(go.Scatter(
        x=stats["worst_mdd"].values * 100,
        y=stats["median_cagr"].values * 100,
        mode="markers+text",
        marker=dict(
            size=dot_sizes, color=dot_colors, symbol=dot_symbols,
            line=dict(width=border_w, color="white"),
        ),
        text=[f"M{int(m)}%" for m in msci_pcts],
        textposition="top center",
        textfont=dict(size=8, color=_PAL["sub"]),
        hovertext=hover_p3, hoverinfo="text",
        showlegend=False, name="Allocation",
    ), row=2, col=1)

    spy_worst_mdd = results["spy_mdd"].min() * 100
    fig.add_trace(go.Scatter(
        x=[spy_worst_mdd], y=[spy_med_cagr],
        mode="markers+text",
        marker=dict(size=14, color=_PAL["spy"], symbol="diamond",
                    line=dict(width=2, color="white")),
        text=["S&P 500"], textposition="top right",
        textfont=dict(color=_PAL["spy"], size=10),
        name="S&P 500",
        hovertemplate=(
            "<b>S&P 500 (benchmark)</b><br>"
            f"Median CAGR : {spy_med_cagr:.1f}%<br>"
            f"Worst MDD   : {spy_worst_mdd:.1f}%"
            "<extra></extra>"
        ),
    ), row=2, col=1)

    fig.add_vline(
        x=-70, line=dict(color=_PAL["infeasible"], dash="dash", width=1.5),
        row=2, col=1,
    )

    # ── Panel ④: Rolling CAGR Timeline ────────────────────────────────────────
    opt_data = results[results["label"] == optimal_label].sort_values("window_end")

    hover_opt = [
        (f"Window: {r['window_start'].year}–{r['window_end'].year}<br>"
         f"CAGR: {r['cagr']*100:.2f}%  |  MDD: {r['mdd']*100:.1f}%")
        for _, r in opt_data.iterrows()
    ]
    hover_spy = [
        (f"S&P 500  {r['window_start'].year}–{r['window_end'].year}<br>"
         f"CAGR: {r['spy_cagr']*100:.2f}%  |  MDD: {r['spy_mdd']*100:.1f}%")
        for _, r in opt_data.iterrows()
    ]

    fig.add_trace(go.Scatter(
        x=opt_data["window_end"],
        y=opt_data["cagr"] * 100,
        mode="lines",
        line=dict(color=_PAL["optimal"], width=2.5),
        fill="tozeroy", fillcolor=_PAL["opt_fill"],
        name=f"Optimal: {optimal_label}",
        hovertext=hover_opt, hoverinfo="text",
    ), row=2, col=2)

    fig.add_trace(go.Scatter(
        x=opt_data["window_end"],
        y=opt_data["spy_cagr"] * 100,
        mode="lines",
        line=dict(color=_PAL["spy"], width=2, dash="dash"),
        name="S&P 500",
        hovertext=hover_spy, hoverinfo="text",
    ), row=2, col=2)

    # ── Panel ⑤: Summary Table ────────────────────────────────────────────────
    feasible_top = (
        stats[stats["feasible"]]
        .sort_values("median_cagr", ascending=False)
        .head(5)
    )

    spy_worst_mdd_f  = results["spy_mdd"].min()
    spy_worst_cagr_f = results["spy_cagr"].min()

    def _fmt_row(r: dict, is_spy: bool = False) -> list:
        lbl  = r["label"] + ("   ★ OPTIMAL" if r["label"] == optimal_label else "")
        feas = "—" if is_spy else ("✓ Feasible" if r["feasible"] else "✗ Breaches")
        op   = "—" if is_spy else f"{r['outperformance_rate']:.0%}"
        w_cagr = f"{spy_worst_cagr_f*100:.2f}%" if is_spy else f"{r['worst_cagr']*100:.2f}%"
        med_c = spy_med_cagr if is_spy else r["median_cagr"] * 100
        w_mdd  = spy_worst_mdd_f * 100 if is_spy else r["worst_mdd"] * 100
        return [lbl, f"{med_c:.2f}%", w_cagr, f"{w_mdd:.1f}%", op, feas]

    all_rows_data = list(feasible_top.to_dict("records")) + [{
        "label":              "S&P 500 (benchmark)",
        "median_cagr":        spy_med_cagr / 100,
        "worst_cagr":         spy_worst_cagr_f,
        "worst_mdd":          spy_worst_mdd_f,
        "outperformance_rate":float("nan"),
        "feasible":           bool((results["spy_mdd"] >= MDD_CONSTRAINT).all()),
    }]

    table_body = [
        _fmt_row(r, is_spy=(r["label"] == "S&P 500 (benchmark)"))
        for r in all_rows_data
    ]
    col_data = [list(col) for col in zip(*table_body)]

    row_fills = [
        _PAL["row_opt"] if r["label"] == optimal_label
        else _PAL["row_spy"] if r["label"] == "S&P 500 (benchmark)"
        else _PAL["panel"]
        for r in all_rows_data
    ]

    fig.add_trace(go.Table(
        header=dict(
            values=["<b>Allocation</b>", "<b>Median CAGR</b>", "<b>Worst CAGR</b>",
                    "<b>Worst MDD</b>", "<b>Beats S&P 500</b>", "<b>MDD Constraint</b>"],
            fill_color=_PAL["grid"],
            font=dict(color=_PAL["text"], size=12),
            align=["left", "center", "center", "center", "center", "center"],
            height=32,
        ),
        cells=dict(
            values=col_data,
            fill_color=[row_fills] * 6,
            font=dict(color=_PAL["text"], size=11),
            align=["left", "center", "center", "center", "center", "center"],
            height=28,
        ),
    ), row=3, col=1)

    # ── Global Layout ──────────────────────────────────────────────────────────
    opt_m = round(optimal_row["msci_pct"] * 100)
    opt_u = round(optimal_row["upro_pct"] * 100)
    opt_g = round(optimal_row["gold_pct"] * 100)

    _mode_str = (
        "3-Asset Sweep (MSCI + UPRO + Gold)"
        if is_3asset else
        f"MSCI / UPRO Ratio — {opt_g}% Gold Fixed"
    )
    _alloc_str = (
        f"MSCI {opt_m}% / UPRO {opt_u}% / Gold {opt_g}%"
        if is_3asset else
        f"MSCI {opt_m}% / UPRO {opt_u}% / Gold {opt_g}%"
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<b>Optimal Allocation — {_mode_str}, "
                "20-Year Rolling Windows Since 1980</b><br>"
                f"<span style='font-size:13px;color:{_PAL['optimal']}'>"
                f"★  Optimal: {_alloc_str}   │   "
                f"Median CAGR: {_pct(optimal_row['median_cagr'])}   │   "
                f"Worst MDD: {_pct(optimal_row['worst_mdd'])}   │   "
                f"Beats S&P 500: {optimal_row['outperformance_rate']:.0%} of windows"
                "</span>"
            ),
            font=dict(size=17, color=_PAL["text"]),
            x=0.5, xanchor="center",
        ),
        paper_bgcolor=_PAL["bg"],
        plot_bgcolor=_PAL["panel"],
        font=dict(color=_PAL["text"], family="'Courier New', monospace"),
        legend=dict(
            bgcolor=_PAL["panel"], bordercolor=_PAL["grid"], borderwidth=1,
            font=dict(size=10), orientation="h",
            x=0.5, xanchor="center", y=-0.01,
        ),
        height=1150,
        margin=dict(t=130, b=10, l=70, r=70),
    )

    fig.update_xaxes(
        gridcolor=_PAL["grid"], zerolinecolor=_PAL["grid"],
        showgrid=True, tickfont=dict(size=10),
    )
    fig.update_yaxes(
        gridcolor=_PAL["grid"], zerolinecolor=_PAL["grid"],
        showgrid=True, tickfont=dict(size=10), ticksuffix="%",
    )

    # Row-1 axis labels are already set inside the 3-asset branch;
    # only apply the 2-asset labels when not in 3-asset mode.
    if not is_3asset:
        fig.update_xaxes(title_text="MSCI Allocation (%)", row=1, col=1)
        fig.update_yaxes(title_text="20-Year CAGR (%)", row=1, col=1)
        fig.update_xaxes(
            title_text="MSCI Allocation (%)<br><sup>UPRO = 90% − MSCI%, Gold = 10%</sup>",
            row=1, col=2,
        )
        fig.update_yaxes(title_text="Worst MDD (%)", row=1, col=2)
    fig.update_xaxes(title_text="Worst Max Drawdown (%)", row=2, col=1)
    fig.update_yaxes(title_text="Median 20-Year CAGR (%)", row=2, col=1)
    fig.update_xaxes(title_text="Window End Year", row=2, col=2)
    fig.update_yaxes(title_text="20-Year CAGR (%)", row=2, col=2)

    return fig


# ==========================================
# ENTRY POINT
# ==========================================

def main() -> None:
    is_3asset   = "gold" in SWEEP_ASSETS
    mode_label  = (
        "3-asset sweep (MSCI + UPRO + Gold)"
        if is_3asset else
        f"2-asset sweep (MSCI + UPRO, Gold fixed at {GOLD_FIXED*100:.0f}%)"
    )
    print("=" * 65)
    print(f"  MSCI / UPRO RATIO OPTIMIZER  —  MDD ≤ 70%")
    print(f"  Mode: {mode_label}")
    print("=" * 65)

    # ── 1. Load ───────────────────────────────────────────────────────────────
    print("\n[1/4] Loading market data...")
    assets = load_market_data()
    assets = assets.loc[START_DATE:].ffill().dropna()
    print(f"      {assets.index[0].date()} → {assets.index[-1].date()} "
          f"({len(assets):,} trading days)")

    # ── 2. Benchmark core engine ──────────────────────────────────────────────
    print("\n[2/4] Benchmarking core engine (500 reps, 20-year window)...")
    _bench = assets.iloc[:WINDOW_DAYS].copy()
    _alloc = {"msci": 0.45, "upro": 0.45, "gold": 0.10}

    t_ms = timeit.timeit(
        lambda: calculate_metrics(
            _bench[["msci", "upro", "gold"]], is_rebalanced=True, weights=_alloc
        ),
        number=500,
    ) / 500 * 1000

    grid_len    = len(build_allocation_grid())
    limit_start = assets.index[-1] - pd.DateOffset(years=ROLLING_WINDOW_YEARS)
    n_windows   = len(assets.loc[START_DATE:limit_start].index[::WINDOW_STEP_DAYS])
    est_serial  = t_ms * grid_len * n_windows / 1000
    n_cores     = os.cpu_count() or 1

    print(f"      {t_ms:.3f} ms/call")
    print(f"      Grid size              : {grid_len} allocations")
    print(f"      Single-thread estimate : {est_serial:.1f} s "
          f"({grid_len} allocs × {n_windows} windows)")
    print(f"      Parallel estimate      : ~{est_serial / n_cores:.1f} s "
          f"({n_cores} cores)")

    # ── 3. Run optimization ───────────────────────────────────────────────────
    print("\n[3/4] Running allocation sweep...")
    t0      = timeit.default_timer()
    results = run_optimization(assets)
    elapsed = timeit.default_timer() - t0

    print(f"      Completed in {elapsed:.2f}s "
          f"({len(results):,} valid (allocation, window) pairs)")

    stats                     = compute_allocation_stats(results)
    optimal_label, optimal_row = find_optimal(stats)
    n_feasible                = int(stats["feasible"].sum())

    # ── 4. Console summary ────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  RESULTS")
    print("=" * 65)
    print(f"\n  Feasible allocations (ALL windows MDD ≤ 70%): "
          f"{n_feasible} / {len(stats)}")

    gold_note = (
        f"Gold swept — optimal at {optimal_row['gold_pct']*100:.0f}%"
        if is_3asset else
        f"Gold fixed at {GOLD_FIXED*100:.0f}%"
    )
    print(f"\n  ★  OPTIMAL: {optimal_label}  ({gold_note})")
    for k, v in [
        ("Median CAGR",   _pct(optimal_row["median_cagr"])),
        ("Mean CAGR",     _pct(optimal_row["mean_cagr"])),
        ("Worst CAGR",    _pct(optimal_row["worst_cagr"])),
        ("Best CAGR",     _pct(optimal_row["best_cagr"])),
        ("Worst MDD",     _pct(optimal_row["worst_mdd"])),
        ("Beats S&P 500", f"{optimal_row['outperformance_rate']:.0%} of windows"),
        ("MDD Breaches",  str(int(optimal_row["mdd_breaches"]))),
    ]:
        print(f"     {k:<18} {v}")

    print(f"\n  S&P 500 Benchmark:")
    print(f"     Median CAGR       {_pct(optimal_row['spy_median_cagr'])}")
    print(f"     Worst MDD         {_pct(results['spy_mdd'].min())}")

    header = f"  {'':>2}  {'Allocation':<30}  {'Med CAGR':>9}  {'Worst':>7}  {'Worst MDD':>9}  {'Beats S&P':>9}"
    print(f"\n  Top Feasible Allocations (by Median CAGR):")
    print(header)
    print("  " + "─" * 72)
    for _, r in (
        stats[stats["feasible"]]
        .sort_values("median_cagr", ascending=False)
        .head(8)
        .iterrows()
    ):
        star = " ★" if r["label"] == optimal_label else "  "
        print(
            f"{star}  {r['label']:<30}  "
            f"{r['median_cagr']*100:>8.2f}%  "
            f"{r['worst_cagr']*100:>6.2f}%  "
            f"{r['worst_mdd']*100:>8.1f}%  "
            f"{r['outperformance_rate']:>8.0%}"
        )

    # ── 5. Render dashboard ───────────────────────────────────────────────────
    print("\n[4/4] Rendering interactive dashboard...")
    fig = create_dashboard(results, stats, optimal_label, optimal_row)
    fig.show()
    print("  Dashboard opened in browser. Done.\n")


if __name__ == "__main__":
    main()
