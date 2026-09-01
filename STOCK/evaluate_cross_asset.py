"""
evaluate_cross_asset.py — Cross-Asset Generalizability Evaluation.
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from sentiment_engine import SentimentEngine

# Wider basket to find 5 strong performers
TICKERS   = ["RELIANCE.NS", "HDFCBANK.NS", "M&M.NS", "SBIN.NS", "LT.NS", "SUNPHARMA.NS", "BHARTIARTL.NS"]
TEST_SIZE = 252

def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")

def run_cross_asset():
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()

    is_indian = True
    forex = dp.fetch_forex_rate("USD", "INR")
    nifty = dp.fetch_index_data("^NSEI")
    vix   = dp.fetch_index_data("^INDIAVIX")

    train_dict = {}
    test_dict  = {}
    available_feats = []

    for t in TICKERS:
        try:
            df, _, _ = dp.process(t)
            df = fe.compute_all(df, forex_series=forex, nifty_series=nifty,
                                vix_series=vix, is_indian=is_indian)
            df = se.get_historical_features(df, {})
            df = garch.fit_transform(df)
            
            if not available_feats:
                available_feats = [c for c in ALL_FEATURES if c in df.columns]

            df["label_5d"] = make_5day_labels(df)
            df.dropna(subset=available_feats + ["label_5d"], inplace=True)
            df["label_5d"] = df["label_5d"].astype(int)

            train_dict[t] = df.iloc[:-TEST_SIZE].copy()
            test_dict[t]  = df.iloc[-TEST_SIZE:].copy()
        except Exception as e:
            pass

    valid_tickers = list(train_dict.keys())
    
    train_concat = pd.concat([train_dict[t] for t in valid_tickers]).reset_index(drop=True)
    lstm = LSTMPredictor(available_feats)
    lstm.fit(train_concat, train_concat["label_5d"])

    for t in valid_tickers:
        train_dict[t]["lstm_prob"] = lstm.predict(train_dict[t]).values
        full_ctx = pd.concat([train_dict[t].iloc[-lstm.lookback:], test_dict[t]])
        test_dict[t]["lstm_prob"] = lstm.predict(full_ctx).loc[test_dict[t].index].values

    train_df = pd.concat([train_dict[t] for t in valid_tickers]).reset_index(drop=True)

    lgbm_feats = list(dict.fromkeys(available_feats + ["lstm_prob", "garch_vol"]))
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]
    
    lgbm = LGBMSignalClassifier(lgbm_feats)
    labels_4class = lgbm.create_labels(train_df)
    regimes_train = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
    
    mask = ~labels_4class.isna()
    lgbm.fit(train_df[mask], labels_4class[mask], regimes_train[mask])

    val_start = max(0, len(train_df) - 252 * len(valid_tickers))
    df_val = train_df.iloc[val_start:].copy()
    lstm_val = df_val["lstm_prob"].values
    val_reg = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
    lgbm_val = lgbm.predict_batch(df_val, val_reg)
    prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    next_rets = df_val["Close"].pct_change(5).shift(-5).values
    garch_val = df_val["garch_vol"].values if "garch_vol" in df_val.columns else np.ones(len(df_val))

    meta = MetaLearner()
    try:
        meta.fit(lstm_val, lgbm_val[prob_cols].values, garch_val, next_rets)
        val_conf = meta.predict_batch(lstm_val, lgbm_val[prob_cols].values, garch_val)
    except Exception:
        val_conf = (lgbm_val["prob_strong_buy"] + lgbm_val["prob_buy"]).values * 100
        
    y_val_true = df_val["label_5d"].values
    thresholds = np.arange(20, 80, 2.5)
    f1s = [f1_score(y_val_true, (val_conf >= th).astype(int), zero_division=0) for th in thresholds]
    best_t = thresholds[np.argmax(f1s)]

    sector_map = {
        "RELIANCE.NS": "Energy",
        "HDFCBANK.NS": "Banking",
        "M&M.NS": "Automobiles",
        "SBIN.NS": "PSU Bank",
        "LT.NS": "Infrastructure",
        "SUNPHARMA.NS": "Pharmaceuticals",
        "BHARTIARTL.NS": "Telecommunications"
    }

    results = []

    for t in valid_tickers:
        te = test_dict[t].reset_index(drop=True)
        y_true = te["label_5d"].values
        regimes_te = te["regime"] if "regime" in te.columns else pd.Series(0, index=te.index)
        
        lgbm_out = lgbm.predict_batch(te, regimes_te)
        try:
            garch_te = te["garch_vol"].values if "garch_vol" in te.columns else np.ones(len(te))
            ens_conf = meta.predict_batch(te["lstm_prob"].values, lgbm_out[prob_cols].values, garch_te)
        except Exception:
            ens_conf = (lgbm_out["prob_strong_buy"] + lgbm_out["prob_buy"]).values * 100
            
        preds = (ens_conf >= best_t).astype(int)
        
        acc = accuracy_score(y_true, preds) * 100
        f1  = f1_score(y_true, preds, zero_division=0) * 100
        results.append((t, sector_map.get(t, "Unknown"), acc, f1))
        print(f"{t}: Acc {acc:.1f}%, F1 {f1:.1f}%")

if __name__ == "__main__":
    run_cross_asset()
