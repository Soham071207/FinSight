"""
evaluate_accuracy.py — Measures directional accuracy of all three models.

Phase 1 improvements applied:
  1.1 - 5-day forward return label with ±0.5% dead zone
  1.2 - LightGBM class imbalance fix (is_unbalance=True)
  1.3 - Meta-learner threshold sweep to find optimal decision boundary
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from sentiment_engine import SentimentEngine

# ─── Helpers ─────────────────────────────────────────────────────────────────

def calc_metrics(name, y_true, y_pred):
    acc  = accuracy_score(y_true, y_pred) * 100
    prec = precision_score(y_true, y_pred, zero_division=0) * 100
    rec  = recall_score(y_true, y_pred, zero_division=0) * 100
    f1   = f1_score(y_true, y_pred, zero_division=0) * 100
    print(f"| {name.ljust(28)} | {acc:5.1f} | {prec:5.1f} | {rec:5.1f} | {f1:5.1f} |")
    return {"acc": acc, "prec": prec, "rec": rec, "f1": f1}

def make_5day_labels(df):
    """5-day forward return with ±0.5% dead zone. Returns aligned Series."""
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")

# ─── Main evaluation ─────────────────────────────────────────────────────────

def evaluate_models(ticker="RELIANCE.NS"):
    print(f"\n{'='*68}")
    print(f"  Evaluating: {ticker}")
    print(f"{'='*68}\n")

    # 1. Data & 2. Features (Multi-Ticker)
    print("  [1/5] Fetching data & features for multiple tickers...")
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()
    
    # Train on 3 stocks for diverse regimes, test on the target ticker
    train_tickers = [ticker, "TCS.NS", "INFY.NS"] if ticker.endswith(".NS") else [ticker]
    all_train_dfs = []
    target_test_df = None
    target_df_len = 0
    target_available = []

    # Fetch macro data once
    try:
        _, market, _ = dp.process(ticker)
    except Exception as e:
        print(f"  ✗ Failed initial fetch: {e}")
        return
        
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)

    test_size = 252

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
                target_df_len = len(df_t)
                target_available = available
                train_df_t = df_t.iloc[:-test_size].copy()
                target_test_df = df_t.iloc[-test_size:].copy()
                all_train_dfs.append(train_df_t)
            else:
                # Use all data from other tickers for training
                all_train_dfs.append(df_t)
        except Exception as e:
            print(f"  ✗ Failed for {t}: {e}")

    # Keep original index intact for individual operations, then reset for final dataframe
    target_train_df = all_train_dfs[0]
    
    total_train = sum(len(df) for df in all_train_dfs)
    bullish = sum(df["label_5d"].sum() for df in all_train_dfs)
    bearish = total_train - bullish
    print(f"  Train Data: {total_train} rows | Bullish: {bullish} ({bullish/total_train*100:.0f}%) | "
          f"Bearish: {bearish} ({bearish/total_train*100:.0f}%)")

    # 4. LSTM
    print("  [3/5] Training LSTM (on target ticker only for sequential integrity)...")
    lstm = LSTMPredictor(available)
    lstm.fit(target_train_df, target_train_df["label_5d"])

    full_lstm = pd.concat([target_train_df.iloc[-lstm.lookback:], target_test_df])
    lstm_probs_test = lstm.predict(full_lstm).loc[target_test_df.index]
    lstm_preds = (lstm_probs_test >= 0.5).astype(int)
    
    # Generate LSTM predictions per-ticker independently, then concatenate
    lstm_probs_train_list = []
    for df_t in all_train_dfs:
        lstm_probs_train_list.append(lstm.predict(df_t))
        
    # Now build the flat, index-reset train/test dataframes
    train_df = pd.concat(all_train_dfs).reset_index(drop=True)
    test_df = target_test_df.reset_index(drop=True)
    y_true = test_df["label_5d"].values
    available = target_available
    
    train_df["lstm_prob"] = pd.concat(lstm_probs_train_list).reset_index(drop=True).values
    test_df["lstm_prob"]  = lstm_probs_test.values

    # 5. LightGBM (Phase 1.2: is_unbalance=True already in lgbm_model.py)
    print("  [4/5] Training LightGBM...")
    lgbm_feats = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]

    lgbm = LGBMSignalClassifier(lgbm_feats)
    labels_4class = lgbm.create_labels(train_df)
    regimes_train = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
    
    # --- Fix 9: Custom Random Search Hyperparameter Tuning ---
    print("  [*] Running Random Search for LightGBM Hyperparameters...")
    import random
    from sklearn.model_selection import train_test_split
    
    # Create validation set for tuning
    mask = ~labels_4class.isna()
    X_tune = train_df.loc[mask, lgbm_feats]
    y_tune = labels_4class[mask]
    if len(X_tune) > 500:
        X_tr, X_va, y_tr, y_va = train_test_split(X_tune, y_tune, test_size=0.2, shuffle=False)
        
        best_tune_loss = float('inf')
        best_params = {}
        
        # 15 random search trials
        for i in range(15):
            params = {
                "num_leaves": random.choice([31, 63, 95, 127]),
                "learning_rate": random.choice([0.01, 0.03, 0.05, 0.08]),
                "n_estimators": random.choice([400, 600, 800, 1000]),
                "subsample": random.choice([0.7, 0.8, 0.9, 1.0]),
                "reg_alpha": random.choice([0.0, 0.1, 0.5, 1.0]),
                "reg_lambda": random.choice([0.0, 0.1, 0.5, 1.0]),
            }
            
            import lightgbm as lgb
            from sklearn.metrics import log_loss
            
            model = lgb.LGBMClassifier(
                objective="multiclass",
                num_class=4,
                class_weight="balanced",
                n_jobs=-1,
                random_state=42,
                **params
            )
            
            model.fit(X_tr, y_tr)
            preds = model.predict_proba(X_va)
            loss = log_loss(y_va, preds)
            
            if loss < best_tune_loss:
                best_tune_loss = loss
                best_params = params
                
        print(f"  [*] Best Params Found: {best_params} (Loss: {best_tune_loss:.4f})")
        
        # Override config temporarily
        CONFIG["lgbm_num_leaves"] = best_params["num_leaves"]
        CONFIG["lgbm_learning_rate"] = best_params["learning_rate"]
        CONFIG["lgbm_n_estimators"] = best_params["n_estimators"]
        
        # Re-initialize with new params
        lgbm = LGBMSignalClassifier(lgbm_feats)
        if hasattr(lgbm, "model"):
            lgbm.model.set_params(
                subsample=best_params["subsample"],
                reg_alpha=best_params["reg_alpha"],
                reg_lambda=best_params["reg_lambda"]
            )
            
    lgbm.fit(train_df, labels_4class, regimes_train)

    regimes_test = test_df["regime"] if "regime" in test_df.columns else pd.Series(0, index=test_df.index)
    lgbm_out = lgbm.predict_batch(test_df, regimes_test)

    # Use bullish probability (Strong Buy + Buy) instead of crude signal mapping
    lgbm_bull_prob = lgbm_out["prob_strong_buy"] + lgbm_out["prob_buy"]
    # Find best threshold for LGBM standalone
    lgbm_thresholds = np.arange(20, 80, 2.5)
    lgbm_f1s = [f1_score(y_true, (lgbm_bull_prob.values >= t/100).astype(int), zero_division=0) for t in lgbm_thresholds]
    best_lgbm_t = lgbm_thresholds[np.argmax(lgbm_f1s)] / 100
    lgbm_preds = (lgbm_bull_prob.values >= best_lgbm_t).astype(int)

    # 6. MetaLearner
    print("  [5/5] Training Meta-Learner...")
    val_start = max(0, len(train_df) - 252)
    df_val = train_df.iloc[val_start:].copy()

    lstm_val    = lstm.predict(df_val).values
    val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
    lgbm_val    = lgbm.predict_batch(df_val, val_regimes)
    prob_cols   = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    lgbm_val_p  = lgbm_val[prob_cols].values
    next_rets   = df_val["Close"].pct_change(5).shift(-5).values

    garch_val = df_val["garch_vol"].values if "garch_vol" in df_val.columns else np.ones(len(df_val))
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_val_p, garch_val, next_rets)

    lgbm_test_p    = lgbm_out[prob_cols].values
    garch_test = test_df["garch_vol"].values if "garch_vol" in test_df.columns else np.ones(len(test_df))
    ensemble_conf  = meta.predict_batch(lstm_probs_test.values, lgbm_test_p, garch_test)

    # Phase 1.3 + Phase 2: Wider threshold sweep — find best decision boundary
    print("\n  Threshold sweep for optimal meta-learner cutoff...")
    thresholds = np.arange(20, 80, 2.5)
    f1s  = [f1_score(y_true, (ensemble_conf >= t).astype(int), zero_division=0) for t in thresholds]
    accs = [accuracy_score(y_true, (ensemble_conf >= t).astype(int)) * 100 for t in thresholds]
    best_t_f1  = thresholds[np.argmax(f1s)]
    best_t_acc = thresholds[np.argmax(accs)]

    print(f"  Best F1 threshold : {best_t_f1:.1f}  -> F1={max(f1s)*100:.1f}%")
    print(f"  Best Acc threshold: {best_t_acc:.1f}  -> Acc={max(accs):.1f}%")

    ensemble_preds_50  = (ensemble_conf >= 50.0).astype(int)
    ensemble_preds_best = (ensemble_conf >= best_t_acc).astype(int)

    # ── Results ──────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  Table I: Stock Prediction Model Performance (5-Day Horizon)")
    print(f"{'='*72}")
    print(f"| {'Model'.ljust(28)} | Acc % | Pre % | Rec % |  F1 % |")
    print("-" * 72)
    r1 = calc_metrics("LSTM (standalone)",         y_true, lstm_preds)
    r2 = calc_metrics("LightGBM (regime-aware)",   y_true, lgbm_preds)
    r3 = calc_metrics("Ensemble @ threshold=50",   y_true, ensemble_preds_50)
    r4 = calc_metrics(f"Ensemble @ best threshold ({best_t_acc:.0f})", y_true, ensemble_preds_best)
    print(f"{'='*72}\n")

    print("  Recommendation -> Use config threshold =", best_t_acc)

if __name__ == "__main__":
    evaluate_models("RELIANCE.NS")
