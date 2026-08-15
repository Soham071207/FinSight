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

    v2 adds Regime-Adaptive Dynamic Loss via per-sample weights:
      - Bear regime: False Positives (predicting Buy on a Sell) are penalized
        `bear_fp_penalty` times harder to prevent buying into crashes.
      - Bull regime: False Negatives (predicting Hold on a Strong Buy) are
        penalized `bull_fn_penalty` times harder to prevent missing rallies.
      - This replaces the static `class_weight='balanced'` which cannot
        differentiate between the same mistake in different regimes.

    Usage:
        clf = LGBMSignalClassifier(feature_cols)
        clf.tune(X_train, y_labels, regimes, trials=15)
        clf.fit(X_train, y_labels, regimes)
        signal, probs = clf.predict(X_test_row, regime)
    """

    # Class label encoding
    LABEL_MAP   = {0: "Strong Buy", 1: "Buy", 2: "Hold", 3: "Sell"}
    INV_MAP     = {"Strong Buy": 0, "Buy": 1, "Hold": 2, "Sell": 3}
    NUM_CLASSES = 4

    # Regime encoding (matches FeatureEngine)
    REGIME_BEAR     = 0
    REGIME_SIDEWAYS = 1
    REGIME_BULL     = 2

    def __init__(
        self,
        feature_cols: list,
        bear_fp_penalty: float = 3.0,
        bull_fn_penalty: float = 2.0,
    ):
        """
        Args:
            feature_cols:     List of input feature column names.
            bear_fp_penalty:  In Bear regime, multiply the weight of Sell-class
                              samples by this factor. Prevents buying into crashes.
            bull_fn_penalty:  In Bull regime, multiply the weight of Strong Buy
                              class samples by this factor. Prevents missing rallies.
        """
        self.feature_cols       = feature_cols
        self.global_model       = None
        self.feature_importance_ = None
        self.best_params        = {}
        self.bear_fp_penalty    = bear_fp_penalty
        self.bull_fn_penalty    = bull_fn_penalty

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
        """LightGBM hyperparameters, merged with any tuned best_params.
        NOTE: class_weight is intentionally omitted here — we use
        per-sample `sample_weight` in fit() which is more expressive.
        """
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
            "n_jobs":        2,
            # class_weight removed — superseded by per-sample regime weights
        }
        base_params.update(self.best_params)
        return base_params

    # ── Regime-Adaptive Sample Weight Construction ────────────────────────

    def _compute_sample_weights(
        self,
        y: pd.Series,
        regimes: pd.Series,
    ) -> np.ndarray:
        """
        Build per-sample weights encoding regime-conditional loss penalties.

        This is a 4-step process:
          1. Base class-balanced weights (corrects global class imbalance).
          2. Data-adaptive penalty calibration: the user-specified penalties
             (bear_fp_penalty, bull_fn_penalty) are the MAXIMUM multipliers.
             The actual multiplier is scaled by how rare the critical class
             is within that regime, preventing over-penalizing when a regime
             already has abundant signal samples.
          3. Secondary Bear+Buy penalty: predicting Buy in a Bear regime
             is nearly as dangerous as the missed Sell. Apply a moderate
             0.5x secondary penalty to Bear+Buy samples.
          4. Weight clipping: cap all weights at 5x the mean weight so no
             single sample dominates the loss landscape.
        """
        y_arr      = np.array(y, dtype=int)
        regime_arr = np.array(regimes, dtype=int)
        weights    = np.ones(len(y_arr), dtype=float)

        # Step 1: Global class-balanced base weights
        class_counts = np.bincount(y_arr, minlength=self.NUM_CLASSES)
        for cls in range(self.NUM_CLASSES):
            if class_counts[cls] > 0:
                weights[y_arr == cls] = len(y_arr) / (self.NUM_CLASSES * class_counts[cls])

        # Step 2: Data-adaptive Bear/Sell penalty
        # Scale penalty by inverse regime-frequency of Sell within Bear regime.
        # If Sell is already abundant in Bear regime, use a smaller penalty.
        bear_mask   = regime_arr == self.REGIME_BEAR
        bear_sell_mask = bear_mask & (y_arr == 3)
        n_bear      = bear_mask.sum()
        n_bear_sell = bear_sell_mask.sum()
        if n_bear > 0 and n_bear_sell > 0:
            # fraction of Bear samples that ARE Sell
            bear_sell_frac = n_bear_sell / n_bear
            # Scale: rarer Sell in Bear => stronger penalty (up to max)
            adaptive_bear_penalty = min(
                self.bear_fp_penalty,
                self.bear_fp_penalty * (1.0 - bear_sell_frac) + 1.0
            )
            weights[bear_sell_mask] *= adaptive_bear_penalty
        else:
            adaptive_bear_penalty = self.bear_fp_penalty  # fallback

        # Step 3: Data-adaptive Bull/StrongBuy penalty
        bull_mask      = regime_arr == self.REGIME_BULL
        bull_sbuy_mask = bull_mask & (y_arr == 0)
        n_bull      = bull_mask.sum()
        n_bull_sbuy = bull_sbuy_mask.sum()
        if n_bull > 0 and n_bull_sbuy > 0:
            bull_sbuy_frac = n_bull_sbuy / n_bull
            adaptive_bull_penalty = min(
                self.bull_fn_penalty,
                self.bull_fn_penalty * (1.0 - bull_sbuy_frac) + 1.0
            )
            weights[bull_sbuy_mask] *= adaptive_bull_penalty
        else:
            adaptive_bull_penalty = self.bull_fn_penalty  # fallback

        # Step 4: Secondary Bear+Buy penalty
        # Buying in a Bear market is the second most dangerous mistake.
        # Apply a moderate additional weight to Bear+Buy samples (label=1)
        # so LightGBM learns to be cautious about bullish signals in Bear.
        bear_buy_mask = bear_mask & (y_arr == 1)
        if bear_buy_mask.sum() > 0:
            secondary_penalty = 1.0 + (adaptive_bear_penalty - 1.0) * 0.4
            weights[bear_buy_mask] *= secondary_penalty

        # Step 5: Weight clipping — cap at 5x mean to prevent outlier dominance
        mean_w  = weights.mean()
        max_cap = 5.0 * mean_w
        clipped = (weights > max_cap).sum()
        weights = np.minimum(weights, max_cap)

        logger.info(
            f"  [LGBM] Regime weights — "
            f"Bear/Sell penalty={adaptive_bear_penalty:.2f}x ({n_bear_sell} samples) | "
            f"Bull/StrongBuy penalty={adaptive_bull_penalty:.2f}x ({n_bull_sbuy} samples) | "
            f"Bear/Buy secondary={secondary_penalty if bear_buy_mask.sum() > 0 else 1.0:.2f}x | "
            f"Clipped={clipped} samples"
        )
        print(
            f"  [LGBM] Regime weights — "
            f"Bear/Sell={adaptive_bear_penalty:.2f}x ({n_bear_sell} samp) | "
            f"Bull/SBuy={adaptive_bull_penalty:.2f}x ({n_bull_sbuy} samp) | "
            f"Bear/Buy secondary penalty | Clipped {clipped} samples"
        )
        return weights



    # ── Tuning ────────────────────────────────────────────────────────────

    def tune(self, X_df: pd.DataFrame, labels: pd.Series, regimes: pd.Series, trials: int = 15):
        """Random search hyperparameter tuning for LightGBM (with regime-adaptive weights)."""
        if not HAS_LGB:
            return self

        valid = labels.notna() & X_df[self.feature_cols].notna().all(axis=1) & regimes.notna()
        X = X_df.loc[valid, self.feature_cols].copy()
        X["regime"] = regimes[valid].astype("category")
        y = labels[valid].astype(int)
        r = regimes[valid].reset_index(drop=True)
        y_reset = y.reset_index(drop=True)

        if len(X) < 500:
            return self

        print(f"  [LGBM] Starting Random Search Hyperparameter Tuning ({trials} trials)...")

        # 80/20 chronological split for tuning validation
        split_idx = int(len(X) * 0.8)
        X_tr, y_tr = X.iloc[:split_idx], y_reset.iloc[:split_idx]
        X_va, y_va = X.iloc[split_idx:], y_reset.iloc[split_idx:]
        r_tr = r.iloc[:split_idx]

        # Compute regime-adaptive weights for training split only
        sw_tr = self._compute_sample_weights(y_tr, r_tr)

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
                n_jobs=2,
                random_state=42,
                **params
            )

            model.fit(
                X_tr, y_tr,
                sample_weight=sw_tr,
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
        Train one global LightGBM model with regime-adaptive sample weights.

        Args:
            X_df    : feature DataFrame
            labels  : integer labels (0-3) from create_labels()
            regimes : regime Series (0-3) from FeatureEngine
        """
        if not HAS_LGB:
            logger.warning("LightGBM unavailable -- skipping training")
            return self

        # Drop rows with NaN labels (last row has no next-day return)
        valid = labels.notna() & X_df[self.feature_cols].notna().all(axis=1) & regimes.notna()

        X = X_df.loc[valid, self.feature_cols].copy()
        X["regime"] = regimes[valid].astype("category")
        y = labels[valid].astype(int)
        r = regimes[valid].reset_index(drop=True)
        y_reset = y.reset_index(drop=True)

        # Build regime-adaptive per-sample weights
        sample_weights = self._compute_sample_weights(y_reset, r)

        params = self._get_params()

        # Train global model (all data)
        logger.info(f"  Training global LightGBM model on {len(X)} samples with regime-adaptive weights...")
        self.global_model = lgb.LGBMClassifier(**params)

        eval_size = max(50, len(X) // 5)

        self.global_model.fit(
            X, y,
            sample_weight=sample_weights,
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

    # ── Walk-Forward Online Learning (Rank 6) ─────────────────────────────

    def online_update(
        self,
        X_new: pd.DataFrame,
        labels_new: pd.Series,
        regimes_new: pd.Series,
        window_size: int = 120,
        n_boost_rounds: int = 50,
    ) -> "LGBMSignalClassifier":
        """
        Incrementally adapt to market concept drift using Walk-Forward Online Learning.

        Instead of retraining the full model from scratch (expensive), this method
        continues LightGBM training from the existing model checkpoint using
        `init_model`. This is equivalent to extending the boosting ensemble
        with `n_boost_rounds` new trees that specifically correct the model's
        errors on the most recent market data.

        Design principles:
          1. Rolling window: only use the last `window_size` recent rows to
             train the update. This prevents old market regimes from diluting
             the adaptation to current conditions (concept drift).
          2. init_model: passes the existing global_model as the starting
             checkpoint. The new trees ADD to the existing ensemble rather
             than replacing it, so long-term patterns are preserved.
          3. Regime-adaptive weights: applies the same regime-conditional
             sample weighting as the original fit(), ensuring Bear/Bull
             penalties remain active during online updates.
          4. Non-destructive: if the update fails (too few rows, single class),
             the original model is kept unchanged.

        Args:
            X_new:        DataFrame of recent feature rows (in chronological order).
            labels_new:   Integer labels (0-3) for each row in X_new.
            regimes_new:  Regime series for each row in X_new.
            window_size:  How many recent rows to use for the update (default=120
                          trading days ≈ 6 months).
            n_boost_rounds: Additional trees to grow on recent data (default=50).

        Returns:
            self (updated in place)
        """
        if not HAS_LGB or self.global_model is None:
            logger.warning("[OnlineUpdate] No base model to update. Run fit() first.")
            return self

        # Use only the most recent `window_size` rows (rolling window)
        if len(X_new) > window_size:
            X_new       = X_new.iloc[-window_size:]
            labels_new  = labels_new.iloc[-window_size:]
            regimes_new = regimes_new.iloc[-window_size:]

        # Validity filter
        valid = (
            labels_new.notna() &
            X_new[self.feature_cols].notna().all(axis=1) &
            regimes_new.notna()
        )
        X = X_new.loc[valid, self.feature_cols].copy()
        X["regime"] = regimes_new[valid].astype("category")
        y = labels_new[valid].astype(int).reset_index(drop=True)
        r = regimes_new[valid].reset_index(drop=True)

        if len(X) < 30:
            logger.warning(f"[OnlineUpdate] Only {len(X)} valid rows — skipping update.")
            return self

        if len(y.unique()) < 2:
            logger.warning("[OnlineUpdate] Single class in window — skipping update.")
            return self

        # Regime-adaptive sample weights on the new window
        sw = self._compute_sample_weights(y, r)

        # Build online-update params: fewer trees, smaller LR to prevent overfitting
        online_params = {
            "objective":     "multiclass",
            "num_class":     self.NUM_CLASSES,
            "num_leaves":    31,              # simpler trees for adaptation
            "learning_rate": 0.01,            # small LR to not overwrite old knowledge
            "n_estimators":  n_boost_rounds,
            "subsample":     0.8,
            "colsample_bytree": 0.8,
            "reg_alpha":     0.1,
            "reg_lambda":    0.5,             # stronger regularization for update
            "min_child_samples": 10,          # allow smaller leaves with limited data
            "verbose":       -1,
            "random_state":  42,
            "n_jobs":        2,
        }

        try:
            # Convert existing fitted model to LightGBM Booster for init_model
            base_booster = self.global_model.booster_

            updated_model = lgb.LGBMClassifier(**online_params)
            updated_model.fit(
                X, y,
                sample_weight=sw,
                categorical_feature=["regime"],
                init_model=base_booster,         # continue from existing checkpoint
            )
            self.global_model = updated_model

            # Refresh feature importances
            self.feature_importance_ = pd.Series(
                self.global_model.feature_importances_,
                index=self.feature_cols + ["regime"],
            ).sort_values(ascending=False)

            logger.info(
                f"  [OnlineUpdate] Model updated on {len(X)} recent rows "
                f"(+{n_boost_rounds} boost rounds, window={window_size}d)"
            )
            print(
                f"  [OnlineUpdate] Model adapted: {len(X)} rows | "
                f"+{n_boost_rounds} trees | rolling window={window_size}d"
            )

        except Exception as e:
            logger.warning(f"[OnlineUpdate] Failed: {e}. Original model retained.")

        return self

    def online_update_from_buffer(
        self,
        buffer: list,
        regimes: pd.Series,
        min_buffer_size: int = 30,
        **kwargs,
    ) -> "LGBMSignalClassifier":
        """
        Convenience wrapper for production loops that accumulate new observations.

        Args:
            buffer:          List of feature dicts (one per trading day).
            regimes:         Regime series aligned with buffer.
            min_buffer_size: Minimum observations before triggering an update.
            **kwargs:        Forwarded to online_update() (window_size, n_boost_rounds).

        Returns:
            self
        """
        if len(buffer) < min_buffer_size:
            logger.debug(f"[OnlineUpdate] Buffer too small ({len(buffer)}). Waiting.")
            return self

        X_buf = pd.DataFrame(buffer)
        if "label" not in X_buf.columns:
            logger.warning("[OnlineUpdate] Buffer missing 'label' column. Skipping.")
            return self

        labels = X_buf.pop("label").astype(int)
        return self.online_update(X_buf, labels, regimes, **kwargs)

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
