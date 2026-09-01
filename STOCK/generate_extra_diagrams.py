import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
from matplotlib.patches import Patch

from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from sentiment_engine import SentimentEngine

def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")

def run():
    print("Gathering data and training models...")
    ticker = "RELIANCE.NS"
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()

    train_tickers = [ticker, "TCS.NS", "INFY.NS"]
    all_train_dfs = []
    test_size = 252

    _, market, _ = dp.process(ticker)
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)

    for t in train_tickers:
        try:
            df_t, _, _ = dp.process(t)
            df_t = fe.compute_all(df_t, forex_series=forex, nifty_series=nifty, vix_series=vix, is_indian=is_indian)
            df_t = se.get_historical_features(df_t, {})
            df_t = garch.fit_transform(df_t)
            available = [c for c in ALL_FEATURES if c in df_t.columns]
            df_t["label_5d"] = make_5day_labels(df_t)
            df_t.dropna(subset=available + ["label_5d"], inplace=True)
            df_t["label_5d"] = df_t["label_5d"].astype(int)
            if t == ticker:
                target_available = available
                target_train_df = df_t.iloc[:-test_size].copy()
                target_test_df = df_t.iloc[-test_size:].copy()
                all_train_dfs.append(target_train_df)
            else:
                all_train_dfs.append(df_t)
        except Exception as e:
            print(f"ERROR for {t}: {e}")

    train_df = pd.concat(all_train_dfs).reset_index(drop=True)
    test_df = target_test_df.reset_index(drop=True)
    y_true = test_df["label_5d"].values
    available = target_available

    print("Training LSTM...")
    lstm = LSTMPredictor(available)
    lstm.fit(target_train_df, target_train_df["label_5d"])
    full_lstm = pd.concat([target_train_df.iloc[-lstm.lookback:], target_test_df])
    lstm_probs_test = lstm.predict(full_lstm).loc[target_test_df.index]
    lstm_probs_flat = lstm_probs_test.values

    lstm_probs_train = []
    for df_t in all_train_dfs:
        lstm_probs_train.append(lstm.predict(df_t))
    train_df["lstm_prob"] = pd.concat(lstm_probs_train).reset_index(drop=True).values
    test_df["lstm_prob"] = lstm_probs_flat

    print("Training LightGBM...")
    lgbm_feats = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]
    lgbm = LGBMSignalClassifier(lgbm_feats)
    labels_4class = lgbm.create_labels(train_df)
    regimes_train = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
    lgbm.fit(train_df, labels_4class, regimes_train)
    regimes_test = test_df["regime"] if "regime" in test_df.columns else pd.Series(0, index=test_df.index)
    lgbm_out = lgbm.predict_batch(test_df, regimes_test)

    print("Training Meta-Learner...")
    val_start = max(0, len(train_df) - 252)
    df_val = train_df.iloc[val_start:].copy()
    lstm_val = lstm.predict(df_val).values
    val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
    lgbm_val = lgbm.predict_batch(df_val, val_regimes)
    prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    lgbm_val_p = lgbm_val[prob_cols].values
    next_rets = df_val["Close"].pct_change(5).shift(-5).values
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_val_p, next_rets)
    lgbm_test_p = lgbm_out[prob_cols].values
    ensemble_conf = meta.predict_batch(lstm_probs_flat, lgbm_test_p)
    ensemble_preds = (ensemble_conf >= 25.0).astype(int)

    sns.set_style("whitegrid")
    
    # 1. Feature Importance Bar Chart
    print("Generating Feature Importance Plot...")
    feat_imp = lgbm.get_feature_importance(15)
    plt.figure(figsize=(10, 8))
    sns.barplot(x=feat_imp.values, y=feat_imp.index, palette="viridis")
    plt.title("Top 15 Features Driving LightGBM Predictions (Gain)", fontsize=14, weight='bold')
    plt.xlabel("Feature Importance (Gain)", fontsize=12)
    plt.ylabel("Feature", fontsize=12)
    plt.tight_layout()
    plt.savefig('feature_importance.png', dpi=300)
    plt.close()

    # 2. Cumulative Equity Curve
    print("Generating Equity Curve Plot...")
    plt.figure(figsize=(12, 6))
    daily_rets = test_df["Close"].pct_change().shift(-1).fillna(0).values
    benchmark_equity = (1 + daily_rets).cumprod() * 10000
    strategy_equity = (1 + (daily_rets * ensemble_preds)).cumprod() * 10000
    dates = pd.to_datetime(target_test_df.index) if type(target_test_df.index) == pd.DatetimeIndex else pd.RangeIndex(len(target_test_df))
    plt.plot(dates, benchmark_equity, label="Passive Buy & Hold Benchmark", color="gray", lw=2, linestyle='--')
    plt.plot(dates, strategy_equity, label="Stacking Ensemble Strategy", color="#1f77b4", lw=2)
    plt.title("Portfolio Equity Curve (Out-of-Sample Backtest)", fontsize=14, weight='bold')
    plt.xlabel("Date" if type(target_test_df.index) == pd.DatetimeIndex else "Trading Days", fontsize=12)
    plt.ylabel("Portfolio Value ($10,000 Initial)", fontsize=12)
    plt.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig('equity_curve.png', dpi=300)
    plt.close()

    # 3. Confusion Matrix Heatmap
    print("Generating Confusion Matrix Heatmap...")
    cm = confusion_matrix(y_true, ensemble_preds)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=['Predict Bear/Cash', 'Predict Bull/Buy'], 
                yticklabels=['Actual Bear', 'Actual Bull'],
                annot_kws={"size": 16})
    plt.title("Stacking Ensemble Confusion Matrix", fontsize=14, weight='bold')
    plt.ylabel("True Market Direction", fontsize=12)
    plt.xlabel("Predicted Market Direction", fontsize=12)
    plt.tight_layout()
    plt.savefig('confusion_matrix_heatmap.png', dpi=300)
    plt.close()

    # 4. Market Regime Time-Series Plot
    print("Generating Market Regime Plot...")
    plt.figure(figsize=(14, 6))
    colors = {0: "#2ca02c", 1: "#98df8a", 2: "#d62728", 3: "#ff9896"}
    labels = {0: "Bull Trending", 1: "Bull Ranging", 2: "Bear Trending", 3: "Bear Ranging"}
    
    plt.plot(dates, test_df["Close"], color='black', lw=1.5, zorder=5)
    
    # Shade backgrounds
    for i in range(len(test_df) - 1):
        reg = test_df["regime"].iloc[i]
        plt.axvspan(dates[i], dates[i+1], color=colors[reg], alpha=0.3, lw=0)
        
    legend_elements = [Patch(facecolor=colors[r], alpha=0.5, label=labels[r]) for r in range(4)]
    plt.legend(handles=legend_elements, loc="best", title="Detected Regime")
    plt.title("Dynamic Market Regime Detection over Out-of-Sample Period", fontsize=14, weight='bold')
    plt.xlabel("Date" if type(target_test_df.index) == pd.DatetimeIndex else "Trading Days", fontsize=12)
    plt.ylabel("Close Price", fontsize=12)
    plt.tight_layout()
    plt.savefig('market_regime_plot.png', dpi=300)
    plt.close()
    
    print("All diagrams generated successfully.")

if __name__ == "__main__":
    run()
