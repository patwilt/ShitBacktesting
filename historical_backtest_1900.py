"""
Historical Backtest Script (1926-Present) - DAILY RESOLUTION
Fetches DAILY market data directly from Ken French's website.
Calculates rolling windows based on trading days.
"""

import pandas as pd
import numpy as np
from tqdm import tqdm
import datetime
import requests
import zipfile
import io

def get_fama_french_daily():
    print("⏳ Downloading Daily Fama-French Market Factors directly...")
    url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
    r = requests.get(url)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    
    with z.open('F-F_Research_Data_Factors_daily.csv') as f:
        df = pd.read_csv(f, skiprows=3, index_col=0)
    
    # Daily files usually have a trailing copy of annual data; clean it up
    df.index = df.index.astype(str).str.strip()
    df = df[df.index.str.len() == 8] # Ensure 8-digit YYYYMMDD
    df.index = pd.to_datetime(df.index, format='%Y%m%d')
    
    df = df.apply(pd.to_numeric, errors='coerce') / 100.0
    return df

def construct_leverage_proxy_daily(market_returns, rf_rates, leverage=3.0, expense_ratio_annual=0.01):
    # Financing costs: (Leverage-1) * (RF + Spread)
    # Plus daily slice of expense ratio
    financing_spread_daily = 0.01 / 252 
    expense_ratio_daily = expense_ratio_annual / 252
    
    leveraged_returns = (leverage * market_returns) - \
                        ((leverage - 1) * (rf_rates + financing_spread_daily)) - \
                        expense_ratio_daily
    return leveraged_returns.clip(lower=-0.99)

def calculate_cagr_daily(returns):
    total_return = (1 + returns).prod()
    # Approx 252 trading days per year
    n_years = len(returns) / 252.0
    return (total_return**(1/n_years) - 1)

def calculate_mdd(returns):
    wealth_index = (1 + returns).cumprod()
    previous_peaks = wealth_index.cummax()
    drawdowns = (wealth_index - previous_peaks) / previous_peaks
    return drawdowns.min()

def run_backtest():
    try:
        data = get_fama_french_daily()
        
        print(f"✅ Data localized. Timeframe: {data.index.min().date()} to {data.index.max().date()}")
        
        # Assets
        data['Market_TR'] = data['Mkt-RF'] + data['RF']
        data['UPRO_TR'] = construct_leverage_proxy_daily(data['Market_TR'], data['RF'])
        data['SPY_TR'] = data['Market_TR']
        
        # Since daily bond data is not easily accessible via FF direct link (usually monthly)
        # We continue using the RF + Term Premium proxy. 
        # Daily Term Premium (2% / 252 days)
        term_premium_daily = 0.02 / 252
        data['Gold_Proxy_TR'] = data['RF'] + term_premium_daily
        
        # Strategies
        data['Strat_50_50'] = 0.5 * data['SPY_TR'] + 0.5 * data['Gold_Proxy_TR']
        data['Strat_15_15_70'] = 0.15 * data['UPRO_TR'] + 0.15 * data['Gold_Proxy_TR'] + 0.70 * data['SPY_TR']
        
        window_years = 50
        # approx 252 trading days per year
        window_days = int(window_years * 252)
        results = []
        
        strategies = {
            'Strat_50_50': 'Strat_50_50',
            'Strat_15_15_70': 'Strat_15_15_70',
            'UPRO_Proxy': 'UPRO_TR',
            'SPY_Proxy': 'SPY_TR'
        }

        print(f"🔄 Running rolling {window_years}-year backtest (DAILY resolution)...")
        # Step every 5 days (weekly) to keep calculation time reasonable while maintaining daily fidelity
        step = 5 
        
        total_steps = range(window_days, len(data), step)
        
        for i in tqdm(total_steps):
            window_data = data.iloc[i-window_days:i]
            row = {'Window_End_Date': data.index[i].date()}
            for label, col in strategies.items():
                row[f'{label}_CAGR'] = calculate_cagr_daily(window_data[col])
                row[f'{label}_MDD'] = calculate_mdd(window_data[col])
            results.append(row)

        results_df = pd.DataFrame(results)
        results_df.to_csv('rolling_stats_results_1900.csv', index=False)
        print(f"✅ Results saved to 'rolling_stats_results_1900.csv' ({len(results_df)} datapoints)")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_backtest()
