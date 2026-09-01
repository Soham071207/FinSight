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

def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")

def run_pipeline(ablation=None, ticker="RELIANCE.NS"):
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()
    
    train_tickers = [ticker, "TCS.NS", "INFY.NS"]
    all_train_dfs = []
    
    _, market, _ = dp.process(ticker)
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)

    test_size = 252

    for t in train_tickers:
        df_t, _, _ = dp.process(t)
        df_t = fe.compute_all(df_t, forex_series=forex, nifty_series=nifty, vix_series=vix, is_indian=is_indian)
        df_t = se.get_historical_features(df_t, {})
        df_t = garch.fit_transform(df_t)

        available = [c for c in ALL_FEATURES if c in df_t.columns]
        
        # Apply ablations to data
        if ablation == "no_sentiment":
            sentiment_feats = ['daily_sentiment_score', 'sentiment_3d_mean', 'sentiment_7d_mean', 'sentiment_momentum', 'sentiment_news_volume']
            available = [c for c in available if c not in sentiment_feats]
            
        if ablation == "no_garch":
            available = [c for c in available if c != "garch_vol"]

        df_t["label_5d"] = make_5day_labels(df_t)
        df_t.dropna(subset=available + ["label_5d"], inplace=True)
        df_t["label_5d"] = df_t["label_5d"].astype(int)

        if t == ticker:
            target_train_df = df_t.iloc[:-test_size].copy()
            target_test_df = df_t.iloc[-test_size:].copy()
            target_available = available
            all_train_dfs.append(target_train_df)
        else:
            all_train_dfs.append(df_t)

    # LSTM
    lstm = LSTMPredictor(target_available)
    lstm.fit(target_train_df, target_train_df["label_5d"])
    
    full_lstm = pd.concat([target_train_df.iloc[-lstm.lookback:], target_test_df])
    lstm_probs_test = lstm.predict(full_lstm).loc[target_test_df.index]
    lstm_probs_train_list = [lstm.predict(df_t) for df_t in all_train_dfs]
        
    train_df = pd.concat(all_train_dfs).reset_index(drop=True)
    test_df = target_test_df.reset_index(drop=True)
    y_true = test_df["label_5d"].values
    available = target_available
    
    train_df["lstm_prob"] = pd.concat(lstm_probs_train_list).reset_index(drop=True).values
    test_df["lstm_prob"]  = lstm_probs_test.values

    # LightGBM
    lgbm_feats = list(dict.fromkeys(available + ["lstm_prob"]))
    if ablation != "no_garch" and "garch_vol" not in lgbm_feats:
        lgbm_feats.append("garch_vol")
        
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]
    
    CONFIG["lgbm_num_leaves"] = 31
    CONFIG["lgbm_learning_rate"] = 0.01
    CONFIG["lgbm_n_estimators"] = 600
    lgbm = LGBMSignalClassifier(lgbm_feats)
    if hasattr(lgbm, "model"):
        lgbm.model.set_params(subsample=0.7, reg_alpha=0.5, reg_lambda=0.1)
        
    labels_4class = lgbm.create_labels(train_df)
    
    if ablation == "no_regime":
        # Force all regimes to 0
        regimes_train = pd.Series(0, index=train_df.index)
        regimes_test = pd.Series(0, index=test_df.index)
    else:
        regimes_train = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
        regimes_test = test_df["regime"] if "regime" in test_df.columns else pd.Series(0, index=test_df.index)
        
    lgbm.fit(train_df, labels_4class, regimes_train)
    lgbm_out = lgbm.predict_batch(test_df, regimes_test)

    # MetaLearner
    val_start = max(0, len(train_df) - 252)
    df_val = train_df.iloc[val_start:].copy()
    lstm_val = df_val["lstm_prob"].values
    
    if ablation == "no_regime":
        val_regimes = pd.Series(0, index=df_val.index)
    else:
        val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
        
    lgbm_val = lgbm.predict_batch(df_val, val_regimes)
    
    prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    lgbm_val_p = lgbm_val[prob_cols].values
    
    garch_val = df_val["garch_vol"].values if "garch_vol" in df_val.columns else np.ones(len(df_val))
    y_val = df_val["Close"].pct_change(5).shift(-5).values
    
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_val_p, y_val)
    
    val_conf = meta.predict_batch(lstm_val, lgbm_val_p)
    y_val_binary = (y_val > 0.005).astype(int)
    
    best_t, best_f1 = 25.0, 0.0
    for t in np.arange(20, 80, 1):
        preds_t = (val_conf >= t).astype(int)
        f1_t = f1_score(y_val_binary, preds_t, zero_division=0)
        if f1_t > best_f1:
            best_f1 = f1_t
            best_t = t

    lgbm_test_p = lgbm_out[prob_cols].values
    ensemble_conf = meta.predict_batch(lstm_probs_test.values, lgbm_test_p)
    
    signals = (ensemble_conf >= best_t).astype(int)
    
    acc = accuracy_score(y_true, signals) * 100
    f1 = f1_score(y_true, signals, zero_division=0) * 100
    return acc, f1

def run_ablation():
    print("Running Ablation Study...\n")
    results = {}
    
    print("[1/3] Running Ablation: No Sentiment (FinBERT & VADER excluded)")
    acc, f1 = run_pipeline("no_sentiment")
    results["No Sentiment"] = (acc, f1)
    
    print("[2/3] Running Ablation: No GARCH Volatility")
    acc, f1 = run_pipeline("no_garch")
    results["No Volatility"] = (acc, f1)
    
    print("[3/3] Running Ablation: No Regime Routing")
    acc, f1 = run_pipeline("no_regime")
    results["No Regime"] = (acc, f1)
    
    print("\n" + "="*60)
    print("  ABLATION STUDY RESULTS (vs. Full Model 51.6% Acc / 60.1% F1)")
    print("="*60)
    print(f"| Ablation Removed         | Acc % |  F1 % | Acc Drop |")
    print("-" * 60)
    
    full_acc, full_f1 = 51.6, 60.1
    
    for name, (a, f) in results.items():
        drop = full_acc - a
        print(f"| Ensemble w/o {name:<11} | {a:>5.1f} | {f:>5.1f} | {drop:>8.1f} |")
    print("="*60 + "\n")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    run_ablation()
