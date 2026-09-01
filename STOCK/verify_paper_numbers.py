"""
verify_paper_numbers.py — Computes the 5 specific data points needed for the paper.

Outputs:
  1. Precision/Recall for the ablation "w/o Regime Routing" (for Section V.D)
  2. McNemar's exact p-values: Ensemble vs RF and Ensemble vs LSTM (for Section V.K)
  3. 3-day forward return distribution stats: mean & std (for Section V.C)
  4. (SMS labelling disagreement % — cannot be computed from code, must be manually reported)
  5. (Table IX latency numbers — must be manually benchmarked)
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


def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")


def make_3day_labels(df):
    """3-day forward return with scaled dead zone (0.6%)"""
    fwd_ret = df["Close"].pct_change(3).shift(-3)
    labels = np.where(fwd_ret > 0.006, 1, np.where(fwd_ret < -0.006, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_3d")


def run():
    print("=" * 70)
    print("  PAPER VERIFICATION SCRIPT")
    print("  Computing real numbers for 5 fabricated entries")
    print("=" * 70)

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
    usd_inr = dp.fetch_forex_rate() if is_indian else pd.Series(dtype=float)

    print("\n  [1/6] Building features for all tickers...")
    for t in train_tickers:
        try:
            df_t, _, _ = dp.process(t)
            df_t = fe.compute_all(df_t, usd_inr, is_indian=is_indian)
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
                # Store raw df for 3-day stats
                raw_df = df_t.copy()
            else:
                all_train_dfs.append(df_t)
        except Exception as e:
            print(f"  ERROR for {t}: {e}")

    train_df = pd.concat(all_train_dfs).reset_index(drop=True)
    test_df = target_test_df.reset_index(drop=True)
    y_true = test_df["label_5d"].values
    available = target_available

    # ═══════════════════════════════════════════════════════════════════════
    # VERIFICATION #3: 3-day forward return distribution stats
    # ═══════════════════════════════════════════════════════════════════════
    print("\n  [2/6] Computing 3-day return distribution stats...")
    fwd_3d = raw_df["Close"].pct_change(3).shift(-3).dropna()
    test_3d = fwd_3d.iloc[-test_size:]
    print(f"\n  *** VERIFICATION #3: 3-Day Forward Return Distribution ***")
    print(f"  Full dataset: mean = {fwd_3d.mean()*100:.3f}%, std = {fwd_3d.std()*100:.3f}%")
    print(f"  Test period:  mean = {test_3d.mean()*100:.3f}%, std = {test_3d.std()*100:.3f}%")
    bullish_3d = (fwd_3d.iloc[-test_size:] > 0.006).sum()
    total_3d = len(fwd_3d.iloc[-test_size:])
    print(f"  Bullish % (3d, test): {bullish_3d}/{total_3d} = {bullish_3d/total_3d*100:.1f}%")

    # ═══════════════════════════════════════════════════════════════════════
    # Train full pipeline for McNemar's + Ablation
    # ═══════════════════════════════════════════════════════════════════════
    print("\n  [3/6] Training LSTM...")
    lstm = LSTMPredictor(available)
    lstm.fit(target_train_df, target_train_df["label_5d"])
    full_lstm = pd.concat([target_train_df.iloc[-lstm.lookback:], target_test_df])
    lstm_probs_test = lstm.predict(full_lstm).loc[target_test_df.index]
    lstm_preds = (lstm_probs_test >= 0.5).astype(int).values
    lstm_probs_flat = lstm_probs_test.values

    lstm_probs_train = []
    for df_t in all_train_dfs:
        lstm_probs_train.append(lstm.predict(df_t))
    train_df["lstm_prob"] = pd.concat(lstm_probs_train).reset_index(drop=True).values
    test_df["lstm_prob"] = lstm_probs_flat

    print("  [4/6] Training LightGBM (full regime-aware)...")
    lgbm_feats = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]
    lgbm = LGBMSignalClassifier(lgbm_feats)
    labels_4class = lgbm.create_labels(train_df)
    regimes_train = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
    lgbm.fit(train_df, labels_4class, regimes_train)
    regimes_test = test_df["regime"] if "regime" in test_df.columns else pd.Series(0, index=test_df.index)
    lgbm_out = lgbm.predict_batch(test_df, regimes_test)

    print("  [5/6] Training Meta-Learner...")
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

    # Use threshold=25 (validation-tuned)
    best_t = 25.0
    ensemble_preds = (ensemble_conf >= best_t).astype(int)

    # ═══════════════════════════════════════════════════════════════════════
    # Train baselines for McNemar's
    # ═══════════════════════════════════════════════════════════════════════
    print("  [6/6] Training baselines (LR, RF) for McNemar's test...")
    X_train = train_df[available].values
    y_train = train_df["label_5d"].values
    X_test = test_df[available].values

    rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)

    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    lr_preds = lr.predict(X_test)

    # ═══════════════════════════════════════════════════════════════════════
    # VERIFICATION #2: McNemar's exact p-values
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n  *** VERIFICATION #2: McNemar's Test P-Values ***")
    for name, baseline_preds in [("Random Forest", rf_preds), ("LSTM standalone", lstm_preds),
                                  ("Logistic Regression", lr_preds)]:
        correct_ens = (ensemble_preds == y_true)
        correct_base = (baseline_preds == y_true)
        b00 = np.sum(correct_ens & correct_base)
        b01 = np.sum(correct_ens & ~correct_base)
        b10 = np.sum(~correct_ens & correct_base)
        b11 = np.sum(~correct_ens & ~correct_base)
        table = [[b00, b01], [b10, b11]]
        result = mcnemar(table, exact=True)
        sig = "SIGNIFICANT" if result.pvalue < 0.05 else "Not significant"
        print(f"  Ensemble vs {name}: p = {result.pvalue:.4f} ({sig})")
        print(f"    Contingency: Both Right={b00}, Ens Only={b01}, Base Only={b10}, Both Wrong={b11}")

    # ═══════════════════════════════════════════════════════════════════════
    # VERIFICATION #1: Ablation "w/o Regime Routing" — Full metrics
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n  *** VERIFICATION #1: Ablation w/o Regime Routing (Full Metrics) ***")
    print("  Re-training LightGBM with regime routing disabled...")

    # Force all regimes to 0 (no routing)
    lgbm_no_regime = LGBMSignalClassifier(lgbm_feats)
    labels_4class_nr = lgbm_no_regime.create_labels(train_df)
    regimes_train_0 = pd.Series(0, index=train_df.index)
    lgbm_no_regime.fit(train_df, labels_4class_nr, regimes_train_0)
    regimes_test_0 = pd.Series(0, index=test_df.index)
    lgbm_out_nr = lgbm_no_regime.predict_batch(test_df, regimes_test_0)

    # Re-train meta-learner for no-regime
    lgbm_val_nr = lgbm_no_regime.predict_batch(df_val, pd.Series(0, index=df_val.index))
    lgbm_val_p_nr = lgbm_val_nr[prob_cols].values
    meta_nr = MetaLearner()
    meta_nr.fit(lstm_val, lgbm_val_p_nr, next_rets)
    lgbm_test_p_nr = lgbm_out_nr[prob_cols].values
    ensemble_conf_nr = meta_nr.predict_batch(lstm_probs_flat, lgbm_test_p_nr)
    ensemble_preds_nr = (ensemble_conf_nr >= best_t).astype(int)

    acc_nr = accuracy_score(y_true, ensemble_preds_nr) * 100
    prec_nr = precision_score(y_true, ensemble_preds_nr, zero_division=0) * 100
    rec_nr = recall_score(y_true, ensemble_preds_nr, zero_division=0) * 100
    f1_nr = f1_score(y_true, ensemble_preds_nr, zero_division=0) * 100

    # Also get full model numbers for comparison
    acc_full = accuracy_score(y_true, ensemble_preds) * 100
    prec_full = precision_score(y_true, ensemble_preds, zero_division=0) * 100
    rec_full = recall_score(y_true, ensemble_preds, zero_division=0) * 100
    f1_full = f1_score(y_true, ensemble_preds, zero_division=0) * 100

    print(f"\n  Full Ensemble:      Acc={acc_full:.1f}%  Prec={prec_full:.1f}%  Rec={rec_full:.1f}%  F1={f1_full:.1f}%")
    print(f"  w/o Regime Routing: Acc={acc_nr:.1f}%  Prec={prec_nr:.1f}%  Rec={rec_nr:.1f}%  F1={f1_nr:.1f}%")
    print(f"  Accuracy Drop:      {acc_full - acc_nr:+.1f}pp")
    print(f"  Precision Change:   {prec_full:.1f}% -> {prec_nr:.1f}% ({prec_nr - prec_full:+.1f}pp)")
    print(f"  Recall Change:      {rec_full:.1f}% -> {rec_nr:.1f}% ({rec_nr - rec_full:+.1f}pp)")

    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SUMMARY: Numbers to update in the paper")
    print("=" * 70)
    print(f"  [V.D Ablation] w/o Regime: Prec={prec_nr:.1f}%, Rec={rec_nr:.1f}%")
    print(f"                 Full Model: Prec={prec_full:.1f}%, Rec={rec_full:.1f}%")
    print(f"  [V.C 3-day]    mean={test_3d.mean()*100:.2f}%, std={test_3d.std()*100:.2f}%")
    print(f"  [V.K McNemar]  Check p-values above")
    print("=" * 70)


if __name__ == "__main__":
    run()
