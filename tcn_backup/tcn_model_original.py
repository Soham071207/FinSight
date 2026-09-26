"""
tcn_model.py — Temporal Convolutional Network (TCN) deep-learning predictor.

Architecture:
  Dilated causal convolutions (dilations 1,2,4,8,16) -> AdditiveAttention -> Dense(32, L2) -> Dense(1)

Input : sequence of (lookback × n_features) — scaled OHLCV + technical + sentiment
Output: next-day return probability  (0 = bearish, 1 = bullish)

Replaces the standard TCN to avoid vanishing gradients over the 60-day window.
Training uses TimeSeriesSplit-compatible windows (no shuffling).
"""

import warnings
warnings.filterwarnings("ignore")

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import numpy as np
import pandas as pd
import logging
import random

from sklearn.preprocessing import StandardScaler
from config import CONFIG

logger = logging.getLogger(__name__)

# Lazy Keras imports
try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, optimizers, callbacks, regularizers
    HAS_KERAS = True
except ImportError:
    HAS_KERAS = False
    logger.warning("TensorFlow/Keras not available. TCN predictions will be 0.5.")



def residual_tcn_block(x, filters, kernel_size, dilation_rate, dropout=0.3):
    """One dilated-causal-conv residual block"""
    prev_x = x
    for _ in range(2):
        x = layers.Conv1D(
            filters=filters,
            kernel_size=kernel_size,
            dilation_rate=dilation_rate,
            padding="causal",
        )(x)
        x = layers.BatchNormalization()(x)
        x = layers.ReLU()(x)
        x = layers.Dropout(dropout)(x)

    # Match channel dims for the residual add if needed
    if prev_x.shape[-1] != filters:
        prev_x = layers.Conv1D(filters, 1, padding="same")(prev_x)

    return layers.Add()([prev_x, x])

class TCNPredictor:
    """
    TCN model that predicts next-day return probability.
    Drop-in replacement for TCNPredictor.

    Usage:
        predictor = TCNPredictor(feature_cols)
        predictor.tune(X_train_df, y_train_series, trials=10)
        predictor.fit(X_train_df, y_train_series)
        probs = predictor.predict(X_test_df)
    """

    def __init__(self, feature_cols: list):
        self.feature_cols = feature_cols
        self.lookback     = CONFIG.get("tcn_lookback", 60)
        self.filters      = CONFIG.get("tcn_filters", 128)
        self.dropout      = CONFIG.get("tcn_dropout", 0.2)
        self.epochs       = CONFIG.get("tcn_epochs", 30)
        self.batch_size   = CONFIG.get("tcn_batch_size", 32)
        self.lr           = CONFIG.get("tcn_learning_rate", 0.001)
        self.dense_units  = CONFIG.get("tcn_dense_units", 32)
        self.model        = None
        self.scaler       = StandardScaler()

    # ── Sequence Creation ─────────────────────────────────────────────────

    def _create_sequences(self, X: np.ndarray, y: np.ndarray):
        Xs, ys = [], []
        for i in range(self.lookback, len(X)):
            Xs.append(X[i - self.lookback : i])
            ys.append(y[i])
        return np.array(Xs), np.array(ys)

    # ── Model Build ───────────────────────────────────────────────────────

    def _build_model(self, n_features: int):
        inputs = layers.Input(shape=(self.lookback, n_features))
        x = inputs
        
        for dilation in [1, 2, 4, 8, 16]:
            x = residual_tcn_block(x, filters=self.filters, kernel_size=3,
                                    dilation_rate=dilation, dropout=self.dropout)

        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dense(self.dense_units, activation="relu", kernel_regularizer=regularizers.l2(1e-4))(x)
        x = layers.Dropout(self.dropout)(x)
        outputs = layers.Dense(1, activation="sigmoid", kernel_regularizer=regularizers.l2(1e-4))(x)

        model = models.Model(inputs, outputs, name="TCN_Attention_DirectionClassifier")
        model.compile(
            optimizer=optimizers.Adam(learning_rate=self.lr),
            loss="binary_crossentropy",
            metrics=["accuracy", tf.keras.metrics.AUC(name="auc")],
        )
        return model

    # ── Tuning ────────────────────────────────────────────────────────────

    def tune(self, X_df: pd.DataFrame, y_series: pd.Series, trials: int = 10):
        if not HAS_KERAS:
            return self

        logger.info(f"  [TCN] Starting Random Search Hyperparameter Tuning ({trials} trials)...")
        print(f"  [TCN] Starting Random Search Hyperparameter Tuning ({trials} trials)...")

        X_scaled = self.scaler.fit_transform(X_df[self.feature_cols].values)
        y_vals   = y_series.values.astype(float)
        X_seq, y_seq = self._create_sequences(X_scaled, y_vals)

        if len(X_seq) < 100:
            return self

        # Use the last 20% of training data as chronologically sound validation set
        val_split = int(len(X_seq) * 0.8)
        X_tr, y_tr = X_seq[:val_split], y_seq[:val_split]
        X_va, y_va = X_seq[val_split:], y_seq[val_split:]
        n_features = X_seq.shape[2]

        best_auc = -1.0
        best_params = {}

        for i in range(trials):
            # Randomly select hyperparameters
            filters = random.choice([64, 128])
            dropout = random.choice([0.2, 0.3, 0.4])
            lr = random.choice([0.001, 0.0005, 0.0001])
            dense_units = random.choice([16, 32, 64])

            # Temporarily set them for the build function
            self.filters = filters
            self.dropout = dropout
            self.lr = lr
            self.dense_units = dense_units

            model = self._build_model(n_features)
            early_stop = callbacks.EarlyStopping(monitor="val_auc", patience=5, mode="max", restore_best_weights=True)
            reduce_lr = callbacks.ReduceLROnPlateau(monitor="val_auc", mode="max", factor=0.5, patience=3, min_lr=1e-5, verbose=0)

            model.fit(
                X_tr, y_tr,
                epochs=15, # Fast epochs for tuning
                batch_size=self.batch_size,
                validation_data=(X_va, y_va),
                shuffle=False,
                callbacks=[early_stop, reduce_lr],
                verbose=0,
            )

            val_auc = model.history.history.get("val_auc", [-1])[-1]
            print(f"    Trial {i+1}/{trials} | Filters: {filters}, Drop: {dropout}, LR: {lr}, Dense: {dense_units} => Val AUC: {val_auc:.4f}")

            if val_auc > best_auc:
                best_auc = val_auc
                best_params = {
                    "filters": filters,
                    "dropout": dropout,
                    "lr": lr,
                    "dense_units": dense_units
                }

        if best_params:
            print(f"  [TCN] Best Params Found: {best_params} (Val AUC: {best_auc:.4f})")
            self.filters = best_params["filters"]
            self.dropout = best_params["dropout"]
            self.lr = best_params["lr"]
            self.dense_units = best_params["dense_units"]

        return self

    # ── Training ──────────────────────────────────────────────────────────

    def fit(self, X_df: pd.DataFrame, y_series: pd.Series):
        if not HAS_KERAS:
            logger.warning("Keras unavailable — skipping TCN training")
            return self

        X_scaled = self.scaler.fit_transform(X_df[self.feature_cols].values)
        y_vals   = y_series.values.astype(float)

        X_seq, y_seq = self._create_sequences(X_scaled, y_vals)

        if len(X_seq) < 50:
            logger.warning("Not enough data for TCN training")
            return self

        n_features = X_seq.shape[2]
        self.model = self._build_model(n_features)

        early_stop = callbacks.EarlyStopping(
            monitor="val_loss", patience=8, restore_best_weights=True
        )
        
        reduce_lr = callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5, verbose=1
        )

        self.model.fit(
            X_seq, y_seq,
            epochs=self.epochs,
            batch_size=self.batch_size,
            validation_split=0.15,
            shuffle=False,
            callbacks=[early_stop, reduce_lr],
            verbose=0,
        )

        val_loss = self.model.history.history.get("val_loss", [0])[-1]
        val_auc  = self.model.history.history.get("val_auc", [0])[-1]
        logger.info(f"  TCN trained: val_loss={val_loss:.4f}, val_auc={val_auc:.3f}")

        return self

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, X_df: pd.DataFrame) -> pd.Series:
        if self.model is None or not HAS_KERAS:
            return pd.Series(0.5, index=X_df.index, name="tcn_prob")

        X_scaled = self.scaler.transform(X_df[self.feature_cols].values)
        X_seq, _ = self._create_sequences(X_scaled, np.zeros(len(X_scaled)))

        if len(X_seq) == 0:
            return pd.Series(0.5, index=X_df.index, name="tcn_prob")

        preds = self.model.predict(X_seq, verbose=0).flatten()

        pred_index = X_df.index[self.lookback:]
        result = pd.Series(preds, index=pred_index, name="tcn_prob")

        full = pd.Series(0.5, index=X_df.index, name="tcn_prob")
        full.loc[pred_index] = result
        return full

    def predict_single(self, X_df: pd.DataFrame) -> float:
        if self.model is None or not HAS_KERAS:
            return 0.5

        if len(X_df) < self.lookback:
            return 0.5

        X_recent = X_df[self.feature_cols].iloc[-self.lookback:]
        X_scaled = self.scaler.transform(X_recent.values)
        X_seq    = np.array([X_scaled])

        prob = float(self.model.predict(X_seq, verbose=0)[0][0])
        return prob

    def predict_with_uncertainty(self, X_df: pd.DataFrame, n_iter: int = 50) -> tuple:
        """
        Monte Carlo (MC) Dropout prediction to capture epistemic uncertainty.
        Keeps Dropout active during inference by passing `training=True`.
        
        Returns:
            (mean_probability, epistemic_uncertainty_std)
        """
        if self.model is None or not HAS_KERAS:
            return 0.5, 0.0

        if len(X_df) < self.lookback:
            return 0.5, 0.0

        X_recent = X_df[self.feature_cols].iloc[-self.lookback:]
        X_scaled = self.scaler.transform(X_recent.values)
        X_seq    = np.array([X_scaled])

        # Run multiple forward passes with Dropout enabled
        mc_preds = []
        for _ in range(n_iter):
            # Using model(X, training=True) forces Dropout to remain active
            pred = self.model(X_seq, training=True)
            mc_preds.append(float(pred[0][0]))
            
        mean_prob = np.mean(mc_preds)
        uncertainty = np.std(mc_preds)
        
        return mean_prob, uncertainty
