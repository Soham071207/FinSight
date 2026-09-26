"""
run_sector_validation.py -- Fix B8: Partial Leave-One-Sector-Out Validation
Trains on 2 sectors, tests on 1 unseen sector to prove cross-sectional generalization.
"""
import warnings, os
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from config import ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from lgbm_model import LGBMSignalClassifier

SECTORS = {
    "IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
    "Financial": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS"],
    "Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"]
}

def make_binary_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index)

def fetch_data():
    dp = DataPipeline()
    fe = FeatureEngine()
    garch = GARCHModel()
    
    forex = dp.fetch_forex_rate("USD", "INR")
    nifty = dp.fetch_index_data("^NSEI")
    vix   = dp.fetch_index_data("^INDIAVIX")
    
    sector_dfs = {"IT": [], "Financial": [], "Pharma": []}
    
    for sec_name, tickers in SECTORS.items():
        print(f"Loading data for {sec_name}...")
        for t in tickers:
            try:
                df, _, _ = dp.process(t)
                df = fe.compute_all(df, forex, True)
                df = garch.fit_transform(df)
                df["label_binary"] = make_binary_labels(df)
                avail = [c for c in ALL_FEATURES if c in df.columns]
                df = df.dropna(subset=avail + ["label_binary"])
                if len(df) > 500:
                    sector_dfs[sec_name].append(df)
            except Exception as e:
                print(f"  Failed {t}: {e}")
                
    # Combine dfs
    for k in sector_dfs:
        if sector_dfs[k]:
            sector_dfs[k] = pd.concat(sector_dfs[k]).reset_index(drop=True)
        else:
            sector_dfs[k] = pd.DataFrame()
            
    return sector_dfs

def main():
    sector_dfs = fetch_data()
    avail = [c for c in ALL_FEATURES if c in sector_dfs["IT"].columns]
    
    print("\n" + "="*50)
    print("  Leave-One-Sector-Out Validation (LightGBM)")
    print("="*50)
    
    for target_sec in SECTORS.keys():
        train_dfs = [sector_dfs[k] for k in SECTORS.keys() if k != target_sec and not sector_dfs[k].empty]
        if not train_dfs: continue
        
        train_df = pd.concat(train_dfs).reset_index(drop=True)
        test_df = sector_dfs[target_sec]
        
        if test_df.empty or train_df.empty:
            continue
            
        lgbm = LGBMSignalClassifier(feature_cols=avail)
        y_train = lgbm.create_labels(train_df)
        
        # Train on N-1 sectors
        lgbm.tune(train_df[avail], y_train, train_df.get("regime", pd.Series(0, index=train_df.index)))
        lgbm.fit(train_df[avail], y_train, train_df.get("regime", pd.Series(0, index=train_df.index)))
        
        # Test on 1 sector
        p_lgbm_test = lgbm.predict_batch(test_df[avail], test_df.get("regime", pd.Series(0, index=test_df.index)))
        y_test = test_df["label_binary"].values
        
        auc = roc_auc_score(y_test, p_lgbm_test["prob_buy"] + p_lgbm_test["prob_strong_buy"])
        print(f"  Target Sector: {target_sec:10s} | Held-out AUC: {auc:.4f}")

if __name__ == "__main__":
    main()
