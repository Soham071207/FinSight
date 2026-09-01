"""
lstm_model.py — LSTM/GRU deep-learning predictor.

Architecture:
  LSTM(128) → Dropout(0.3) → LSTM(64) → Dropout(0.3)
  → Dense(32, relu) → Dense(1, sigmoid)

Input : sequence of (lookback × n_features) — scaled OHLCV + technical + sentiment
Output: next-day return probability  (0 = bearish, 1 = bullish)

Training uses TimeSeriesSplit-compatible windows (no shuffling).
"""

import warnings
warnings.filterwarnings("ignore")

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import numpy as np
import pandas as pd
import logging

from sklearn.preprocessing import StandardScaler

from config import CONFIG

logger = logging.getLogger(__name__)

# Lazy Keras imports
try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, GRU, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping
    HAS_KERAS = True
except ImportError:
    HAS_KERAS = False
    logger.warning("TensorFlow/Keras not available. LSTM predictions will be 0.5.")


class LSTMPredictor:
    """
    LSTM model that predicts next-day return probability.

    Usage:
        predictor = LSTMPredictor(feature_cols)
        predictor.fit(X_train_df, y_train_series)
        probs = predictor.predict(X_test_df)  # returns pd.Series of probabilities
    """

    def __init__(self, feature_cols: list):
        self.feature_cols = feature_cols
        self.lookback     = CONFIG["lstm_lookback"]
        self.units        = CONFIG["lstm_units"]       # [128, 64]
        self.dropout      = CONFIG["lstm_dropout"]     # 0.3
        self.epochs       = CONFIG["lstm_epochs"]      # 30
        self.batch_size   = CONFIG["lstm_batch_size"]  # 32
        self.lr           = CONFIG["lstm_learning_rate"]
        self.model        = None
        self.scaler       = StandardScaler()

    # ── Sequence Creation ─────────────────────────────────────────────────

    def _create_sequences(self, X: np.ndarray, y: np.ndarray):
        """
        Convert 2-D arrays into 3-D sequences for LSTM.
        X shape: (samples, features) → (samples - lookback, lookback, features)
        y shape: (samples,)          → (samples - lookback,)
        """
        Xs, ys = [], []
        for i in range(self.lookback, len(X)):
            Xs.append(X[i - self.lookback : i])
            ys.append(y[i])
        return np.array(Xs), np.array(ys)

    # ── Model Build ───────────────────────────────────────────────────────

    def _build_model(self, n_features: int):
        """Build LSTM architecture."""
        model = Sequential([
            # First LSTM layer — returns sequences for stacking
            LSTM(self.units[0], return_sequences=True,
                 input_shape=(self.lookback, n_features)),
            Dropout(self.dropout),

            # Second LSTM layer — returns final hidden state
            LSTM(self.units[1], return_sequences=False),
            Dropout(self.dropout),

            # Dense classifier head
            Dense(32, activation="relu"),
            Dense(1, activation="sigmoid"),  # probability output
        ])
        model.compile(
            optimizer=Adam(learning_rate=self.lr),
            loss="binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    # ── Training ──────────────────────────────────────────────────────────

    def fit(self, X_df: pd.DataFrame, y_series: pd.Series):
        """
        Train the LSTM on feature DataFrame + binary label Series.

        Args:
            X_df     : DataFrame with feature columns (time-ordered)
            y_series : Series with binary labels (1 = up, 0 = down)
        """
        if not HAS_KERAS:
            logger.warning("Keras unavailable — skipping LSTM training")
            return self

        # Scale features
        X_scaled = self.scaler.fit_transform(X_df[self.feature_cols].values)
        y_vals   = y_series.values.astype(float)

        # Create sequences
        X_seq, y_seq = self._create_sequences(X_scaled, y_vals)

        if len(X_seq) < 50:
            logger.warning("Not enough data for LSTM training")
            return self

        # Build model
        n_features = X_seq.shape[2]
        self.model = self._build_model(n_features)

        # Early stopping to prevent overfitting
        early_stop = EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        )

        # Train (no shuffle — time series!)
        self.model.fit(
            X_seq, y_seq,
            epochs=self.epochs,
            batch_size=self.batch_size,
            validation_split=0.15,
            shuffle=False,          # CRITICAL: no random shuffle for time series
            callbacks=[early_stop],
            verbose=0,
        )

        # Log training summary
        val_loss = self.model.history.history.get("val_loss", [0])[-1]
        val_acc  = self.model.history.history.get("val_accuracy", [0])[-1]
        logger.info(f"  LSTM trained: val_loss={val_loss:.4f}, val_acc={val_acc:.3f}")

        return self

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, X_df: pd.DataFrame) -> pd.Series:
        """
        Predict next-day return probabilities for the given features.

        Args:
            X_df : DataFrame with same feature columns as training

        Returns:
            pd.Series of probabilities indexed like X_df (trimmed by lookback)
        """
        if self.model is None or not HAS_KERAS:
            # Fallback: return 0.5 (neutral)
            return pd.Series(0.5, index=X_df.index, name="lstm_prob")

        X_scaled = self.scaler.transform(X_df[self.feature_cols].values)
        X_seq, _ = self._create_sequences(X_scaled, np.zeros(len(X_scaled)))

        if len(X_seq) == 0:
            return pd.Series(0.5, index=X_df.index, name="lstm_prob")

        preds = self.model.predict(X_seq, verbose=0).flatten()

        # Align index: predictions start at index[lookback]
        pred_index = X_df.index[self.lookback:]
        result = pd.Series(preds, index=pred_index, name="lstm_prob")

        # Backfill the first `lookback` rows with 0.5
        full = pd.Series(0.5, index=X_df.index, name="lstm_prob")
        full.loc[pred_index] = result
        return full

    def predict_single(self, X_df: pd.DataFrame) -> float:
        """
        Predict probability for the most recent data point.
        Expects X_df to have at least `lookback` rows.
        """
        if self.model is None or not HAS_KERAS:
            return 0.5

        if len(X_df) < self.lookback:
            return 0.5

        # Take last `lookback` rows
        X_recent = X_df[self.feature_cols].iloc[-self.lookback:]
        X_scaled = self.scaler.transform(X_recent.values)
        X_seq    = np.array([X_scaled])  # shape (1, lookback, features)

        prob = float(self.model.predict(X_seq, verbose=0)[0][0])
        return prob
