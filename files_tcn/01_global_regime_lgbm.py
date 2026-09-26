"""
FIX #1: Global LightGBM with regime as a categorical feature
==============================================================
PROBLEM:  4 independent regime-specific LightGBM models each see only ~25%
          of training data -> data-starved -> ablation shows -0.4pp vs global model.

FIX:      Train ONE LightGBM on ALL data, with `regime` as a categorical feature.
          The tree can still split on regime when it matters, but shares
          statistical power across regimes when it doesn't. This is the
          standard fix for "stratified models underperforming due to small
          per-stratum sample size."

Drop-in:  Replace your current `train_regime_models()` (which trains 4 models)
          with `train_global_regime_model()` below. At inference, you no
          longer need "identify regime -> pick matching model" branching;
          just pass `regime` as a feature column to the single model.
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, matthews_corrcoef


REGIME_LABELS = {0: "Bull_Trending", 1: "Bull_Ranging", 2: "Bear_Trending", 3: "Bear_Ranging"}


def compute_regime(df: pd.DataFrame) -> pd.Series:
    """
    Same regime logic as before (Table I in your paper), but now used to
    populate a FEATURE COLUMN rather than to select which model to use.

    df must contain: close, ema_50, adx
    """
    bull = df["close"] > df["ema_50"]
    trending = df["adx"] > 25
    regime = pd.Series(1, index=df.index)  # default Bull_Ranging
    regime[bull & trending] = 0   # Bull Trending
    regime[bull & ~trending] = 1  # Bull Ranging
    regime[~bull & trending] = 2  # Bear Trending
    regime[~bull & ~trending] = 3  # Bear Ranging
    return regime.astype("category")


def build_feature_matrix(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """
    Adds `regime` as an explicit categorical feature alongside your existing
    26 engineered features (RSI, MACD, ATR, BB, EMA distances, ADX, OBV, VWAP,
    rolling returns, garch_vol, sentiment_score, etc.)
    """
    X = df[feature_cols].copy()
    X["regime"] = compute_regime(df)
    return X


def train_global_regime_model(
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 3,
    test_size: int = 252,
):
    """
    Single LightGBM classifier trained on the FULL dataset with `regime` as
    a categorical column, evaluated via walk-forward CV (same scheme you
    already use: TimeSeriesSplit, n_splits=3, test_size=252).

    y is the same 4-class target you already define in Table II
    (Strong Buy / Buy / Hold / Sell), OR swap to binary if you've moved to
    a binary BUY/SELL target -- this function works for either, LightGBM
    infers num_class from the data.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
    fold_metrics = []
    models = []

    cat_features = ["regime"]
    n_classes = y.nunique()
    objective = "multiclass" if n_classes > 2 else "binary"

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        params = dict(
            n_estimators=300,
            max_depth=6,
            num_leaves=31,
            learning_rate=0.05,
            objective=objective,
            random_state=42,
        )
        if objective == "multiclass":
            params["num_class"] = n_classes

        model = lgb.LGBMClassifier(**params)
        model.fit(
            X_train, y_train,
            categorical_feature=cat_features,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )

        preds = model.predict(X_test)
        proba = model.predict_proba(X_test)

        metrics = {
            "fold": fold,
            "accuracy": accuracy_score(y_test, preds),
            "f1_macro": f1_score(y_test, preds, average="macro"),
            "mcc": matthews_corrcoef(y_test, preds),
        }
        # AUC only meaningful for binary; for multiclass use one-vs-rest macro AUC
        try:
            if objective == "binary":
                metrics["auc"] = roc_auc_score(y_test, proba[:, 1])
            else:
                metrics["auc_ovr_macro"] = roc_auc_score(y_test, proba, multi_class="ovr", average="macro")
        except ValueError:
            pass  # e.g. only one class present in a fold

        fold_metrics.append(metrics)
        models.append(model)
        print(f"[Fold {fold}] {metrics}")

    return models, pd.DataFrame(fold_metrics)


def compare_global_vs_per_regime(global_metrics: pd.DataFrame, per_regime_metrics: pd.DataFrame):
    """
    Quick side-by-side print so you can paste this straight into your
    ablation table (Table VIII) as a new row: 'Global LightGBM + regime feature'.
    """
    print("\n=== Global (regime-as-feature) vs Per-Regime (4 independent models) ===")
    print("Global  :", global_metrics.mean(numeric_only=True).round(4).to_dict())
    print("PerRegime:", per_regime_metrics.mean(numeric_only=True).round(4).to_dict())


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Minimal synthetic smoke test so you can verify this runs end-to-end
    # before wiring in your real feature pipeline. Replace with your
    # actual df (OHLCV + 26 engineered features + garch_vol + sentiment_score).
    # ------------------------------------------------------------------
    rng = np.random.default_rng(42)
    n = 1500
    dates = pd.date_range("2019-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    ema_50 = pd.Series(close).rolling(50, min_periods=1).mean().values
    adx = rng.uniform(10, 40, n)

    df = pd.DataFrame({
        "close": close, "ema_50": ema_50, "adx": adx,
        "rsi": rng.uniform(20, 80, n),
        "macd": rng.normal(0, 1, n),
        "atr_norm": rng.uniform(0.5, 3, n),
        "garch_vol": rng.uniform(0.5, 2.5, n),
        "sentiment_score": rng.uniform(-1, 1, n),
        "roll_ret_5": rng.normal(0, 2, n),
    }, index=dates)

    feature_cols = ["rsi", "macd", "atr_norm", "garch_vol", "sentiment_score", "roll_ret_5"]
    X = build_feature_matrix(df, feature_cols)

    fwd_ret = pd.Series(close, index=dates).pct_change(5).shift(-5)
    y = pd.cut(fwd_ret, bins=[-np.inf, -0.01, 0.005, 0.02, np.inf], labels=[3, 2, 1, 0])
    y = y.astype(float).fillna(2).astype(int)

    models, metrics_df = train_global_regime_model(X, y)
    print("\nMean metrics across folds:")
    print(metrics_df.mean(numeric_only=True))
