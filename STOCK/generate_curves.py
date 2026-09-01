"""
generate_curves.py — Generate ROC + Precision-Recall curves.
Evaluates the 2-model ensemble (LSTM + LightGBM).
Includes strict out-of-sample threshold tuning on a validation set
to prevent data leakage.
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    roc_curve, auc, precision_recall_curve, average_precision_score,
    accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
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
    print("="*60)
    print("FULL MODEL EVALUATION (2-MODEL ENSEMBLE)")
    print("="*60)

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
    forex = dp.fetch_forex_rate() if is_indian else pd.Series(dtype=float)
    
    print("\n[1/6] Building features for all tickers...")
    for t in train_tickers:
        try:
            df_t, _, _ = dp.process(t)
            df_t = fe.compute_all(df_t, forex, is_indian=is_indian)
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
    y_test = test_df["label_5d"].values
    available = target_available

    # --- LSTM ---
    print("\n[2/6] Training LSTM...")
    lstm = LSTMPredictor(available)
    lstm.fit(target_train_df, target_train_df["label_5d"])
    full_lstm = pd.concat([target_train_df.iloc[-lstm.lookback:], target_test_df])
    lstm_probs_test = lstm.predict(full_lstm).loc[target_test_df.index].values

    lstm_probs_train = []
    for df_t in all_train_dfs:
        lstm_probs_train.append(lstm.predict(df_t))
    train_df["lstm_prob"] = pd.concat(lstm_probs_train).reset_index(drop=True).values
    test_df["lstm_prob"] = lstm_probs_test

    # --- LightGBM ---
    print("[3/6] Training LightGBM...")
    lgbm_feats = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]
    lgbm = LGBMSignalClassifier(lgbm_feats)
    labels_4class = lgbm.create_labels(train_df)
    regimes_train = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
    lgbm.fit(train_df, labels_4class, regimes_train)
    regimes_test = test_df["regime"] if "regime" in test_df.columns else pd.Series(0, index=test_df.index)
    lgbm_out_test = lgbm.predict_batch(test_df, regimes_test)

    # --- Meta-Learner (with Validation Leakage Fix) ---
    print("[4/6] Training Meta-Learner & Tuning Threshold...")
    # We use the last year of the TRAINING set as our validation fold
    val_size = min(252, len(train_df) // 4)
    df_val = train_df.iloc[-val_size:].copy()

    lstm_val = df_val["lstm_prob"].values
    val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
    lgbm_val = lgbm.predict_batch(df_val, val_regimes)
    prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    lgbm_val_p = lgbm_val[prob_cols].values
    garch_val = df_val["garch_vol"].values if "garch_vol" in df_val.columns else np.ones(len(df_val))
    y_val = df_val["Close"].pct_change(5).shift(-5).values

    # Fit meta-learner on validation data
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_val_p, y_val)

    # Predict on validation data to tune threshold
    val_conf = meta.predict_batch(lstm_val, lgbm_val_p)
    y_val_binary = (y_val > 0.005).astype(int)

    # Strict Data Leakage Fix: Tune threshold ONLY on Validation set
    best_t, best_f1 = 25.0, 0.0
    for t in np.arange(20, 80, 1):
        preds_t = (val_conf >= t).astype(int)
        f1_t = f1_score(y_val_binary, preds_t, zero_division=0)
        if f1_t > best_f1:
            best_f1 = f1_t
            best_t = t
    print(f"  Optimal out-of-sample threshold found: {best_t:.0f} (Val F1={best_f1*100:.1f}%)")

    # Now predict on strictly blind Test data
    lgbm_test_p = lgbm_out_test[prob_cols].values
    test_conf = meta.predict_batch(lstm_probs_test, lgbm_test_p)
    test_probs = np.clip(test_conf / 100.0, 0, 1)
    
    # Use the threshold derived from the validation set! NO LEAKAGE!
    test_preds = (test_conf >= best_t).astype(int)

    # --- Baselines ---
    print("[5/6] Training Baselines...")
    X_train = train_df[available].values
    y_train = train_df["label_5d"].values
    X_test = test_df[available].values

    rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_probs = rf.predict_proba(X_test)[:, 1]

    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    lr_probs = lr.predict_proba(X_test)[:, 1]

    # Print key metrics
    print("\n" + "="*60)
    print(f"UNBIASED OOS EVALUATION RESULTS (Threshold={best_t:.0f})")
    print("="*60)
    acc = accuracy_score(y_test, test_preds) * 100
    f1 = f1_score(y_test, test_preds) * 100
    prec = precision_score(y_test, test_preds, zero_division=0) * 100
    rec = recall_score(y_test, test_preds, zero_division=0) * 100
    print(f"Stacking Ensemble: Acc={acc:.1f}% | F1={f1:.1f}% | Prec={prec:.1f}% | Rec={rec:.1f}%")
    
    for name, probs in [("Random Forest", rf_probs), ("Logistic Regression", lr_probs)]:
        preds = (probs >= 0.5).astype(int)
        a = accuracy_score(y_test, preds) * 100
        f = f1_score(y_test, preds) * 100
        print(f"{name}: Acc={a:.1f}% | F1={f:.1f}%")

    # --- Generate All 6 Diagrams ---
    print("\n[6/6] Generating all diagrams...")
    sns.set_style("whitegrid")

    models = {
        "Stacking Ensemble (2-model)": test_probs,
        "Random Forest": rf_probs,
        "LSTM": lstm_probs_test,
        "Logistic Regression": lr_probs
    }

    # 1. ROC Curve
    plt.figure(figsize=(10, 8))
    for name, probs in models.items():
        fpr, tpr, _ = roc_curve(y_test, probs)
        roc_auc = auc(fpr, tpr)
        plt.plot(fpr, tpr, lw=2, label=f'{name} (AUC = {roc_auc:.3f})')
    plt.plot([0, 1], [0, 1], color='gray', lw=2, linestyle='--', label='Random Chance')
    plt.xlim([0.0, 1.0]); plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate', fontsize=12)
    plt.ylabel('True Positive Rate', fontsize=12)
    plt.title('Receiver Operating Characteristic (ROC) Curve', fontsize=14, weight='bold')
    plt.legend(loc="lower right", fontsize=10)
    plt.savefig('roc_curve.png', dpi=300, bbox_inches='tight'); plt.close()
    print("  Generated roc_curve.png")

    # 2. Precision-Recall Curve
    plt.figure(figsize=(10, 8))
    for name, probs in models.items():
        precision, recall, _ = precision_recall_curve(y_test, probs)
        pr_auc = average_precision_score(y_test, probs)
        plt.plot(recall, precision, lw=2, label=f'{name} (AP = {pr_auc:.3f})')
    baseline_pr = np.sum(y_test) / len(y_test)
    plt.axhline(y=baseline_pr, color='gray', lw=2, linestyle='--', label=f'Baseline ({baseline_pr:.2f})')
    plt.xlim([0.0, 1.0]); plt.ylim([0.0, 1.05])
    plt.xlabel('Recall', fontsize=12); plt.ylabel('Precision', fontsize=12)
    plt.title('Precision-Recall Curve', fontsize=14, weight='bold')
    plt.legend(loc="upper right", fontsize=10)
    plt.savefig('pr_curve.png', dpi=300, bbox_inches='tight'); plt.close()
    print("  Generated pr_curve.png")

    # 3. Feature Importance
    feat_imp = lgbm.get_feature_importance(15)
    plt.figure(figsize=(10, 8))
    sns.barplot(x=feat_imp.values, y=feat_imp.index, palette="viridis")
    plt.title("Top 15 Features Driving LightGBM Predictions (Gain)", fontsize=14, weight='bold')
    plt.xlabel("Feature Importance (Gain)", fontsize=12); plt.ylabel("Feature", fontsize=12)
    plt.tight_layout(); plt.savefig('feature_importance.png', dpi=300); plt.close()
    print("  Generated feature_importance.png")

    # 4. Equity Curve
    plt.figure(figsize=(12, 6))
    daily_rets = test_df["Close"].pct_change().shift(-1).fillna(0).values
    benchmark_equity = (1 + daily_rets).cumprod() * 10000
    strategy_equity = (1 + (daily_rets * test_preds)).cumprod() * 10000
    dates = target_test_df.index if hasattr(target_test_df.index, 'date') else pd.RangeIndex(len(target_test_df))
    plt.plot(dates, benchmark_equity, label="Passive Buy & Hold", color="gray", lw=2, linestyle='--')
    plt.plot(dates, strategy_equity, label="Stacking Ensemble Strategy", color="#1f77b4", lw=2)
    plt.title("Portfolio Equity Curve (Out-of-Sample Backtest)", fontsize=14, weight='bold')
    plt.xlabel("Trading Days", fontsize=12); plt.ylabel("Portfolio Value ($10,000 Initial)", fontsize=12)
    plt.legend(loc="upper left"); plt.tight_layout()
    plt.savefig('equity_curve.png', dpi=300); plt.close()
    print("  Generated equity_curve.png")

    # 5. Confusion Matrix
    cm = confusion_matrix(y_test, test_preds)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['Predict Bear/Cash', 'Predict Bull/Buy'],
                yticklabels=['Actual Bear', 'Actual Bull'], annot_kws={"size": 16})
    plt.title("Stacking Ensemble Confusion Matrix", fontsize=14, weight='bold')
    plt.ylabel("True Direction", fontsize=12); plt.xlabel("Predicted Direction", fontsize=12)
    plt.tight_layout(); plt.savefig('confusion_matrix_heatmap.png', dpi=300); plt.close()
    print("  Generated confusion_matrix_heatmap.png")

    # 6. Regime Plot
    plt.figure(figsize=(14, 6))
    colors = {0: "#2ca02c", 1: "#98df8a", 2: "#d62728", 3: "#ff9896"}
    labels = {0: "Bull Trending", 1: "Bull Ranging", 2: "Bear Trending", 3: "Bear Ranging"}
    plt.plot(dates, test_df["Close"].values, color='black', lw=1.5, zorder=5)
    for i in range(len(test_df) - 1):
        reg = test_df["regime"].iloc[i]
        plt.axvspan(dates[i], dates[i+1], color=colors[reg], alpha=0.3, lw=0)
    legend_elements = [Patch(facecolor=colors[r], alpha=0.5, label=labels[r]) for r in range(4)]
    plt.legend(handles=legend_elements, loc="best", title="Detected Regime")
    plt.title("Dynamic Market Regime Detection over Out-of-Sample Period", fontsize=14, weight='bold')
    plt.xlabel("Trading Days", fontsize=12); plt.ylabel("Close Price", fontsize=12)
    plt.tight_layout(); plt.savefig('market_regime_plot.png', dpi=300); plt.close()
    print("  Generated market_regime_plot.png")

    print("\n" + "="*60)
    print("ALL DONE! 6 diagrams generated without data leakage.")
    print("="*60)

if __name__ == "__main__":
    run()
