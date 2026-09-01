"""
lgbm_model.py — LightGBM 4-class signal classifier with regime-specific models.

Classes: Strong Buy / Buy / Hold / Sell
Label construction (no leakage):
  next_ret = Close.pct_change().shift(-1)
  Strong Buy : next_ret > +2 %
  Buy        : +0.5 % < next_ret ≤ +2 %
  Hold       : -1 % < next_ret ≤ +0.5 %
  Sell       : next_ret ≤ -1 %

Trains one LightGBM model per regime (0-3).
At inference: detect current regime → use the matching model.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import logging

from config import CONFIG

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    logger.warning("LightGBM not installed. LGBMClassifier will return Hold.")


class LGBMSignalClassifier:
    """
    Regime-aware LightGBM multi-class classifier.

    Usage:
        clf = LGBMSignalClassifier(feature_cols)
        clf.fit(X_train, y_labels, regimes)
        signal, probs = clf.predict(X_test_row, regime)
    """

    # Class label encoding
    LABEL_MAP  = {0: "Strong Buy", 1: "Buy", 2: "Hold", 3: "Sell"}
    INV_MAP    = {"Strong Buy": 0, "Buy": 1, "Hold": 2, "Sell": 3}
    NUM_CLASSES = 4

    def __init__(self, feature_cols: list):
        self.feature_cols   = feature_cols
        self.regime_models  = {}          # regime_id → trained lgb.Booster
        self.global_model   = None        # fallback model (all regimes)
        self.feature_importance_ = None

    # ── Label Construction ────────────────────────────────────────────────

    @staticmethod
    def create_labels(df: pd.DataFrame) -> pd.Series:
        """
        Create 4-class labels from next-day returns.
        Uses shift(-1) on close to prevent look-ahead bias.
        """
        next_ret = df["Close"].pct_change().shift(-1)

        labels = pd.Series(2, index=df.index, name="label")  # default: Hold
        labels[next_ret > 0.02]                           = 0  # Strong Buy
        labels[(next_ret > 0.005) & (next_ret <= 0.02)]   = 1  # Buy
        labels[(next_ret > -0.01) & (next_ret <= 0.005)]  = 2  # Hold
        labels[next_ret <= -0.01]                          = 3  # Sell

        return labels

    # ── LightGBM Parameters ──────────────────────────────────────────────

    def _get_params(self) -> dict:
        """LightGBM hyperparameters from config."""
        return {
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
        }

    # ── Training ──────────────────────────────────────────────────────────

    def fit(self, X_df: pd.DataFrame, labels: pd.Series,
            regimes: pd.Series):
        """
        Train one LightGBM model per regime + one global fallback.

        Args:
            X_df    : feature DataFrame
            labels  : integer labels (0-3) from create_labels()
            regimes : regime Series (0-3) from FeatureEngine
        """
        if not HAS_LGB:
            logger.warning("LightGBM unavailable — skipping training")
            return self

        # Drop rows with NaN labels (last row has no next-day return)
        valid = labels.notna() & X_df[self.feature_cols].notna().all(axis=1)
        X = X_df.loc[valid, self.feature_cols]
        y = labels[valid].astype(int)
        r = regimes[valid].astype(int)

        params = self._get_params()

        # ── Train global model (all data) ─────────────────────────────
        logger.info("  Training global LightGBM model …")
        self.global_model = lgb.LGBMClassifier(**params)
        self.global_model.fit(
            X, y,
            eval_set=[(X.iloc[-200:], y.iloc[-200:])],
            callbacks=[lgb.early_stopping(CONFIG["lgbm_early_stopping"], verbose=False),
                       lgb.log_evaluation(period=0)],
        )

        # Store feature importance from global model
        self.feature_importance_ = pd.Series(
            self.global_model.feature_importances_,
            index=self.feature_cols,
        ).sort_values(ascending=False)

        # ── Train regime-specific models ──────────────────────────────
        for regime_id in range(4):
            mask = r == regime_id
            X_r  = X[mask]
            y_r  = y[mask]

            if len(X_r) < 100:
                logger.info(f"  Regime {regime_id}: only {len(X_r)} samples → using global model")
                self.regime_models[regime_id] = None  # fall back to global
                continue

            logger.info(f"  Regime {regime_id} ({CONFIG['regime_labels'][regime_id]}): "
                        f"{len(X_r)} samples")
            model = lgb.LGBMClassifier(**params)
            eval_size = max(50, len(X_r) // 5)
            model.fit(
                X_r, y_r,
                eval_set=[(X_r.iloc[-eval_size:], y_r.iloc[-eval_size:])],
                callbacks=[lgb.early_stopping(CONFIG["lgbm_early_stopping"], verbose=False),
                           lgb.log_evaluation(period=0)],
            )
            self.regime_models[regime_id] = model

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

        X = X_df[self.feature_cols]

        # Select regime-specific model or fall back to global
        model = self.regime_models.get(regime, None) or self.global_model

        probs = model.predict_proba(X)
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
        Predict signals for a batch of rows, using per-row regime routing.

        Returns DataFrame with columns: signal, prob_strong_buy, prob_buy, prob_hold, prob_sell
        """
        if not HAS_LGB or self.global_model is None:
            return pd.DataFrame({
                "signal": "Hold",
                "prob_strong_buy": 0.0, "prob_buy": 0.0,
                "prob_hold": 1.0, "prob_sell": 0.0,
            }, index=X_df.index)

        results = []
        X = X_df[self.feature_cols]

        for regime_id in range(4):
            mask = regimes == regime_id
            if not mask.any():
                continue

            model = self.regime_models.get(regime_id, None) or self.global_model
            X_r = X[mask]
            probs = model.predict_proba(X_r)
            signals = [self.LABEL_MAP[int(np.argmax(p))] for p in probs]

            batch_df = pd.DataFrame({
                "signal": signals,
                "prob_strong_buy": probs[:, 0] if probs.shape[1] > 0 else 0,
                "prob_buy":        probs[:, 1] if probs.shape[1] > 1 else 0,
                "prob_hold":       probs[:, 2] if probs.shape[1] > 2 else 0,
                "prob_sell":       probs[:, 3] if probs.shape[1] > 3 else 0,
            }, index=X_r.index)
            results.append(batch_df)

        if not results:
            return pd.DataFrame({
                "signal": "Hold",
                "prob_strong_buy": 0.0, "prob_buy": 0.0,
                "prob_hold": 1.0, "prob_sell": 0.0,
            }, index=X_df.index)

        return pd.concat(results).sort_index()

    def get_feature_importance(self, top_n: int = 20) -> pd.Series:
        """Return top-N feature importances from global model."""
        if self.feature_importance_ is None:
            return pd.Series(dtype=float)
        return self.feature_importance_.head(top_n)
