# Dodgey Investing Code

> *Over every rolling N-year period in history, how did a hybrid leveraged portfolio compare to plain index investing?*

---

## Pipeline

```
data_downloader.py          →  data/market_data/
rolling_backtest_suite.py   →  data/BT_*/rolling_msci_strategies_results.csv
visual_backtest_report.ipynb     →  institutional-grade charts & summary stats
```

---

## Usage

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Download market data

```bash
python data_downloader.py
```

Fetches `^GSPC`, `GC=F` (Gold), and `IWDA.L` (MSCI World) from Yahoo Finance
and saves CSVs to `data/market_data/`.

> **Tip:** A VPN improves Yahoo Finance reliability.

### 3. Configure & run the backtest

All knobs are at the top of `rolling_backtest_suite.py` — no digging into functions required.

```bash
python rolling_backtest_suite.py
```

Output is written to a timestamped folder:

```
data/BT_<window>y_<start>_to_<end>_<timestamp>/rolling_msci_strategies_results.csv
```

#### Backtest window settings

| Variable | Default | Description |
|---|---|---|
| `ROLLING_WINDOW_YEARS` | `20` | Length of each rolling window |
| `START_DATE` | `1960-01-01` | Earliest window start (suggest 1980+ for gold) |
| `REBALANCE_DAYS` | `63` | Rebalance frequency in trading days (~quarterly) |
| `DATA_FOLDER` | `data/market_data` | Input data location |

#### Strategy weights

Change the weights and the CSV column names update automatically — no manual rename required.

```python
# S1: Hybrid SPY
S1_WEIGHTS = {"spy": 0.70, "upro": 0.15, "gold": 0.15}
# → column name becomes "Hybrid SPY (70/15/15)"

# S3: Hybrid MSCI
S3_WEIGHTS = {"msci": 0.70, "upro": 0.15, "gold": 0.15}
# → column name becomes "Hybrid MSCI (70/15/15)"
```

#### Asset model assumptions

| Variable | Default | Description |
|---|---|---|
| `SPY_DIVIDEND_YIELD` | `0.015` | Annual dividend yield added to S&P 500 price returns |
| `UPRO_LEVERAGE` | `3.0` | Leverage multiplier for the UPRO proxy |
| `UPRO_EXPENSE_RATIO` | `0.0091` | UPRO annual expense ratio (0.91%) |
| `UPRO_FINANCING_SPREAD` | `0.003` | Overnight repo spread above Fed Funds Rate |
| `MSCI_DIVIDEND_YIELD` | `0.02` | Annual dividend yield for MSCI World |
| `MSCI_PRE1990_ALPHA` | `0.01` | +1%/yr Japan boom adjustment pre-1990 |
| `MSCI_POST2010_ALPHA` | `-0.02` | −2%/yr US tech dominance drag post-2010 |
| `GOLD_PRE1980_CAGR` | `0.12` | Synthetic gold return pre-1980 (USD decoupling era) |
| `GOLD_1980_TO_REAL_CAGR` | `-0.025` | Synthetic gold return 1980 → real data start |

### 4. Visualise

Open `visual_backtest_report.ipynb` in Jupyter and run all cells. The first cell
lists all available backtest runs newest-first and prompts you to select one
(press Enter to accept the default — most recent).

The notebook produces an institutional-grade interactive report:

| Section | Description |
|---|---|
| **Hero Metric Banner** | Median CAGR, P25–P75 expected range, Worst MDD, and Sharpe Proxy for every strategy |
| **Rolling CAGR Timeline** | Plotly line chart; green/crimson shading marks above/below median regimes |
| **Performance Distributions** | Violin + Box plots showing the full probability density of outcomes |
| **Underwater Drawdown Chart** | Crimson fill area chart of Max Drawdown over time |
| **Pain Period Summary** | Table of the 10 longest consecutive stretches in the worst-quartile drawdown regime |
| **CDF of Max Drawdown** | Probability of experiencing a given loss; −20% and −40% risk zones marked |
| **Monthly Alpha Map** | Plotly heatmap of median CAGR by year × calendar month |

All charts use Plotly (fully interactive — zoom, hover, toggle series).

---

## Strategies

The two hybrid strategies and their benchmarks. S1/S3 weights are configurable
in `rolling_backtest_suite.py` — see above.

| | Description | Rebalance |
|---|---|---|
| **S1** | Hybrid SPY — configurable blend of S&P 500 / 3× Leveraged / Gold | Quarterly |
| **S2** | 100% S&P 500 (benchmark) | — |
| **S3** | Hybrid MSCI — same structure, MSCI World instead of S&P 500 | Quarterly |
| **S4** | 100% MSCI World (benchmark) | — |

---

## Data & Assumptions

Real market data only goes back so far, so the suite builds a synthetic history
where needed.

| Asset | Real data (Yahoo) | Synthetic fill |
|---|---|---|
| S&P 500 TR | `^GSPC` from ~1928 | `SPY_DIVIDEND_YIELD` added to price returns |
| UPRO proxy | Derived from `^GSPC` | `UPRO_LEVERAGE`× daily return − period-appropriate financing cost |
| Gold | `GC=F` from ~1974 | pre-1980: `GOLD_PRE1980_CAGR`; 1980→real: `GOLD_1980_TO_REAL_CAGR` |
| MSCI World | `IWDA.L` from 2009 | Synthetic from GSPC with `MSCI_PRE1990_ALPHA` / `MSCI_POST2010_ALPHA` |

**UPRO financing cost** uses historical Fed Funds Rates (FRED) rather than a
flat rate, so the model correctly penalises the 2022–24 hiking cycle (~10.5%
total annual cost) and rewards the 2009–15 ZIRP era (~1.5% total annual cost):

```
annual_cost = (L-1) × (r_f + UPRO_FINANCING_SPREAD) + UPRO_EXPENSE_RATIO
```

---

## Limitations

These are intentional simplifications, not bugs.

1. **Pre-1974 gold data** is a constant-return proxy. Results from windows
   starting before 1974 should be treated as directional only.

2. **UPRO intraday slippage** is not modelled. UPRO rebalances its swap
   exposure intraday on volatile days, incurring small additional drag
   (~5–10 bps/year). This has a negligible effect on long rolling windows.

3. **MSCI World pre-2009** is synthetic. The alpha adjustments are calibrated
   estimates, not real returns. Adjust `MSCI_PRE1990_ALPHA` and
   `MSCI_POST2010_ALPHA` if you have a different view.

4. **No transaction costs or taxes** are modelled on rebalancing.

---

## Tests

```bash
python -m pytest tests/ -v
```

Tests covering the backtest engine, data helpers, and financial maths.
