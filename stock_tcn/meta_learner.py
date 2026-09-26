"""
meta_learner.py — Three-stream stacking meta-learner with OOF cross-validation.

Blends outputs from:
  * TCN probability        (1 value)
  * GRU probability        (1 value)  [NEW v4: absorbed from baseline]
  * LightGBM class probs   (4 values: Strong Buy, Buy, Hold, Sell)

Key design decisions (v4 — Solid Ensemble Fix):
  1. GRU absorbed as a first-class stream. Previously it was trained as a
     baseline and discarded. Now it feeds directly into the meta-stacker.
  2. OOF stacker: meta-features are generated via 5-fold TimeSeriesSplit
     cross-validation on the validation fold, fixing the overfitting that
     forced the old rank-blend fallback.
  3. The LightGBM stacker is now activated when OOF AUC exceeds rank-blend
     AUC by a 0.002 margin. Falls back to 3-way rank-blend otherwise.
  4. Rank-blend updated to 3-way: w*TCN + (1-w)*0.5*LGBM + (1-w)*0.5*GRU.
  5. Backward-compatible: gru_probs=None uses 0.5 neutral fill — works with
     original 2-stream calling convention (live inference without GRU).
"""

import numpy as np
import pandas as pd
import logging
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger(__name__)

META_FEATURE_NAMES = [
    "tcn_prob",
    "lgbm_bull_prob",    # Strong Buy + Buy
    "lgbm_bear_prob",    # Sell
    "lgbm_entropy",      # Uncertainty of the LGBM itself
    "gru_prob",          # GRU sequence model probability  [NEW v4]
    "tcn_rank",          # Rank-normalized TCN probability
    "lgbm_rank",         # Rank-normalized LGBM bull probability
    "gru_rank",          # Rank-normalized GRU probability  [NEW v4]
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
    Three-stream AUC-optimized stacking meta-learner with Bayesian Uncertainty Quantification.

    The meta-stacker blends TCN, GRU, and LightGBM probabilities using either:
      a) An OOF-trained LightGBM stacker (preferred, when OOF AUC > rank-blend AUC + 0.002)
      b) A 3-way rank-blend: w*TCN + (1-w)*0.5*LGBM + (1-w)*0.5*GRU (fallback)

    GRU Integration (v4):
        GRU was previously trained as a baseline and thrown away. It is now a
        first-class input to the meta-stacker. When gru_probs=None (e.g., live
        inference without GRU), a 0.5 neutral fill is used — fully backward compatible.

    OOF Stacker (v4):
        The old `use_rank_blend=True` hardcode is replaced with a proper OOF
        validation procedure using 5-fold TimeSeriesSplit on the validation fold.
        This prevents stacker overfitting and gives a fair AUC comparison.

    Uncertainty Quantification:
        MC Dropout simulation with triple perturbation (TCN gaussian, LGBM Dirichlet, GRU gaussian).
    """

    def __init__(
        self,
        mc_samples: int = 30,
        veto_threshold: float = 0.12,
        noise_scale: float = 0.08,
    ):
        """
        Args:
            mc_samples:      Number of stochastic forward passes for MC Dropout.
            veto_threshold:  Base veto threshold (sideways regime). Scaled per regime.
            noise_scale:     Initial noise std; auto-calibrated after fit().
        """
        # AUC-optimized shallow stacker (now properly activated via OOF check)
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
        self.scaler            = RobustScaler()
        self.is_fitted         = False
        self.threshold         = 0.5
        self.tcn_standalone_auc = 0.0
        self.gru_standalone_auc = 0.0
        self.ensemble_auc      = 0.0
        self.use_rank_blend    = True   # Re-evaluated on every fit()
        self.tcn_weight        = 0.6

        # Bayesian uncertainty parameters
        self.mc_samples        = mc_samples
        self.noise_scale       = noise_scale
        self._noise_calibrated = False

        # Regime-conditional veto thresholds
        self._base_veto_threshold = veto_threshold
        self._veto_by_regime = {
            0: veto_threshold * 0.67,   # Bear: extra-conservative
            1: veto_threshold,           # Sideways: base
            2: veto_threshold * 1.33,   # Bull: slightly permissive
        }

        self.last_uncertainty: float = 0.0
        self.last_vetoed: bool       = False

    # ── Internal Helpers ──────────────────────────────────────────────────

    def _build_features(self,
                        tcn_probs: np.ndarray,
                        lgbm_probs: np.ndarray,
                        gru_probs: np.ndarray = None) -> np.ndarray:
        """
        Build 8-feature meta-feature matrix.
        When gru_probs=None, uses 0.5 neutral fill so the scaler stays consistent.
        """
        tcn_col   = tcn_probs.flatten()
        bull_prob = lgbm_probs[:, 0] + lgbm_probs[:, 1]   # Strong Buy + Buy
        bear_prob = lgbm_probs[:, 3]                       # Sell
        ent       = lgbm_entropy(lgbm_probs)
        tcn_rank  = rank_normalize(tcn_col)
        lgbm_rank = rank_normalize(bull_prob)
        gru_col   = (np.clip(gru_probs.flatten(), 1e-6, 1 - 1e-6)
                     if gru_probs is not None
                     else np.full(len(tcn_col), 0.5))
        gru_rank  = rank_normalize(gru_col)
        return np.column_stack([tcn_col, bull_prob, bear_prob, ent, gru_col,
                                 tcn_rank, lgbm_rank, gru_rank])

    def _rank_blend_scores(self,
                           tcn_v: np.ndarray,
                           bull_prob: np.ndarray,
                           gru_v: np.ndarray = None,
                           w: float = None) -> np.ndarray:
        """
        3-way rank-blend: w*TCN + (1-w)*0.5*LGBM + (1-w)*0.5*GRU.
        Falls back to 2-way (TCN + LGBM) when gru_v is None.
        """
        if w is None:
            w = self.tcn_weight
        tcn_r  = rank_normalize(tcn_v)
        lgbm_r = rank_normalize(bull_prob)
        if gru_v is not None:
            gru_r = rank_normalize(gru_v)
            return w * tcn_r + (1 - w) * 0.5 * lgbm_r + (1 - w) * 0.5 * gru_r
        return w * tcn_r + (1 - w) * lgbm_r

    # ── Training ──────────────────────────────────────────────────────────

    def fit(self,
            tcn_probs: np.ndarray,
            lgbm_probs: np.ndarray,
            next_rets: np.ndarray,
            gru_probs: np.ndarray = None):
        """
        Fit the meta-learner using OOF stacker + rank-blend comparison.

        Procedure:
          1. Compute standalone AUCs for each stream.
          2. Grid-search optimal 3-way rank-blend weight.
          3. Generate OOF stacker predictions via 5-fold TimeSeriesSplit.
          4. Activate stacker if OOF AUC > rank-blend AUC + 0.002.
          5. Auto-calibrate MC noise scale from training variance.

        Args:
            tcn_probs : (N,) TCN bullish probabilities on validation fold.
            lgbm_probs: (N, 4) LGBM 4-class probabilities on validation fold.
            next_rets : (N,) forward returns — used to build binary labels.
            gru_probs : (N,) optional GRU probabilities on validation fold.
        """
        labels = (next_rets > 0).astype(int)

        # Validity mask — drop NaN rows from any stream
        valid = (np.isfinite(tcn_probs) &
                 np.isfinite(lgbm_probs).all(axis=1) &
                 np.isfinite(labels))
        if gru_probs is not None:
            valid &= np.isfinite(gru_probs.flatten())

        tcn_v  = tcn_probs[valid]
        lgbm_v = lgbm_probs[valid]
        lab_v  = labels[valid]
        gru_v  = gru_probs.flatten()[valid] if gru_probs is not None else None

        if len(tcn_v) < 30 or len(np.unique(lab_v)) < 2:
            logger.warning("Not enough data for meta-learner. Using fallback.")
            self.is_fitted = False
            return self

        # ── 1. Standalone AUCs ──────────────────────────────────────────────
        bull_prob = lgbm_v[:, 0] + lgbm_v[:, 1]
        self.tcn_standalone_auc = roc_auc_score(lab_v, tcn_v)
        lgbm_standalone_auc     = roc_auc_score(lab_v, bull_prob)

        if gru_v is not None:
            self.gru_standalone_auc = roc_auc_score(lab_v, gru_v)
            print(f"  [Meta] Standalone AUC — "
                  f"TCN={self.tcn_standalone_auc:.4f} | "
                  f"LGBM={lgbm_standalone_auc:.4f} | "
                  f"GRU={self.gru_standalone_auc:.4f}")
        else:
            print(f"  [Meta] Standalone AUC — "
                  f"TCN={self.tcn_standalone_auc:.4f} | "
                  f"LGBM={lgbm_standalone_auc:.4f} (no GRU provided)")

        # ── 2. Best 3-way rank-blend weight (grid search) ──────────────────
        best_blend_auc, best_w = 0.0, 0.6
        for w in np.arange(0.20, 0.95, 0.05):
            blend = self._rank_blend_scores(tcn_v, bull_prob, gru_v, w)
            auc   = roc_auc_score(lab_v, blend)
            if auc > best_blend_auc:
                best_blend_auc, best_w = auc, w
        self.tcn_weight = best_w

        # ── 3. OOF stacker with 5-fold TimeSeriesSplit ─────────────────────
        X_meta    = self._build_features(
            tcn_v.reshape(-1, 1), lgbm_v,
            gru_v.reshape(-1, 1) if gru_v is not None else None
        )
        X_sc      = self.scaler.fit_transform(X_meta)
        oof_preds = np.full(len(lab_v), np.nan)
        
        tscv_gen = TimeSeriesSplit(n_splits=5)

        for fold_tr, fold_va in tscv_gen.split(X_sc):
            if len(np.unique(lab_v[fold_tr])) < 2 or len(fold_tr) < 20:
                continue
            fold_model = lgb.LGBMClassifier(
                n_estimators=200, max_depth=3, num_leaves=7,
                learning_rate=0.03, objective="binary", metric="auc",
                random_state=42, verbosity=-1,
                class_weight="balanced", subsample=0.8, reg_lambda=0.5,
            )
            fold_model.fit(X_sc[fold_tr], lab_v[fold_tr])
            oof_preds[fold_va] = fold_model.predict_proba(X_sc[fold_va])[:, 1]

        valid_oof = ~np.isnan(oof_preds)
        if valid_oof.sum() >= 20 and len(np.unique(lab_v[valid_oof])) >= 2:
            stacker_auc = roc_auc_score(lab_v[valid_oof], oof_preds[valid_oof])
        else:
            stacker_auc = 0.0

        print(f"  [Meta] Rank-Blend AUC={best_blend_auc:.4f} | "
              f"OOF-Stacker AUC={stacker_auc:.4f} (w_tcn={best_w:.2f})")

        # ── 4. Choose stacker vs rank-blend ────────────────────────────────
        if stacker_auc > best_blend_auc + 0.002:
            self.use_rank_blend = False
            self.ensemble_auc   = stacker_auc
            # Train final stacker on full validation data
            self.model.fit(X_sc, lab_v)
            self.threshold = (youden_threshold(lab_v[valid_oof], oof_preds[valid_oof])
                              if valid_oof.sum() >= 20 else 0.5)
            print(f"  [Meta] -> OOF Stacker selected "
                  f"(Delta AUC = +{stacker_auc - best_blend_auc:.4f})")
        else:
            self.use_rank_blend = True
            self.ensemble_auc   = best_blend_auc
            blend_all      = self._rank_blend_scores(tcn_v, bull_prob, gru_v, best_w)
            self.threshold = youden_threshold(lab_v, blend_all)
            print(f"  [Meta] -> Rank-Blend selected "
                  f"(stacker Delta AUC = {stacker_auc - best_blend_auc:+.4f}, below 0.002 threshold)")

        # ── 5. Auto-calibrate MC noise_scale from training blend variance ──
        # At 0.10 * empirical_std the veto suppresses ~5-20% of predictions.
        blend_all     = self._rank_blend_scores(tcn_v, bull_prob, gru_v, best_w)
        empirical_std = float(np.std(blend_all))
        calibrated_noise = max(0.005, 0.10 * empirical_std)
        self.noise_scale       = calibrated_noise
        self._noise_calibrated = True
        logger.info(f"  [Meta] noise_scale auto-calibrated to {calibrated_noise:.4f} "
                    f"(empirical blend std={empirical_std:.4f})")
        print(f"  [Meta] noise_scale auto-calibrated to {calibrated_noise:.4f}")

        self.is_fitted = True
        return self

    # ── Bayesian Inference ────────────────────────────────────────────────

    def predict_batch_with_uncertainty(
        self,
        tcn_probs: np.ndarray,
        lgbm_probs: np.ndarray,
        regimes: np.ndarray,
        gru_probs: np.ndarray = None,
    ) -> np.ndarray:
        """
        Bayesian prediction via Monte Carlo simulation with triple perturbation
        (vectorized across the entire test batch).

        Perturbations:
          1. Gaussian noise on TCN probability.
          2. Dirichlet noise on LGBM 4-class distribution.
          3. Gaussian noise on GRU probability.
        """
        tcn_probs = tcn_probs.flatten()
        N = len(tcn_probs)

        dirichlet_concentration = max(0.5, 1.0 / (self.noise_scale + 1e-6))
        lgbm_probs_4 = np.clip(lgbm_probs[:, :4], 1e-6, 1.0)
        lgbm_probs_4 = lgbm_probs_4 / lgbm_probs_4.sum(axis=1, keepdims=True)
        # Neutral 0.5 fill when GRU is absent
        gru_arr = (gru_probs.flatten() if gru_probs is not None
                   else np.full(N, 0.5))

        rng = np.random.default_rng()
        all_mc_scores = []

        for _ in range(self.mc_samples):
            # 1. Gaussian noise on TCN
            noisy_tcn = np.clip(
                tcn_probs + rng.normal(0.0, self.noise_scale, size=N),
                0.0, 1.0
            )
            # 2. Dirichlet noise on LGBM
            noisy_lgbm = np.array(
                [rng.dirichlet(p * dirichlet_concentration) for p in lgbm_probs_4]
            )
            noisy_bull = noisy_lgbm[:, 0] + noisy_lgbm[:, 1]
            # 3. Gaussian noise on GRU
            noisy_gru = np.clip(
                gru_arr + rng.normal(0.0, self.noise_scale, size=N),
                0.0, 1.0
            )

            if self.use_rank_blend:
                gv = noisy_gru if gru_probs is not None else None
                blend_scores = self._rank_blend_scores(noisy_tcn, noisy_bull, gv)
            else:
                # Stacker path: build features from noisy inputs
                X_noisy = self._build_features(
                    noisy_tcn.reshape(-1, 1),
                    np.column_stack([noisy_lgbm[:, 0], noisy_lgbm[:, 1],
                                     noisy_lgbm[:, 2], noisy_lgbm[:, 3]]),
                    noisy_gru.reshape(-1, 1) if gru_probs is not None else None,
                )
                X_sc = self.scaler.transform(X_noisy)
                blend_scores = self.model.predict_proba(X_sc)[:, 1]

            all_mc_scores.append(blend_scores)

        all_mc_scores = np.vstack(all_mc_scores)   # (mc_samples, N)
        mean_raw = np.mean(all_mc_scores, axis=0)
        std_raw  = np.std(all_mc_scores, axis=0)

        # Apply regime-specific veto thresholds
        veto_mask = np.zeros(N, dtype=bool)
        for i in range(N):
            r = regimes[i] if regimes is not None else 1
            thresh = self._veto_by_regime.get(int(r), self._base_veto_threshold)
            veto_mask[i] = std_raw[i] > thresh

        # Scale non-vetoed to [0, 100] using Youden threshold
        t = self.threshold
        mean_scaled = np.where(
            mean_raw < t,
            (mean_raw / (t + 1e-9)) * 50,
            50 + ((mean_raw - t) / (1.0 - t + 1e-9)) * 50
        )
        mean_scaled = np.clip(mean_scaled, 0, 100)
        mean_scaled[veto_mask] = 50.0   # Override vetoed → neutral HOLD

        num_vetoed = np.sum(veto_mask)
        logger.info(f"  [MC Veto] {num_vetoed}/{N} suppressed ({(num_vetoed/N)*100:.1f}%)")
        print(f"    [MC Veto] {num_vetoed}/{N} suppressed ({(num_vetoed/N)*100:.1f}%)")

        return mean_scaled

    def _predict_raw(self,
                     tcn_probs: np.ndarray,
                     lgbm_probs: np.ndarray,
                     gru_probs: np.ndarray = None) -> np.ndarray:
        """Return raw probability scores in [0,1] (not scaled to 0-100)."""
        bull = lgbm_probs[:, 0] + lgbm_probs[:, 1]
        gru_v = gru_probs.flatten() if gru_probs is not None else None

        if not self.is_fitted:
            return self._rank_blend_scores(tcn_probs.flatten(), bull, gru_v)

        if self.use_rank_blend:
            return self._rank_blend_scores(tcn_probs.flatten(), bull, gru_v)

        # Stacker path
        X    = self._build_features(tcn_probs, lgbm_probs, gru_probs)
        X_sc = self.scaler.transform(X)
        return self.model.predict_proba(X_sc)[:, 1]

    def predict_batch(self,
                      tcn_probs: np.ndarray,
                      lgbm_probs: np.ndarray,
                      gru_probs: np.ndarray = None) -> np.ndarray:
        """Batch prediction scaled to [0, 100] (deterministic, no MC uncertainty)."""
        raw = self._predict_raw(tcn_probs, lgbm_probs, gru_probs)
        t   = self.threshold
        scaled = np.where(
            raw < t,
            (raw / (t + 1e-9)) * 50,
            50 + ((raw - t) / (1.0 - t + 1e-9)) * 50
        )
        return np.clip(scaled, 0, 100)

    def predict(self,
                tcn_prob: float,
                lgbm_probs: np.ndarray,
                gru_prob: float = None,
                regime: int = None) -> float:
        """
        Single-sample prediction scaled to [0, 100].

        Backward-compatible wrapper around predict_batch() for live inference.
        Called by main.py, stock_api.py, and run_ablation_worker.py.

        Args:
            tcn_prob  : Scalar TCN probability.
            lgbm_probs: (4,) array of LGBM class probabilities.
            gru_prob  : Optional scalar GRU probability.
            regime    : Optional regime (unused — kept for old call-site compat).
        """
        tcn_arr  = np.array([tcn_prob])
        lgbm_arr = np.array(lgbm_probs).reshape(1, -1)
        gru_arr  = np.array([gru_prob]) if gru_prob is not None else None
        scores   = self.predict_batch(tcn_arr, lgbm_arr, gru_probs=gru_arr)
        return float(scores[0])
