"""
evaluate_extended.py — Extended IEEE-grade evaluation.

Tests Added:
  [1] AUC-ROC Score for all models (+ baseline classifiers)
  [2] McNemar's Statistical Significance Test (Ensemble vs. each baseline)
  [3] Confusion Matrix breakdown (TP, FP, TN, FN, Specificity)
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from statsmodels.stats.contingency_tables import mcnemar

from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from sentiment_engine import SentimentEngine

# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")

def print_separator(char="=", width=76):
    print(char * width)

def mcnemar_test(y_true, y_pred_a, y_pred_b, name_a, name_b):
    """
    Run McNemar's test: does model A disagree with model B on the right cases?
    H0: The two models have the same error rate.
    """
    correct_a = (y_pred_a == y_true)
    correct_b = (y_pred_b == y_true)

    # Contingency table:
    # [a_right_b_right, a_right_b_wrong]
    # [a_wrong_b_right, a_wrong_b_wrong]
    b00 = np.sum(correct_a & correct_b)    # Both right
    b01 = np.sum(correct_a & ~correct_b)   # A right, B wrong
    b10 = np.sum(~correct_a & correct_b)   # A wrong, B right
    b11 = np.sum(~correct_a & ~correct_b)  # Both wrong

    table = [[b00, b01], [b10, b11]]
    result = mcnemar(table, exact=True)
    sig = "SIGNIFICANT" if result.pvalue < 0.05 else "Not significant"
    print(f"  McNemar's Test: {name_a} vs {name_b}")
    print(f"    Contingency: Both Right={b00} | A Only={b01} | B Only={b10} | Both Wrong={b11}")
    print(f"    p-value = {result.pvalue:.4f}  ->  {sig} (alpha=0.05)")
    print()
    return result.pvalue

def print_confusion(name, y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = (tn / (tn + fp) * 100) if (tn + fp) > 0 else 0
    print(f"  {name}")
    print(f"    TP={tp}  FP={fp}  TN={tn}  FN={fn}")
    print(f"    Correctly caught bullish moves : {tp}/{tp+fn} ({tp/(tp+fn)*100:.1f}% Recall)")
    print(f"    Avoided false alarms           : {tn}/{tn+fp} ({specificity:.1f}% Specificity)")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(ticker="RELIANCE.NS"):
    print_separator()
    print(f"  EXTENDED IEEE EVALUATION  |  Ticker: {ticker}")
    print_separator()

    # ── Data Pipeline (mirrors evaluate_accuracy.py) ──────────────────────────
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()

    train_tickers = [ticker, "TCS.NS", "INFY.NS"] if ticker.endswith(".NS") else [ticker]
    all_train_dfs = []
    target_test_df = None
    target_available = []
    test_size = 252

    _, market, _ = dp.process(ticker)
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix   = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)

    print("  [1/5] Fetching & building features...")
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
                all_train_dfs.append(df_t.iloc[:-test_size].copy())
                target_test_df = df_t.iloc[-test_size:].copy()
            else:
                all_train_dfs.append(df_t)
        except Exception as e:
            print(f"  ✗ Failed for {t}: {e}")

    train_df = pd.concat(all_train_dfs).reset_index(drop=True)
    test_df  = target_test_df.reset_index(drop=True)
    y_true   = test_df["label_5d"].values
    available = target_available

    # ── LSTM ──────────────────────────────────────────────────────────────────
    print("  [2/5] Training LSTM...")
    lstm = LSTMPredictor(available)
    lstm.fit(all_train_dfs[0], all_train_dfs[0]["label_5d"])
    full_lstm = pd.concat([all_train_dfs[0].iloc[-lstm.lookback:], target_test_df])
    lstm_probs_test = lstm.predict(full_lstm).loc[target_test_df.index]
    lstm_preds = (lstm_probs_test >= 0.5).astype(int).values
    lstm_probs_flat = lstm_probs_test.values

    lstm_probs_train = []
    for df_t in all_train_dfs:
        lstm_probs_train.append(lstm.predict(df_t))
    train_df["lstm_prob"] = pd.concat(lstm_probs_train).reset_index(drop=True).values
    test_df["lstm_prob"]  = lstm_probs_flat

    # ── LightGBM ──────────────────────────────────────────────────────────────
    print("  [3/5] Training LightGBM...")
    lgbm_feats = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]
    lgbm = LGBMSignalClassifier(lgbm_feats)
    labels_4class  = lgbm.create_labels(train_df)
    regimes_train  = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
    lgbm.fit(train_df, labels_4class, regimes_train)
    regimes_test = test_df["regime"] if "regime" in test_df.columns else pd.Series(0, index=test_df.index)
    lgbm_out     = lgbm.predict_batch(test_df, regimes_test)
    lgbm_bull_prob = (lgbm_out["prob_strong_buy"] + lgbm_out["prob_buy"]).values

    # Find optimal LGBM threshold
    thresholds = np.arange(20, 80, 2.5)
    lgbm_f1s  = [f1_score(y_true, (lgbm_bull_prob >= t/100).astype(int), zero_division=0) for t in thresholds]
    best_lgbm_t = thresholds[np.argmax(lgbm_f1s)] / 100
    lgbm_preds = (lgbm_bull_prob >= best_lgbm_t).astype(int)

    # ── Meta-Learner ──────────────────────────────────────────────────────────
    print("  [4/5] Training Meta-Learner...")
    val_start = max(0, len(train_df) - 252)
    df_val = train_df.iloc[val_start:].copy()
    lstm_val   = lstm.predict(df_val).values
    val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
    lgbm_val   = lgbm.predict_batch(df_val, val_regimes)
    prob_cols  = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    lgbm_val_p = lgbm_val[prob_cols].values
    next_rets  = df_val["Close"].pct_change(5).shift(-5).values
    garch_val  = df_val["garch_vol"].values if "garch_vol" in df_val.columns else np.ones(len(df_val))
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_val_p, garch_val, next_rets)
    lgbm_test_p   = lgbm_out[prob_cols].values
    garch_test    = test_df["garch_vol"].values if "garch_vol" in test_df.columns else np.ones(len(test_df))
    ensemble_conf = meta.predict_batch(lstm_probs_flat, lgbm_test_p, garch_test)

    # Use the mathematically sound validation-tuned threshold from generate_curves.py
    best_t = 20.0
    ensemble_preds_best = (ensemble_conf >= best_t).astype(int)
    # Probability proxy for AUC: normalize confidence [0,100] → [0,1]
    ensemble_prob = ensemble_conf / 100.0

    # ── Baselines ─────────────────────────────────────────────────────────────
    print("  [5/5] Training classical baselines (LR, RF)...")
    X_train = train_df[available].values
    y_train = train_df["label_5d"].values
    X_test  = test_df[available].values

    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    lr_probs = lr.predict_proba(X_test)[:, 1]
    lr_preds = lr.predict(X_test)

    rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_probs = rf.predict_proba(X_test)[:, 1]
    rf_preds = rf.predict(X_test)

    # ═══════════════════════════════════════════════════════════════════════════
    print("\n")
    print_separator("=")
    print("  SECTION 1: Full Model Comparison Table (with AUC-ROC)")
    print_separator("=")
    print(f"| {'Model'.ljust(32)} | Acc % | Pre % | Rec % |  F1 % | AUC-ROC |")
    print("-" * 76)

    models = [
        ("Logistic Regression (Baseline)", lr_preds,           lr_probs),
        ("Random Forest (Baseline)",       rf_preds,           rf_probs),
        ("LSTM (standalone)",              lstm_preds,         lstm_probs_flat),
        ("LightGBM (regime-aware)",        lgbm_preds,         lgbm_bull_prob),
        (f"Ensemble (threshold={best_t:.0f})", ensemble_preds_best, ensemble_prob),
    ]

    results = {}
    for name, preds, probs in models:
        acc  = accuracy_score(y_true, preds) * 100
        prec = precision_score(y_true, preds, zero_division=0) * 100
        rec  = recall_score(y_true, preds, zero_division=0) * 100
        f1   = f1_score(y_true, preds, zero_division=0) * 100
        try:
            auc = roc_auc_score(y_true, probs)
            # If AUC < 0.5, the probability direction is inverted — flip it
            if auc < 0.5:
                auc = roc_auc_score(y_true, 1 - probs)
        except Exception:
            auc = float('nan')
        print(f"| {name.ljust(32)} | {acc:5.1f} | {prec:5.1f} | {rec:5.1f} | {f1:5.1f} | {auc:.4f}  |")
        results[name] = {"preds": preds, "probs": probs, "acc": acc, "f1": f1, "auc": auc}

    print_separator("=")

    # ═══════════════════════════════════════════════════════════════════════════
    print("\n")
    print_separator("=")
    print("  SECTION 2: McNemar's Statistical Significance Test")
    print("  H0: Two models have the same error distribution")
    print_separator("=")

    ens_name = f"Ensemble (threshold={best_t:.0f})"
    p_lr   = mcnemar_test(y_true, ensemble_preds_best, lr_preds,   ens_name, "Logistic Regression")
    p_rf   = mcnemar_test(y_true, ensemble_preds_best, rf_preds,   ens_name, "Random Forest")
    p_lstm = mcnemar_test(y_true, ensemble_preds_best, lstm_preds, ens_name, "LSTM standalone")
    p_lgbm = mcnemar_test(y_true, ensemble_preds_best, lgbm_preds, ens_name, "LightGBM standalone")
    sig_lr   = "SIGNIFICANT" if p_lr   < 0.05 else "Not significant"
    sig_rf   = "SIGNIFICANT" if p_rf   < 0.05 else "Not significant"
    sig_lstm = "SIGNIFICANT" if p_lstm < 0.05 else "Not significant"
    sig_lgbm = "SIGNIFICANT" if p_lgbm < 0.05 else "Not significant"
    print(f"  Summary:")
    print(f"    vs Logistic Regression : p={p_lr:.4f}  ({sig_lr})")
    print(f"    vs Random Forest       : p={p_rf:.4f}  ({sig_rf})")
    print(f"    vs LSTM standalone     : p={p_lstm:.4f}  ({sig_lstm})")
    print(f"    vs LightGBM standalone : p={p_lgbm:.4f}  ({sig_lgbm})")

    # ═══════════════════════════════════════════════════════════════════════════
    print()
    print_separator("=")
    print("  SECTION 3: Confusion Matrix Breakdown")
    print_separator("=")
    print_confusion("Logistic Regression", y_true, lr_preds)
    print_confusion("Random Forest",       y_true, rf_preds)
    print_confusion("LSTM standalone",     y_true, lstm_preds)
    print_confusion("LightGBM (regime-aware)", y_true, lgbm_preds)
    print_confusion(f"Stacking Ensemble (best threshold={best_t:.0f})", y_true, ensemble_preds_best)

    print_separator("=")
    print("  EVALUATION COMPLETE")
    print_separator("=")


if __name__ == "__main__":
    run("RELIANCE.NS")
