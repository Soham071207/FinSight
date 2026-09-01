"""
meta_learner.py — Ridge regression stacking meta-learner.

Blends outputs from:
  • LSTM probability       (1 value)
  • LightGBM class probs   (4 values: Strong Buy, Buy, Hold, Sell)

Into a single final confidence score (0 – 100).

Trained on walk-forward validation outputs only (never on training data)
to avoid data leakage.
"""

import numpy as np
import pandas as pd
import logging

from sklearn.linear_model import Ridge
from sklearn.preprocessing import MinMaxScaler

from config import CONFIG

logger = logging.getLogger(__name__)


class MetaLearner:
    """
    Ridge regression meta-learner that stacks LSTM + LightGBM outputs.

    Usage:
        ml = MetaLearner()
        ml.fit(lstm_probs, lgbm_probs_df, labels)
        final_score = ml.predict(lstm_prob, lgbm_probs)
    """

    def __init__(self):
        self.alpha  = CONFIG["ridge_alpha"]
        self.model  = Ridge(alpha=self.alpha)
        self.scaler = MinMaxScaler(feature_range=(0, 100))
        self.is_fitted = False

    def _build_features(self, lstm_probs: np.ndarray,
                        lgbm_probs: np.ndarray) -> np.ndarray:
        """
        Stack LSTM and LightGBM outputs into a single feature matrix.

        Args:
            lstm_probs : array of shape (n,) — LSTM return probabilities
            lgbm_probs : array of shape (n, 4) — LightGBM class probabilities

        Returns:
            np.ndarray of shape (n, 5)
        """
        lstm_col = lstm_probs.reshape(-1, 1)

        # Ensure lgbm_probs is 2-D
        if lgbm_probs.ndim == 1:
            lgbm_probs = lgbm_probs.reshape(1, -1)

        return np.hstack([lstm_col, lgbm_probs])

    def fit(self, lstm_probs: np.ndarray, lgbm_probs: np.ndarray,
            labels: np.ndarray):
        """
        Fit the meta-learner on walk-forward validation outputs.

        Args:
            lstm_probs : shape (n,) — LSTM output probabilities
            lgbm_probs : shape (n, 4) — LightGBM class probabilities
            labels     : shape (n,) — actual next-day returns (continuous)
        """
        X = self._build_features(lstm_probs, lgbm_probs)

        # Clean NaN / inf
        valid = np.isfinite(X).all(axis=1) & np.isfinite(labels)
        X      = X[valid]
        labels = labels[valid]

        if len(X) < 20:
            logger.warning("Not enough data for meta-learner. Using simple averaging.")
            self.is_fitted = False
            return self

        # Fit Ridge regression
        self.model.fit(X, labels)

        # Fit scaler on predictions to normalise to 0-100 range
        raw_preds = self.model.predict(X)
        self.scaler.fit(raw_preds.reshape(-1, 1))

        self.is_fitted = True
        logger.info(f"  Meta-learner fitted on {len(X)} samples | "
                    f"Coefs: {self.model.coef_.round(3)}")
        return self

    def predict(self, lstm_prob: float, lgbm_probs: np.ndarray) -> float:
        """
        Predict final confidence score (0-100).

        Args:
            lstm_prob  : single LSTM probability
            lgbm_probs : array of shape (4,) — LightGBM class probabilities

        Returns:
            float confidence score in [0, 100]
        """
        if not self.is_fitted:
            # Fallback: weighted average heuristic
            # LSTM contributes bullishness, LightGBM provides signal direction
            bull_weight = lgbm_probs[0] * 1.0 + lgbm_probs[1] * 0.6  # Strong Buy + Buy
            bear_weight = lgbm_probs[3] * 1.0                        # Sell
            net = lstm_prob * 0.4 + bull_weight * 0.4 - bear_weight * 0.2
            return float(np.clip(net * 100, 0, 100))

        X = self._build_features(
            np.array([lstm_prob]),
            lgbm_probs.reshape(1, -1),
        )
        raw = self.model.predict(X)[0]
        scaled = self.scaler.transform(np.array([[raw]]))[0][0]
        return float(np.clip(scaled, 0, 100))

    def predict_batch(self, lstm_probs: np.ndarray,
                      lgbm_probs: np.ndarray) -> np.ndarray:
        """
        Predict final scores for a batch.

        Returns:
            np.ndarray of shape (n,) with scores in [0, 100]
        """
        if not self.is_fitted:
            scores = []
            for i in range(len(lstm_probs)):
                lp = lgbm_probs[i] if i < len(lgbm_probs) else np.array([0, 0, 1, 0])
                scores.append(self.predict(lstm_probs[i], lp))
            return np.array(scores)

        X = self._build_features(lstm_probs, lgbm_probs)
        raw = self.model.predict(X)
        scaled = self.scaler.transform(raw.reshape(-1, 1)).flatten()
        return np.clip(scaled, 0, 100)
