import os
import sys
import logging
import warnings
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import tensorflow as tf

# Configure path so we can import from both current and backup
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
import config

# Import new model and TS-TCC
from tcn_model import TCNPredictor as NewTCNPredictor
from ts_tcc import fine_tune_from_pretrained

def get_old_tcn_module():
    import importlib.util
    backup_path = os.path.join(base_dir, "tcn_backup", "tcn_model.py")
    if not os.path.exists(backup_path):
        backup_path = os.path.join(base_dir, "..", "STOCK", "tcn_model.py")
    spec = importlib.util.spec_from_file_location("old_tcn", backup_path)
    old_tcn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_tcn)
    return old_tcn

def evaluate_model(y_true, y_pred_prob):
    y_pred = (y_pred_prob > 0.5).astype(int)
    return {
        "Accuracy": accuracy_score(y_true, y_pred),
        "Precision": precision_score(y_true, y_pred, zero_division=0),
        "Recall": recall_score(y_true, y_pred, zero_division=0),
        "F1": f1_score(y_true, y_pred, zero_division=0),
        "AUC": roc_auc_score(y_true, y_pred_prob)
    }

def main():
    print("=" * 60)
    print("  TCN COMPARISON (50 TICKERS): Old vs New (TCN-MHA+PE)")
    print("=" * 60)
    
    tickers = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS",
        "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
        "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "TATASTEEL.NS",
        "HCLTECH.NS", "BAJAJFINSV.NS", "NTPC.NS", "POWERGRID.NS", "INDUSINDBK.NS",
        "NESTLEIND.NS",  "M&M.NS",        "GRASIM.NS",    "TECHM.NS",      "JSWSTEEL.NS",
        "CIPLA.NS",      "ADANIENT.NS",   "ADANIPORTS.NS","TATAMOTORS.NS", "HDFCLIFE.NS",
        "SBILIFE.NS",    "ONGC.NS",       "HINDALCO.NS",  "DRREDDY.NS",    "EICHERMOT.NS",
        "BAJAJ-AUTO.NS", "DIVISLAB.NS",   "BRITANNIA.NS", "APOLLOHOSP.NS", "COALINDIA.NS",
        "TATACONSUM.NS", "HEROMOTOCO.NS", "UPL.NS",       "BPCL.NS",       "LTIM.NS"
    ]
    
    config.CONFIG["history_window_years"] = 3
    config.CONFIG["tickers"] = tickers
    
    print(f"\n[1] Fetching data for {len(tickers)} tickers...")
    dp = DataPipeline()
    fe = FeatureEngine()
    
    all_train_df = []
    all_test_df = []
    
    for ticker in tickers:
        try:
            raw = dp.fetch_data(ticker)
            if raw is None or raw.empty:
                continue
                
            df = fe.compute_all(raw)
            df["Target"] = (df["Close"].pct_change().shift(-1) > 0).astype(int)
            df = df.dropna()
            
            split_idx = int(len(df) * 0.8)
            all_train_df.append(df.iloc[:split_idx])
            all_test_df.append(df.iloc[split_idx:])
        except Exception as e:
            print(f"  WARNING: Skipping {ticker} due to error: {e}")
            
    print(f"[2] Concatenating DataFrames...")
    train_df = pd.concat(all_train_df).reset_index(drop=True)
    test_df = pd.concat(all_test_df).reset_index(drop=True)
    
    feature_cols = [c for c in train_df.columns if c not in ["Date", "Target", "regime", "garch_vol", "daily_sentiment_score"]]
    
    X_train = train_df[feature_cols]
    y_train = train_df["Target"]
    y_test = test_df["Target"]
    
    print(f"\n[3] Training OLD TCN on {len(X_train)} aggregate samples...")
    old_tcn = get_old_tcn_module()
    
    old_model = old_tcn.TCNPredictor(feature_cols)
    old_model.epochs = 5
    old_model.fit(train_df, y_train)
    old_probs = old_model.predict(test_df).dropna()
    y_true_old = y_test.loc[old_probs.index]
    old_metrics = evaluate_model(y_true_old, old_probs)
    
    print(f"\n[4] Training NEW TCN-MHA+PE on {len(X_train)} aggregate samples...")
    new_model = NewTCNPredictor(feature_cols)
    new_model.epochs = 5
    new_model.fit(train_df, y_train)
    new_probs = new_model.predict(test_df).dropna()
    y_true_new = y_test.loc[new_probs.index]
    new_metrics = evaluate_model(y_true_new, new_probs)
    
    print(f"\n[5] Fine-tuning TS-TCC Pre-Trained TCN-MHA+PE on {len(X_train)} samples...")
    ts_tcc_model = NewTCNPredictor(feature_cols)
    # We use 5 epochs to match the other runs for a fair comparison
    weights_path = os.path.join(base_dir, "ts_tcc_encoder.weights.h5")
    if os.path.exists(weights_path):
        fine_tune_from_pretrained(
            tcn_predictor=ts_tcc_model,
            pretrained_weights_path=weights_path,
            X_train_df=train_df,
            y_train=y_train,
            finetune_epochs=5,
            finetune_lr=1e-4
        )
        ts_tcc_probs = ts_tcc_model.predict(test_df).dropna()
        y_true_tstcc = y_test.loc[ts_tcc_probs.index]
        tstcc_metrics = evaluate_model(y_true_tstcc, ts_tcc_probs)
    else:
        print("  WARNING: TS-TCC weights not found. Skipping 3rd model.")
        tstcc_metrics = None
    
    print("\n" + "=" * 90)
    print("  COMPARISON RESULTS (50-Ticker Out-of-Sample Test)")
    print("=" * 90)
    print(f"{'Metric':<12} | {'Old TCN Baseline':<20} | {'New TCN-MHA+PE':<20} | {'TS-TCC Fine-Tuned':<20}")
    print("-" * 90)
    for k in old_metrics.keys():
        old_val = old_metrics[k]
        new_val = new_metrics[k]
        diff_new = new_val - old_val
        ind_new = "(+)" if diff_new > 0 else "(-)" if diff_new < 0 else "( )"
        
        tstcc_str = ""
        if tstcc_metrics:
            tstcc_val = tstcc_metrics[k]
            diff_tstcc = tstcc_val - old_val
            ind_tstcc = "(+)" if diff_tstcc > 0 else "(-)" if diff_tstcc < 0 else "( )"
            tstcc_str = f"| {tstcc_val:.4f}  {ind_tstcc} ({diff_tstcc:+.4f})"
            
        print(f"{k:<12} | {old_val:.4f}               | {new_val:.4f}  {ind_new} ({diff_new:+.4f}) {tstcc_str}")
    
    print("\nDone.")

if __name__ == "__main__":
    main()
