"""
FIX #3: Replace LSTM with a Temporal Convolutional Network (TCN)
===================================================================
PROBLEM:  Standalone LSTM gets 51.2% accuracy, AUC 0.509 -- barely above
          noise. It's your weakest individual component and drags on
          whatever the meta-learner can do with its output.

FIX:      TCN uses dilated causal convolutions instead of recurrence.
          Advantages for your use case:
            - No vanishing/exploding gradients over the 60-day window
              (LSTMs can struggle here even with gating)
            - Trains faster, more stable on small/medium financial datasets
            - Wider effective receptive field per layer via dilation
              (e.g., dilations 1,2,4,8,16 cover the full 60-day window
              in just 5-6 layers)
          This is a drop-in replacement: same input shape (60, n_features),
          same sigmoid output, same training loop you already have.

ALSO INCLUDED: an attention-augmented LSTM variant, in case you want to
keep the LSTM (e.g., for the "we compare LSTM vs LSTM+Attention vs TCN"
ablation story) rather than fully replacing it.
"""

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models, callbacks, optimizers


# ---------------------------------------------------------------------------
# Option A: TCN (recommended primary replacement)
# ---------------------------------------------------------------------------

def residual_tcn_block(x, filters, kernel_size, dilation_rate, dropout=0.3):
    """
    One dilated-causal-conv residual block:
    Conv -> BatchNorm -> ReLU -> Dropout -> Conv -> BatchNorm -> ReLU -> Dropout -> + residual
    """
    prev_x = x
    for _ in range(2):
        x = layers.Conv1D(
            filters=filters,
            kernel_size=kernel_size,
            dilation_rate=dilation_rate,
            padding="causal",          # critical: causal padding = no future leakage
        )(x)
        x = layers.BatchNormalization()(x)
        x = layers.ReLU()(x)
        x = layers.Dropout(dropout)(x)

    # Match channel dims for the residual add if needed
    if prev_x.shape[-1] != filters:
        prev_x = layers.Conv1D(filters, 1, padding="same")(prev_x)

    return layers.Add()([prev_x, x])


def build_tcn_model(lookback: int, n_features: int, filters: int = 64, dropout: float = 0.3):
    """
    Drop-in replacement for your 2-layer LSTM(128->64).
    Input shape: (lookback, n_features) -- same (60, n_features) you already use.
    Output: single sigmoid unit, same as your current Dense(1, activation='sigmoid').
    """
    inputs = layers.Input(shape=(lookback, n_features))

    x = inputs
    # Dilations 1,2,4,8,16 -> receptive field covers the full 60-day window
    for dilation in [1, 2, 4, 8, 16]:
        x = residual_tcn_block(x, filters=filters, kernel_size=3,
                                dilation_rate=dilation, dropout=dropout)

    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(dropout)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)

    model = models.Model(inputs, outputs, name="TCN_DirectionClassifier")
    model.compile(
        optimizer=optimizers.Adam(learning_rate=0.001),
        loss="binary_crossentropy",
        metrics=["accuracy", tf.keras.metrics.AUC(name="auc")],
    )
    return model


# ---------------------------------------------------------------------------
# Option B: LSTM + Attention (keep LSTM, add attention on top)
# ---------------------------------------------------------------------------

class AdditiveAttention(layers.Layer):
    """
    Simple additive (Bahdanau-style) attention over the LSTM's per-timestep
    outputs. Lets the model learn to weight, e.g., "3 days ago" more than
    "day 47" instead of relying only on the LSTM's final hidden state.
    """

    def __init__(self, units=64, **kwargs):
        super().__init__(**kwargs)
        self.units = units
        self.W = layers.Dense(units)
        self.V = layers.Dense(1)

    def call(self, encoder_outputs):
        # encoder_outputs: (batch, timesteps, hidden_dim)
        score = self.V(tf.nn.tanh(self.W(encoder_outputs)))  # (batch, timesteps, 1)
        attention_weights = tf.nn.softmax(score, axis=1)      # (batch, timesteps, 1)
        context = attention_weights * encoder_outputs
        context = tf.reduce_sum(context, axis=1)              # (batch, hidden_dim)
        return context, attention_weights


def build_lstm_attention_model(lookback: int, n_features: int, dropout: float = 0.3):
    """
    Same 2-layer LSTM(128->64) you already have, but layer 2 now returns
    full sequences (not just the final state) and feeds an attention layer.
    This is the minimal-change option if you want to keep LSTM as your
    base architecture but improve it.
    """
    inputs = layers.Input(shape=(lookback, n_features))

    x = layers.LSTM(128, return_sequences=True, dropout=dropout)(inputs)
    x = layers.LSTM(64, return_sequences=True, dropout=dropout)(x)  # NOTE: True now, not False

    context, attn_weights = AdditiveAttention(units=64, name="attention")(x)

    x = layers.Dense(32, activation="relu")(context)
    x = layers.Dropout(dropout)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)

    model = models.Model(inputs, outputs, name="LSTM_Attention_DirectionClassifier")
    model.compile(
        optimizer=optimizers.Adam(learning_rate=0.001),
        loss="binary_crossentropy",
        metrics=["accuracy", tf.keras.metrics.AUC(name="auc")],
    )
    return model


# ---------------------------------------------------------------------------
# Shared training utility (same config as your paper: batch=32, epochs=50,
# early stopping patience=5, best-weight restoration)
# ---------------------------------------------------------------------------

def train_sequence_model(model, X_train, y_train, X_val, y_val, epochs=50, batch_size=32):
    early_stop = callbacks.EarlyStopping(
        monitor="val_auc", mode="max", patience=5,
        restore_best_weights=True,
    )
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stop],
        verbose=2,
    )
    return history


if __name__ == "__main__":
    # Smoke test: synthetic data shaped like your real (60, n_features) windows
    rng = np.random.default_rng(42)
    n_samples, lookback, n_features = 600, 60, 10

    X = rng.normal(0, 1, (n_samples, lookback, n_features)).astype("float32")
    # Inject a weak learnable signal so training isn't pure noise
    signal = X[:, -1, 0] + X[:, -5, 1] * 0.5
    y = (signal > np.median(signal)).astype("float32")

    split = int(n_samples * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    print("=== Building TCN ===")
    tcn = build_tcn_model(lookback, n_features)
    tcn.summary()
    train_sequence_model(tcn, X_train, y_train, X_val, y_val, epochs=5)

    print("\n=== Building LSTM + Attention ===")
    lstm_attn = build_lstm_attention_model(lookback, n_features)
    lstm_attn.summary()
    train_sequence_model(lstm_attn, X_train, y_train, X_val, y_val, epochs=5)
