"""
compute_fix_15tickers.py - Run pipeline for 7 more tickers and pre-2019 sentiment-free multi-period backtest.
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from sentiment_engine import SentimentEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from sklearn.metrics import accuracy_score, f1_score
from backtest_engine import BacktestEngine
import datetime

def evaluate_ticker(ticker, dp, fe, se, garch):
    try:
        df, _, _ = dp.process(ticker)
        df = fe.compute_all(df, forex_series=dp.fetch_forex_rate("USD", "INR"), 
                            nifty_series=dp.fetch_index_data("^NSEI"), 
                            vix_series=dp.fetch_index_data("^INDIAVIX"), is_indian=True)
        df = se.get_historical_features(df, {})
        df = garch.fit_transform(df)
        
        fwd_ret = df["Close"].pct_change(5).shift(-5)
        df["label_5d"] = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
        
        av_cols = [c for c in ALL_FEATURES if c in df.columns]
        df.dropna(subset=["label_5d"] + av_cols, inplace=True)
        df["label_5d"] = df["label_5d"].astype(int)
        
        if len(df) < 500:
            return None, None
            
        train_df = df.iloc[:-252].copy()
        test_df = df.iloc[-252:].copy()
        
        lstm = LSTMPredictor(av_cols)
        lstm.fit(train_df, train_df["label_5d"])
        
        lgbm = LGBMSignalClassifier(av_cols)
        lgbm.fit(train_df, lgbm.create_labels(train_df), train_df.get("regime", pd.Series(0, index=train_df.index)))
        
        lstm_test = lstm.predict(pd.concat([train_df.iloc[-lstm.lookback:], test_df])).loc[test_df.index]
        lgbm_test = lgbm.predict_batch(test_df, test_df.get("regime", pd.Series(0, index=test_df.index)))
        
        val_start = max(0, len(train_df) - 252)
        lstm_val = lstm.predict(train_df.iloc[val_start:]).values
        lgbm_val = lgbm.predict_batch(train_df.iloc[val_start:], train_df.iloc[val_start:].get("regime", pd.Series(0, index=train_df.iloc[val_start:].index)))
        
        meta = MetaLearner()
        meta.fit(lstm_val, lgbm_val[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values, 
                 train_df["Close"].iloc[val_start:].pct_change(5).shift(-5).values)
        
        conf = meta.predict_batch(lstm_test.values, lgbm_test[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values)
        y_true = test_df["label_5d"].values
        sigs = (conf >= 25.0).astype(int)
        
        acc = accuracy_score(y_true, sigs) * 100
        f1 = f1_score(y_true, sigs, zero_division=0) * 100
        return acc, f1
    except Exception as e:
        print(f"Error on {ticker}: {e}")
        return None, None

def run_multi_period_sentiment_free():
    print("\n" + "="*70)
    print("  Pre-2019 Sentiment-Free Multi-Period Backtest")
    print("="*70)
    dp = DataPipeline()
    fe = FeatureEngine()
    garch = GARCHModel()
    
    # We fetch a long history for RELIANCE
    import yfinance as yf
    raw_df = yf.download("RELIANCE.NS", start="2010-01-01", end="2019-01-01", progress=False)
    if isinstance(raw_df.columns, pd.MultiIndex):
        raw_df.columns = raw_df.columns.droplevel(1)
    
    # Map to standard format
    df = raw_df.copy()
    if 'Adj Close' in df.columns:
        df['Close'] = df['Adj Close']
        
    df = fe.compute_all(df, forex_series=dp.fetch_forex_rate("USD", "INR"), 
                        nifty_series=dp.fetch_index_data("^NSEI"), 
                        vix_series=dp.fetch_index_data("^INDIAVIX"), is_indian=True)
    df = garch.fit_transform(df)
    
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    df["label_5d"] = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    
    # Omit sentiment features
    sentiment_features = ["finbert_sentiment", "vader_sentiment", "hybrid_sentiment", "sentiment_momentum", "news_volume"]
    av_cols = [c for c in ALL_FEATURES if c in df.columns and c not in sentiment_features]
    df.dropna(subset=["label_5d"] + av_cols, inplace=True)
    df["label_5d"] = df["label_5d"].astype(int)
    
    print(f"Total usable days pre-2019 (sentiment-free): {len(df)}")
    
    # Multi-period evaluation
    # Windows of 252 days test, preceded by >= 504 days train
    total_days = len(df)
    window_size = 252
    train_size = 504
    
    windows = []
    current_end = total_days
    
    while current_end - window_size >= train_size:
        test_start = current_end - window_size
        test_end = current_end
        train_start = 0  # Expanding window
        train_end = test_start
        
        train_df = df.iloc[train_start:train_end].copy()
        test_df = df.iloc[test_start:test_end].copy()
        
        try:
            lstm = LSTMPredictor(av_cols)
            lstm.fit(train_df, train_df["label_5d"])
            
            lgbm = LGBMSignalClassifier(av_cols)
            lgbm.fit(train_df, lgbm.create_labels(train_df), train_df.get("regime", pd.Series(0, index=train_df.index)))
            
            lstm_test = lstm.predict(pd.concat([train_df.iloc[-lstm.lookback:], test_df])).loc[test_df.index]
            lgbm_test = lgbm.predict_batch(test_df, test_df.get("regime", pd.Series(0, index=test_df.index)))
            
            val_start = max(0, len(train_df) - 252)
            lstm_val = lstm.predict(train_df.iloc[val_start:]).values
            lgbm_val = lgbm.predict_batch(train_df.iloc[val_start:], train_df.iloc[val_start:].get("regime", pd.Series(0, index=train_df.iloc[val_start:].index)))
            
            meta = MetaLearner()
            meta.fit(lstm_val, lgbm_val[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values, 
                     train_df["Close"].iloc[val_start:].pct_change(5).shift(-5).values)
            
            conf = meta.predict_batch(lstm_test.values, lgbm_test[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values)
            y_true = test_df["label_5d"].values
            sigs = (conf >= 25.0).astype(int)
            
            acc = accuracy_score(y_true, sigs) * 100
            f1 = f1_score(y_true, sigs, zero_division=0) * 100
            
            windows.append((test_df.index[0].date(), test_df.index[-1].date(), acc, f1))
        except Exception as e:
            print(f"Error on window ending {test_df.index[-1].date()}: {e}")
            
        current_end -= window_size

    for w in reversed(windows):
        print(f"  Window {w[0]} to {w[1]}: Acc={w[2]:.1f}% | F1={w[3]:.1f}%")
        
    if windows:
        mean_acc = np.mean([w[2] for w in windows])
        print(f"  Mean Sentiment-Free Accuracy across {len(windows)} windows: {mean_acc:.1f}%")

def main():
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()
    
    # Get exact date boundaries for RELIANCE (Full Pipeline)
    print("="*70)
    print("  Checking exact data boundaries for RELIANCE.NS")
    print("="*70)
    df, _, _ = dp.process("RELIANCE.NS")
    df = fe.compute_all(df, forex_series=dp.fetch_forex_rate("USD", "INR"), 
                        nifty_series=dp.fetch_index_data("^NSEI"), 
                        vix_series=dp.fetch_index_data("^INDIAVIX"), is_indian=True)
    df = se.get_historical_features(df, {})
    df = garch.fit_transform(df)
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    df["label_5d"] = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    
    av_cols = [c for c in ALL_FEATURES if c in df.columns]
    df.dropna(subset=["label_5d"] + av_cols, inplace=True)
    
    start_date = df.index[0].date()
    end_date = df.index[-1].date()
    total_days = len(df)
    print(f"  Start Date: {start_date}")
    print(f"  End Date: {end_date}")
    print(f"  Total Usable Days: {total_days}")
    
    # Evaluate 7 more tickers
    print("\n" + "="*70)
    print("  Evaluating 7 Additional Tickers for Table VI")
    print("="*70)
    tickers = [
        ("INFY.NS", "Information Tech"),
        ("ITC.NS", "FMCG"),
        ("MARUTI.NS", "Automobiles"),
        ("SUZLON.NS", "Mid-Cap Energy"),
        ("IDEA.NS", "Mid-Cap Telecom"),
        ("ZOMATO.NS", "Mid-Cap Consumer"),
        ("TATASTEEL.NS", "Metals")
    ]
    
    for tk, sec in tickers:
        acc, f1 = evaluate_ticker(tk, dp, fe, se, garch)
        if acc is not None:
            print(f"  {tk} ({sec}): Acc={acc:.1f}% | F1={f1:.1f}%")
            
    run_multi_period_sentiment_free()

if __name__ == "__main__":
    main()
