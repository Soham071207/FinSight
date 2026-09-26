"""
FIX #2: Upgrade the stacking meta-learner
==========================================
PROBLEM:  Ridge regression assumes a LINEAR combination of
          [lstm_prob, lgbm_class_0_prob, ..., lgbm_class_3_prob] is enough.
          It can't capture interactions like "LSTM bullish AND regime=Bull_Trending"
          which is exactly the kind of signal stacking is supposed to exploit.
          This is also part of why your AUC sits ~0.50-0.54: Ridge is leaving
          a tunable nonlinear boundary on the table.

FIX:      (a) Compare Ridge vs LogisticRegression(L2) vs shallow LightGBM/XGBoost
              stacker on IDENTICAL inputs/folds -> pick the best by AUC/MCC,
              not just accuracy.
          (b) Add isotonic regression calibration on top of whichever stacker
              wins, so the output probability is trustworthy enough to pick a
              non-degenerate decision threshold (fixes the 92% recall / 14%
              specificity problem from before).

Drop-in:  Replace your `MetaLearner` (currently `sklearn.linear_model.Ridge`)
          with `StackerComparison` below. Run it once during development to
          pick the winner, then hardcode that choice in production.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score, matthews_corrcoef,
    confusion_matrix, balanced_accuracy_score
)
import lightgbm as lgb
import xgboost as xgb


META_FEATURE_NAMES = ["lstm_prob", "lgbm_p0", "lgbm_p1", "lgbm_p2", "lgbm_p3"]


def build_meta_features(lstm_prob: np.ndarray, lgbm_proba_4class: np.ndarray) -> pd.DataFrame:
    """
    Same inputs you already pass to Ridge: 1-D LSTM sigmoid output +
    4-D LightGBM class-probability vector = 5 columns total.

    lstm_prob:        shape (n,)
    lgbm_proba_4class: shape (n, 4)

    Returns a DataFrame (not a bare array) so downstream models keep
    feature names -- avoids sklearn's "X does not have valid feature
    names" warnings and makes feature-importance output readable.
    """
    arr = np.column_stack([lstm_prob, lgbm_proba_4class])
    return pd.DataFrame(arr, columns=META_FEATURE_NAMES)


def youden_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """
    Find the threshold that maximizes Youden's J statistic
    (sensitivity + specificity - 1), instead of maximizing F1.

    This is THE fix for your 92.3% recall / 14.5% specificity problem --
    maximizing F1 alone on an imbalanced-ish target rewards a model that
    just predicts the majority class almost always. Youden's J forces a
    balance between catching positives and not flooding the book with
    false buy signals.
    """
    from sklearn.metrics import roc_curve
    fpr, tpr, thresholds = roc_curve(y_true, y_proba)
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    return thresholds[best_idx]


def evaluate_at_threshold(y_true, y_proba, threshold):
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, y_pred),
        "f1": f1_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "mcc": matthews_corrcoef(y_true, y_pred),
        "auc": roc_auc_score(y_true, y_proba),
        "recall": tp / (tp + fn) if (tp + fn) else 0,
        "specificity": tn / (tn + fp) if (tn + fp) else 0,
    }


class StackerComparison:
    """
    Trains 4 candidate meta-learners on the SAME walk-forward folds and
    reports metrics side by side: Ridge (baseline), LogisticRegression,
    shallow LightGBM, shallow XGBoost. Also reports the calibrated +
    Youden-threshold version of the winner.
    """

    def __init__(self, n_splits=3, test_size=252):
        self.n_splits = n_splits
        self.test_size = test_size
        self.results = {}

    def run(self, X_meta: pd.DataFrame, y_binary: np.ndarray):
        tscv = TimeSeriesSplit(n_splits=self.n_splits, test_size=self.test_size)

        candidates = {
            "ridge": lambda: Ridge(alpha=1.0),
            "logreg_l2": lambda: LogisticRegression(C=1.0, max_iter=1000),
            "lgbm_shallow": lambda: lgb.LGBMClassifier(
                n_estimators=100, max_depth=2, num_leaves=7,
                learning_rate=0.05, random_state=42, verbosity=-1,
            ),
            "xgb_shallow": lambda: xgb.XGBClassifier(
                n_estimators=100, max_depth=2, learning_rate=0.05,
                random_state=42, eval_metric="logloss",
            ),
        }

        all_fold_results = {name: [] for name in candidates}

        for fold, (train_idx, test_idx) in enumerate(tscv.split(X_meta)):
            X_train, X_test = X_meta.iloc[train_idx], X_meta.iloc[test_idx]
            y_train, y_test = y_binary[train_idx], y_binary[test_idx]

            for name, factory in candidates.items():
                model = factory()
                model.fit(X_train, y_train)

                if name == "ridge":
                    # Ridge outputs continuous score; rescale to [0,1]-ish via min-max on the fold
                    raw = model.predict(X_test)
                    proba = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
                else:
                    proba = model.predict_proba(X_test)[:, 1]

                # Use a default 0.5 threshold first, for like-for-like comparison
                metrics = evaluate_at_threshold(y_test, proba, threshold=0.5)
                metrics["fold"] = fold
                all_fold_results[name].append(metrics)

        summary = {}
        for name, fold_list in all_fold_results.items():
            df = pd.DataFrame(fold_list)
            summary[name] = df.mean(numeric_only=True)
            print(f"\n=== {name} (mean across {self.n_splits} folds, threshold=0.5) ===")
            print(df.mean(numeric_only=True).round(4))

        self.results = summary
        return summary

    def best_by_auc(self):
        return max(self.results, key=lambda k: self.results[k]["auc"])


def calibrate_and_retune(model, X_train, y_train, X_test, y_test):
    """
    Once you've picked the winning stacker architecture, wrap it in
    isotonic calibration and re-derive the decision threshold via
    Youden's J instead of the default 0.5 / F1-max approach.

    This directly targets the 92.3% recall / 14.5% specificity imbalance:
    calibration fixes the probability scale, Youden's J picks a threshold
    that doesn't just chase recall.
    """
    calibrated = CalibratedClassifierCV(model, method="isotonic", cv=3)
    calibrated.fit(X_train, y_train)
    proba_test = calibrated.predict_proba(X_test)[:, 1]

    best_thresh = youden_threshold(y_test, proba_test)
    metrics = evaluate_at_threshold(y_test, proba_test, best_thresh)

    print("\n=== Calibrated model + Youden threshold ===")
    print(pd.Series(metrics).round(4))
    return calibrated, best_thresh, metrics


if __name__ == "__main__":
    # Smoke test with synthetic data shaped like your real meta-features
    rng = np.random.default_rng(42)
    n = 1500

    lstm_prob = rng.uniform(0, 1, n)
    lgbm_proba_4class = rng.dirichlet(alpha=[1, 1, 1, 1], size=n)
    X_meta = build_meta_features(lstm_prob, lgbm_proba_4class)

    # Synthetic binary target with a slight, learnable relationship to inputs
    signal = 0.6 * lstm_prob + 0.4 * lgbm_proba_4class[:, 0] + rng.normal(0, 0.15, n)
    y_binary = (signal > np.median(signal)).astype(int)

    comparison = StackerComparison(n_splits=3, test_size=252)
    summary = comparison.run(X_meta, y_binary)

    best = comparison.best_by_auc()
    print(f"\n>>> Best stacker by AUC: {best}")

    # Final calibration step on a simple train/test split for demonstration
    split = n - 252
    X_train, X_test = X_meta.iloc[:split], X_meta.iloc[split:]
    y_train, y_test = y_binary[:split], y_binary[split:]

    final_model = lgb.LGBMClassifier(
        n_estimators=100, max_depth=2, num_leaves=7,
        learning_rate=0.05, random_state=42, verbosity=-1,
    )
    calibrate_and_retune(final_model, X_train, y_train, X_test, y_test)
