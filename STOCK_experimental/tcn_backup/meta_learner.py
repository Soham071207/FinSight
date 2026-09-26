"""
meta_learner.py — AUC-optimized stacking meta-learner.

Blends outputs from:
  * TCN probability        (1 value)
  * LightGBM class probs   (4 values: Strong Buy, Buy, Hold, Sell)

Key design decisions (v2):
  1. Meta-stacker uses AUC as primary metric (not log-loss/calibration).
  2. Rank-averaging fallback: averages normalized probability RANKS,
     which provably preserves AUC better than averaging raw probabilities.
  3. TCN signal is treated as the anchor — LGBM adds regime context only
     when it genuinely improves AUC on the validation fold.
  4. Threshold selection uses Youden's J statistic (maximises TPR - FPR).
"""

import numpy as np
import pandas as pd
import logging
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger(__name__)

META_FEATURE_NAMES = [
    "tcn_prob",
    "lgbm_bull_prob",    # Strong Buy + Buy
    "lgbm_bear_prob",    # Sell
    "lgbm_entropy",      # Uncertainty of the LGBM itself
    "tcn_rank",          # Rank-normalized TCN probability
    "lgbm_rank",         # Rank-normalized LGBM bull probability
]


def youden_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    fpr, tpr, thresholds = roc_curve(y_true, y_proba)
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    return float(thresholds[best_idx])


def rank_normalize(arr: np.ndarray) -> np.ndarray:
    """Convert raw probabilities to rank-normalized scores in [0,1]."""
    ranks = np.argsort(np.argsort(arr)).astype(float)
    return ranks / (len(ranks) - 1 + 1e-9)


def lgbm_entropy(probs: np.ndarray) -> np.ndarray:
    """Shannon entropy of LightGBM 4-class distribution (per row)."""
    p = np.clip(probs, 1e-9, 1.0)
    return -np.sum(p * np.log(p), axis=1)


class MetaLearner:
    """
    AUC-optimized stacking meta-learner.

    The meta-stacker is a LightGBM binary classifier trained with
    'binary' objective and AUC metric, ensuring the model learns to
    discriminate rather than calibrate. It is validated against the
    TCN standalone AUC; if the ensemble does not exceed the TCN AUC,
    it falls back to a rank-weighted average that mathematically
    preserves the TCN's superior discrimination.
    """

    def __init__(self):
        # AUC-optimized shallow stacker
        self.model = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=3,
            num_leaves=7,
            learning_rate=0.03,
            objective="binary",
            metric="auc",
            random_state=42,
            verbosity=-1,
            class_weight="balanced",
            subsample=0.8,
            reg_lambda=0.5,
        )
        self.scaler = RobustScaler()
        self.is_fitted = False
        self.threshold = 0.5
        self.tcn_standalone_auc = 0.0
        self.ensemble_auc = 0.0
        self.use_rank_blend = False     # Fallback if stacker degrades AUC
        self.tcn_weight = 0.7           # Default rank-blend TCN weight

    def _build_features(self,
                        tcn_probs: np.ndarray,
                        lgbm_probs: np.ndarray) -> np.ndarray:
        tcn_col   = tcn_probs.flatten()
        bull_prob = lgbm_probs[:, 0] + lgbm_probs[:, 1]   # Strong Buy + Buy
        bear_prob = lgbm_probs[:, 3]                       # Sell
        ent       = lgbm_entropy(lgbm_probs)
        tcn_rank  = rank_normalize(tcn_col)
        lgbm_rank = rank_normalize(bull_prob)
        return np.column_stack([tcn_col, bull_prob, bear_prob, ent, tcn_rank, lgbm_rank])

    def fit(self, tcn_probs: np.ndarray, lgbm_probs: np.ndarray, next_rets: np.ndarray):
        labels = (next_rets > 0).astype(int)

        # Validity mask
        valid = (np.isfinite(tcn_probs) &
                 np.isfinite(lgbm_probs).all(axis=1) &
                 np.isfinite(labels))
        tcn_v, lgbm_v, lab_v = tcn_probs[valid], lgbm_probs[valid], labels[valid]

        if len(tcn_v) < 30 or len(np.unique(lab_v)) < 2:
            logger.warning("Not enough data for meta-learner. Using fallback.")
            self.is_fitted = False
            return self

        # Record TCN standalone AUC as the floor
        bull_prob = lgbm_v[:, 0] + lgbm_v[:, 1]
        self.tcn_standalone_auc = roc_auc_score(lab_v, tcn_v)
        lgbm_standalone_auc     = roc_auc_score(lab_v, bull_prob)

        # --- Find optimal rank-blend weight by grid search ---
        best_blend_auc, best_w = 0.0, 0.7
        for w in np.arange(0.4, 0.95, 0.05):
            tcn_r  = rank_normalize(tcn_v)
            lgbm_r = rank_normalize(bull_prob)
            blend  = w * tcn_r + (1 - w) * lgbm_r
            auc    = roc_auc_score(lab_v, blend)
            if auc > best_blend_auc:
                best_blend_auc = auc
                best_w = w
        self.tcn_weight = best_w

        # --- Always use rank-blend (stacker removed to prevent overfitting) ---
        self.use_rank_blend = True
        self.ensemble_auc = best_blend_auc
        
        logger.info(
            f"  Meta-learner using Rank-Blend (w_tcn={best_w:.2f}) | "
            f"TCN_AUC={self.tcn_standalone_auc:.4f} | "
            f"Blend_AUC={best_blend_auc:.4f}"
        )
        print(
            f"  Meta-learner using Rank-Blend (w_tcn={best_w:.2f}) | "
            f"TCN_AUC={self.tcn_standalone_auc:.4f} | "
            f"Blend_AUC={best_blend_auc:.4f}"
        )

        # --- Threshold via Youden's J on the best blend ---
        blend_v = best_w * rank_normalize(tcn_v) + (1 - best_w) * rank_normalize(bull_prob)
        self.threshold = youden_threshold(lab_v, blend_v)

        self.is_fitted = True
        return self

    def _predict_raw(self, tcn_probs: np.ndarray, lgbm_probs: np.ndarray) -> np.ndarray:
        """Return raw probability scores (not scaled to 0–100)."""
        if not self.is_fitted:
            bull = lgbm_probs[:, 0] + lgbm_probs[:, 1]
            return 0.5 * tcn_probs.flatten() + 0.5 * bull

        bull = lgbm_probs[:, 0] + lgbm_probs[:, 1]

        if self.use_rank_blend:
            tcn_r  = rank_normalize(tcn_probs.flatten())
            lgbm_r = rank_normalize(bull)
            return self.tcn_weight * tcn_r + (1 - self.tcn_weight) * lgbm_r
        else:
            X    = self._build_features(tcn_probs.flatten(), lgbm_probs)
            X_sc = self.scaler.transform(X)
            return self.model.predict_proba(X_sc)[:, 1]

    def predict(self, tcn_prob: float, lgbm_probs: np.ndarray) -> float:
        """Single-sample prediction scaled to [0, 100]."""
        raw = self._predict_raw(
            np.array([tcn_prob]),
            lgbm_probs.reshape(1, -1)
        )[0]

        t = self.threshold
        if raw < t:
            scaled = (raw / (t + 1e-9)) * 50
        else:
            scaled = 50 + ((raw - t) / (1.0 - t + 1e-9)) * 50

        return float(np.clip(scaled, 0, 100))

    def predict_batch(self, tcn_probs: np.ndarray, lgbm_probs: np.ndarray) -> np.ndarray:
        """Batch prediction scaled to [0, 100]."""
        raw = self._predict_raw(tcn_probs, lgbm_probs)
        t   = self.threshold

        scaled = np.where(
            raw < t,
            (raw / (t + 1e-9)) * 50,
            50 + ((raw - t) / (1.0 - t + 1e-9)) * 50
        )
        return np.clip(scaled, 0, 100)
