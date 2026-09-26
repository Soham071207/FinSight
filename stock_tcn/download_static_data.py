import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

DATA_DIR = "data"
END_DATE = "2026-06-22"
HISTORY_YEARS = 5

# ── All 50 NIFTY-50 constituents ──────────────────────────────────────────────
NIFTY50_TICKERS = [
    # IT
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "LTIM.NS",
    # Banking & Financial Services
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "INDUSINDBK.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    # Energy
    "RELIANCE.NS", "ONGC.NS", "BPCL.NS",
    # Auto
    "MARUTI.NS", "M&M.NS", "TATAMOTORS.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS",
    # Pharma
    "SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    # FMCG
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
    # Metals & Mining
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "COALINDIA.NS", "UPL.NS",
    # Infrastructure & Capital Goods
    "LT.NS", "NTPC.NS", "POWERGRID.NS", "BHARTIARTL.NS",
    # Consumer
    "ASIANPAINT.NS", "TITAN.NS",
    # Cement
    "ULTRACEMCO.NS", "GRASIM.NS",
    # Conglomerates
    "ADANIENT.NS", "ADANIPORTS.NS",
]

# ── Benchmark & Macro series ─────────────────────────────────────────────────
MACRO_TICKERS = [
    "^NSEI",       # NIFTY 50 index (benchmark)
    "^INDIAVIX",   # India VIX
    "USDINR=X",    # USD/INR exchange rate
]

TICKERS = NIFTY50_TICKERS + MACRO_TICKERS

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
