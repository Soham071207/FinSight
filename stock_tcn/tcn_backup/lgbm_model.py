"""
lgbm_model.py — LightGBM 4-class signal classifier with global regime routing.

Classes: Strong Buy / Buy / Hold / Sell
Label construction (no leakage):
  next_ret = Close.pct_change().shift(-1)
  Strong Buy : next_ret > +2 %
  Buy        : +0.5 % < next_ret ≤ +2 %
  Hold       : -1 % < next_ret ≤ +0.5 %
  Sell       : next_ret ≤ -1 %

Trains ONE LightGBM model on all data, using regime as a categorical feature.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import logging
import random

from config import CONFIG
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    logger.warning("LightGBM not installed. LGBMClassifier will return Hold.")


class LGBMSignalClassifier:
    """
    Regime-aware LightGBM multi-class classifier using a global model.

    Usage:
        clf = LGBMSignalClassifier(feature_cols)
        clf.tune(X_train, y_labels, regimes, trials=15)
        clf.fit(X_train, y_labels, regimes)
        signal, probs = clf.predict(X_test_row, regime)
    """

    # Class label encoding
    LABEL_MAP  = {0: "Strong Buy", 1: "Buy", 2: "Hold", 3: "Sell"}
    INV_MAP    = {"Strong Buy": 0, "Buy": 1, "Hold": 2, "Sell": 3}
    NUM_CLASSES = 4

    def __init__(self, feature_cols: list):
        self.feature_cols   = feature_cols
        self.global_model   = None
        self.feature_importance_ = None
        self.best_params = {}

    # ── Label Construction ────────────────────────────────────────────────

    @staticmethod
    def create_labels(df: pd.DataFrame) -> pd.Series:
        """
        Create 4-class labels from next-day returns using volatility-adjusted thresholds.
        Uses shift(-1) on close to prevent look-ahead bias.
        Thresholds are based on the ATR (Average True Range).
        """
        next_ret = df["Close"].pct_change().shift(-1)
        
        # We need an ATR measure. If atr_14 is present, it's normalized to close.
        if "atr_14" in df.columns:
            atr = df["atr_14"]
        else:
            # Fallback to static thresholds if ATR is missing
            atr = pd.Series(0.015, index=df.index)

        # Dynamic thresholds:
        # Strong Buy : next_ret > 1.25 * ATR
        # Buy        : 0.25 * ATR < next_ret <= 1.25 * ATR
        # Hold       : -0.5 * ATR < next_ret <= 0.25 * ATR
        # Sell       : next_ret <= -0.5 * ATR

        labels = pd.Series(2, index=df.index, name="label")  # default: Hold
        labels[next_ret > 1.25 * atr]                           = 0  # Strong Buy
        labels[(next_ret > 0.25 * atr) & (next_ret <= 1.25 * atr)]   = 1  # Buy
        labels[(next_ret > -0.5 * atr) & (next_ret <= 0.25 * atr)]  = 2  # Hold
        labels[next_ret <= -0.5 * atr]                          = 3  # Sell

        return labels

    # ── LightGBM Parameters ──────────────────────────────────────────────

    def _get_params(self) -> dict:
        """LightGBM hyperparameters, merged with any tuned best_params."""
        base_params = {
            "objective":     "multiclass",
            "num_class":     self.NUM_CLASSES,
            "metric":        "multi_logloss",
            "num_leaves":    CONFIG["lgbm_num_leaves"],
            "max_depth":     CONFIG["lgbm_max_depth"],
            "learning_rate": CONFIG["lgbm_learning_rate"],
            "n_estimators":  CONFIG["lgbm_n_estimators"],
            "subsample":     0.8,
            "colsample_bytree": 0.8,
            "reg_alpha":     0.1,
            "reg_lambda":    0.1,
            "min_child_samples": 20,
            "verbose":       -1,
            "random_state":  42,
            "n_jobs":        -1,
            "class_weight":  "balanced"
        }
        base_params.update(self.best_params)
        return base_params

    # ── Tuning ────────────────────────────────────────────────────────────
    
    def tune(self, X_df: pd.DataFrame, labels: pd.Series, regimes: pd.Series, trials: int = 15):
        """Random search hyperparameter tuning for LightGBM."""
        if not HAS_LGB:
            return self

        valid = labels.notna() & X_df[self.feature_cols].notna().all(axis=1) & regimes.notna()
        X = X_df.loc[valid, self.feature_cols].copy()
        X["regime"] = regimes[valid].astype("category")
        y = labels[valid].astype(int)
        
        if len(X) < 500:
            return self

        print(f"  [LGBM] Starting Random Search Hyperparameter Tuning ({trials} trials)...")
        
        # 80/20 chronological split for tuning validation
        split_idx = int(len(X) * 0.8)
        X_tr, y_tr = X.iloc[:split_idx], y.iloc[:split_idx]
        X_va, y_va = X.iloc[split_idx:], y.iloc[split_idx:]
        
        best_loss = float('inf')
        best_p = {}
        
        for i in range(trials):
            params = {
                "num_leaves": random.choice([31, 63, 127]),
                "learning_rate": random.choice([0.01, 0.03, 0.05]),
                "n_estimators": random.choice([400, 600, 1000]),
                "subsample": random.choice([0.7, 0.8, 0.9]),
                "reg_lambda": random.choice([0.1, 0.5, 1.0]),
                "reg_alpha": random.choice([0.0, 0.1, 0.5]),
            }
            
            model = lgb.LGBMClassifier(
                objective="multiclass",
                num_class=self.NUM_CLASSES,
                class_weight="balanced",
                n_jobs=-1,
                random_state=42,
                **params
            )
            
            model.fit(
                X_tr, y_tr,
                categorical_feature=["regime"]
            )
            
            preds = model.predict_proba(X_va)
            loss = log_loss(y_va, preds)
            
            print(f"    Trial {i+1}/{trials} | leaves: {params['num_leaves']}, lr: {params['learning_rate']}, est: {params['n_estimators']} => Val Loss: {loss:.4f}")
            
            if loss < best_loss:
                best_loss = loss
                best_p = params
                
        if best_p:
            print(f"  [LGBM] Best Params Found: {best_p} (Val Loss: {best_loss:.4f})")
            self.best_params = best_p
            
        return self

    # ── Training ──────────────────────────────────────────────────────────

    def fit(self, X_df: pd.DataFrame, labels: pd.Series, regimes: pd.Series):
        """
        Train one global LightGBM model with regime as categorical feature.

        Args:
            X_df    : feature DataFrame
            labels  : integer labels (0-3) from create_labels()
            regimes : regime Series (0-3) from FeatureEngine
        """
        if not HAS_LGB:
            logger.warning("LightGBM unavailable — skipping training")
            return self

        # Drop rows with NaN labels (last row has no next-day return)
        valid = labels.notna() & X_df[self.feature_cols].notna().all(axis=1) & regimes.notna()
        
        X = X_df.loc[valid, self.feature_cols].copy()
        X["regime"] = regimes[valid].astype("category")
        y = labels[valid].astype(int)

        params = self._get_params()

        # ── Train global model (all data) ─────────────────────────────
        logger.info(f"  Training global LightGBM model on {len(X)} samples with regime feature…")
        self.global_model = lgb.LGBMClassifier(**params)
        
        eval_size = max(50, len(X) // 5)
        
        self.global_model.fit(
            X, y,
            categorical_feature=["regime"],
            eval_set=[(X.iloc[-eval_size:], y.iloc[-eval_size:])],
            callbacks=[lgb.early_stopping(CONFIG["lgbm_early_stopping"], verbose=False),
                       lgb.log_evaluation(period=0)],
        )

        # Store feature importance from global model
        self.feature_importance_ = pd.Series(
            self.global_model.feature_importances_,
            index=self.feature_cols + ["regime"],
        ).sort_values(ascending=False)

        return self

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, X_df: pd.DataFrame, regime: int) -> tuple:
        """
        Predict signal for given features and regime.

        Returns:
            (signal_str, probabilities_array)
            signal_str : one of "Strong Buy", "Buy", "Hold", "Sell"
            probabilities : np.array of shape (4,) summing to 1.0
        """
        if not HAS_LGB or self.global_model is None:
            return "Hold", np.array([0.0, 0.0, 1.0, 0.0])

        X = X_df[self.feature_cols].copy()
        X["regime"] = pd.Series(regime, index=X.index, dtype="category")

        probs = self.global_model.predict_proba(X)
        if probs.ndim == 2:
            probs = probs[-1]  # last row if multiple
        else:
            probs = probs.flatten()

        # Ensure correct shape
        if len(probs) != self.NUM_CLASSES:
            return "Hold", np.array([0.0, 0.0, 1.0, 0.0])

        signal_idx = int(np.argmax(probs))
        signal_str = self.LABEL_MAP[signal_idx]

        return signal_str, probs

    def predict_batch(self, X_df: pd.DataFrame, regimes: pd.Series) -> pd.DataFrame:
        """
        Predict signals for a batch of rows.

        Returns DataFrame with columns: signal, prob_strong_buy, prob_buy, prob_hold, prob_sell
        """
        if not HAS_LGB or self.global_model is None:
            return pd.DataFrame({
                "signal": "Hold",
                "prob_strong_buy": 0.0, "prob_buy": 0.0,
                "prob_hold": 1.0, "prob_sell": 0.0,
            }, index=X_df.index)

        X = X_df[self.feature_cols].copy()
        X["regime"] = regimes.astype("category")

        probs = self.global_model.predict_proba(X)
        signals = [self.LABEL_MAP[int(np.argmax(p))] for p in probs]

        batch_df = pd.DataFrame({
            "signal": signals,
            "prob_strong_buy": probs[:, 0] if probs.shape[1] > 0 else 0,
            "prob_buy":        probs[:, 1] if probs.shape[1] > 1 else 0,
            "prob_hold":       probs[:, 2] if probs.shape[1] > 2 else 0,
            "prob_sell":       probs[:, 3] if probs.shape[1] > 3 else 0,
        }, index=X_df.index)

        return batch_df

    def get_feature_importance(self, top_n: int = 20) -> pd.Series:
        """Return top-N feature importances from global model."""
        if self.feature_importance_ is None:
            return pd.Series(dtype=float)
        return self.feature_importance_.head(top_n)

    def explain(self, X_df: pd.DataFrame, regimes: pd.Series, output_path: str):
        """
        Generate SHAP values and save a summary plot.
        """
        if not HAS_LGB or self.global_model is None:
            return

        try:
            import shap
            import matplotlib.pyplot as plt
            
            valid = X_df[self.feature_cols].notna().all(axis=1) & regimes.notna()
            X = X_df.loc[valid, self.feature_cols].copy()
            X["regime"] = regimes[valid].astype("category")

            # SHAP can be slow, so we take a sample if the dataset is huge
            if len(X) > 1000:
                X_sample = X.sample(1000, random_state=42)
            else:
                X_sample = X

            print("  [SHAP] Calculating Shapley values for Explainability...")
            explainer = shap.TreeExplainer(self.global_model)
            shap_values = explainer.shap_values(X_sample)

            plt.figure(figsize=(10, 6))
            shap.summary_plot(shap_values, X_sample, show=False)
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"  [SHAP] Summary plot saved to {output_path}")

        except ImportError:
            logger.warning("SHAP library not installed. Cannot generate XAI plot.")
        except Exception as e:
            logger.error(f"Failed to generate SHAP plot: {e}")
