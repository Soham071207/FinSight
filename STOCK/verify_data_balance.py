import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np

from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from lgbm_model import LGBMSignalClassifier

def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")

def run():
    print("="*60)
    print("DATA INTEGRITY AND BALANCE VERIFICATION")
    print("="*60)
    
    ticker = "RELIANCE.NS"
    dp = DataPipeline()
    fe = FeatureEngine()
    
    # 1. Fetch Data
    print(f"\n[1] Fetching raw data for {ticker}...")
    df, market, _ = dp.process(ticker)
    print(f"Raw rows: {len(df)}")
    
    # 2. Build Features
    print("\n[2] Building features...")
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)
    
    df = fe.compute_all(df, forex_series=forex, nifty_series=nifty, vix_series=vix, is_indian=is_indian)
    
    # Check NaN values in features
    available = [c for c in ALL_FEATURES if c in df.columns]
    missing = df[available].isna().sum()
    missing_pct = (missing / len(df)) * 100
    high_missing = missing_pct[missing_pct > 10]
    
    print("\n--- Missing Value Analysis ---")
    if len(high_missing) > 0:
        print("WARNING: Features with >10% missing values:")
        for feat, pct in high_missing.items():
            print(f"  {feat}: {pct:.1f}% missing")
    else:
        print("PASS: No severe missing data in technical features.")
        
    # 3. Label Balance (LSTM Binary)
    print("\n[3] Checking LSTM Label Balance (5-day return ±0.5% threshold)...")
    df["label_5d"] = make_5day_labels(df)
    valid_binary = df.dropna(subset=["label_5d"])
    binary_counts = valid_binary["label_5d"].value_counts(normalize=True) * 100
    
    print(f"Total valid samples: {len(valid_binary)}")
    print(f"Class 1 (Bullish): {binary_counts.get(1.0, 0):.1f}%")
    print(f"Class 0 (Bearish): {binary_counts.get(0.0, 0):.1f}%")
    
    if abs(binary_counts.get(1.0, 0) - binary_counts.get(0.0, 0)) > 20:
        print("WARNING: High class imbalance in binary labels.")
    else:
        print("PASS: Binary labels are reasonably balanced.")

    # 4. Label Balance (LightGBM 4-Class)
    print("\n[4] Checking LightGBM Label Balance (4-Class)...")
    lgbm_labels = LGBMSignalClassifier.create_labels(df)
    valid_4class = lgbm_labels.dropna()
    class_counts = valid_4class.value_counts(normalize=True).sort_index() * 100
    
    print(f"Total valid samples: {len(valid_4class)}")
    for val, name in LGBMSignalClassifier.LABEL_MAP.items():
        print(f"Class {val} ({name}): {class_counts.get(val, 0):.1f}%")
        
    if class_counts.min() < 5:
        print("WARNING: One or more classes have very low representation (<5%). LGBM class weights (is_unbalance=True) are highly recommended.")
    else:
        print("PASS: 4-class labels have sufficient representation.")

    # 5. Regime Balance
    print("\n[5] Checking Market Regime Distribution...")
    if "regime" in df.columns:
        regime_counts = df["regime"].value_counts(normalize=True).sort_index() * 100
        for r in range(4):
            print(f"Regime {r} ({CONFIG['regime_labels'][r]}): {regime_counts.get(r, 0):.1f}%")
        if regime_counts.min() < 5:
            print("WARNING: Some regimes are very rare. Regime-specific models might fail to train due to lack of data.")
        else:
            print("PASS: Regimes are adequately distributed.")
    else:
        print("WARNING: Regime column not found.")
        
    print("\n" + "="*60)
    
if __name__ == "__main__":
    run()
