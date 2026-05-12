# Dodgey Investing Code

> *Over every rolling N-year period in history, how did a hybrid leveraged portfolio compare to plain index investing?*

---

## Pipeline

```
data_downloader.py          →  data/market_data/
rolling_backtest_suite.py   →  data/BT_*/rolling_msci_strategies_results.csv
visual_backtest_report.ipynb     →  charts & summary stats
strategy_evaluator.py       →  Streamlit FI projection app (optional)
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

### 3. Run the backtest

```bash
python rolling_backtest_suite.py
```

Output is written to a timestamped folder:

```
data/BT_30y_1987-01-01_to_<today>_<timestamp>/rolling_msci_strategies_results.csv
```

Key settings at the top of `rolling_backtest_suite.py`:

| Variable | Default | Description |
|---|---|---|
| `ROLLING_WINDOW_YEARS` | `30` | Length of each rolling window |
| `START_DATE` | `1987-01-01` | Earliest window start date |
| `DATA_FOLDER` | `data/market_data` | Input data location |

### 4. Visualise

Open `rolling_Cagr_sp20.ipynb` in Jupyter and run all cells. The first cell
lists all available backtest runs and prompts you to select one (defaults to
the newest).

Charts produced:
- Summary statistics table (median CAGR, median MDD)
- KDE distributions of rolling CAGR and MDD
- Rolling CAGR timeline across history
- CDF of drawdown severity

### 5. FI Projector (optional)

```bash
streamlit run strategy_evaluator.py
```

Upload a backtest CSV (or let the app auto-detect the latest one), then
configure salary, DCA amount, and investment horizon to find your personal
Coast-FI and full-FI crossover years.

---

## Strategies

| | Description | Rebalance |
|---|---|---|
| **S1** | 70% S&P 500 / 15% 3× Leveraged / 15% Gold | Quarterly |
| **S2** | 100% S&P 500 | — |
| **S3** | 70% MSCI World / 15% 3× Leveraged / 15% Gold | Quarterly |
| **S4** | 100% MSCI World | — |

---

## Data & Assumptions

Real market data only goes back so far, so the suite builds a synthetic history
where needed.

| Asset | Real data (Yahoo) | Synthetic fill |
|---|---|---|
| S&P 500 TR | `^GSPC` from ~1928 | 1.5% annual dividend yield added |
| UPRO proxy | Derived from `^GSPC` | 3× daily return − period-appropriate financing cost |
| Gold | `GC=F` from ~1974 | 1970–80: +12% CAGR; 1980–real start: −2.5% CAGR |
| MSCI World | `IWDA.L` from 2009 | Synthetic from GSPC with era-adjusted alpha |

**UPRO financing cost** uses historical Fed Funds Rates (FRED) rather than a
flat rate, so the model correctly penalises the 2022–24 hiking cycle (~10.5%
total annual cost) and rewards the 2009–15 ZIRP era (~1.5% total annual cost):

```
annual_cost = (L-1) × (r_f + 0.30%) + 0.91% expense ratio
```

---

## Limitations

These are intentional simplifications, not bugs.

1. **Pre-1974 gold data** is a constant-return proxy. Results from windows
   starting before 1974 should be treated as directional only.

2. **UPRO intraday slippage** is not modelled. UPRO rebalances its swap
   exposure intraday on volatile days, incurring small additional drag
   (~5–10 bps/year). This has a negligible effect on long rolling windows.

3. **MSCI World pre-2009** is synthetic. The alpha adjustments (+1%/yr
   pre-1990 for the Japan boom, −2%/yr post-2010 for US tech dominance) are
   calibrated estimates, not real returns.

4. **No transaction costs or taxes** are modelled on rebalancing.

---

## Tests

```bash
python -m pytest tests/ -v
```

36 tests covering the backtest engine, data helpers, and the Streamlit app's
financial maths. All should pass in under a minute.
