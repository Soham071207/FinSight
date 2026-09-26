import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

DATA_DIR = "data"
END_DATE = "2026-06-22"
HISTORY_YEARS = 5

TICKERS = [
    "TCS.NS", "RELIANCE.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBI.NS",
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA",
    "^NSEI", "^INDIAVIX", "USDINR=X"
]

def run():
    os.makedirs(DATA_DIR, exist_ok=True)
    start_date = (datetime.strptime(END_DATE, "%Y-%m-%d") - timedelta(days=HISTORY_YEARS * 365 + 90)).strftime("%Y-%m-%d")
    
    print(f"Downloading data from {start_date} to {END_DATE}")
    
    for ticker in TICKERS:
        try:
            print(f"Fetching {ticker}...")
            df = yf.download(ticker, start=start_date, end=END_DATE, auto_adjust=True, progress=False)
            if df.empty:
                print(f"  -> WARNING: No data for {ticker}")
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                
            out_path = os.path.join(DATA_DIR, f"{ticker.replace('^', '').replace('=', '_')}.parquet")
            df.to_parquet(out_path)
            print(f"  -> Saved {len(df)} rows to {out_path}")
        except Exception as e:
            print(f"  -> Error fetching {ticker}: {e}")

if __name__ == "__main__":
    run()
