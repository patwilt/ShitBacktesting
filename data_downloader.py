import bt
import pandas as pd
import os
import time
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
DATA_FOLDER = "data/market_data"
# Tickers prioritized for length. 
# 'GC=F' (Gold Futures) typically has much longer history than 'gold' or 'GLD' on Yahoo.
TICKERS = {'^GSPC': 'gspc', '^OEX': 'oex', 'GC=F': 'gold', 'IWDA.L': 'msci_real'}
START_DATE = '1900-01-01'
END_DATE = datetime.now().strftime('%Y-%m-%d')

def download_data():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    
    print(f"🚀 Starting Multi-Source Download (VPN Active)...")
    
    for symbol, filename in TICKERS.items():
        try:
            print(f"📥 Fetching {symbol}...")
            df = bt.get(symbol, start=START_DATE, end=END_DATE)
            
            if not df.empty:
                actual_start = df.index.min().strftime('%Y-%m-%d')
                actual_end = df.index.max().strftime('%Y-%m-%d')
                print(f"  🏁 Result: {actual_start} to {actual_end} ({len(df)} rows)")
                
                path = os.path.join(DATA_FOLDER, f"{filename}.csv")
                df.to_csv(path)
                print(f"  ✅ Saved {symbol} to {path}\n")
            else:
                print(f"  ⚠️ No data returned for {symbol}\n")
                
            time.sleep(5) 
        except Exception as e:
            print(f"  ❌ Error downloading {symbol}: {e}\n")

if __name__ == "__main__":
    download_data()
