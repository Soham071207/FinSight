"""Quick smoke test for the TS-TCC framework."""
import os, sys, warnings
warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import tensorflow as tf

from tcn_model import TCNPredictor
from ts_tcc import (
    TSAugmenter, build_projection_head,
    build_temporal_cross_predictor, nt_xent_loss,
    TSTCCPretrainer, build_pretrain_sequences
)

# ── Dummy data ────────────────────────────────────────────────────────────────
N_STOCKS = 5
ROWS_PER = 150
FEATURES = 20
LOOKBACK = 60

feature_cols = [f"f{i}" for i in range(FEATURES)]

# Simulate 5 tickers, 150 rows each
np.random.seed(42)
all_X_dfs = [
    pd.DataFrame(np.random.randn(ROWS_PER, FEATURES).astype("float32"), columns=feature_cols)
    for _ in range(N_STOCKS)
]

print("=" * 55)
print("  TS-TCC Smoke Test")
print("=" * 55)

# ── 1. Augmentations ──────────────────────────────────────────────────────────
print("\n[1] Testing TSAugmenter...")
aug = TSAugmenter()
x_sample = np.random.randn(LOOKBACK, FEATURES).astype("float32")
x_weak   = aug.weak_augment(x_sample)
x_strong = aug.strong_augment(x_sample)
assert x_weak.shape == x_strong.shape == (LOOKBACK, FEATURES), "Augment shape mismatch"
print(f"    weak shape  : {x_weak.shape}  OK")
print(f"    strong shape: {x_strong.shape}  OK")

X_batch = np.random.randn(8, LOOKBACK, FEATURES).astype("float32")
x_w, x_s = aug.augment_batch(X_batch)
assert x_w.shape == x_s.shape == (8, LOOKBACK, FEATURES)
print(f"    batch aug   : {x_w.shape}  OK")

# ── 2. NT-Xent Loss ───────────────────────────────────────────────────────────
print("\n[2] Testing NT-Xent loss...")
z1 = tf.random.normal((16, 128))
z2 = tf.random.normal((16, 128))
loss = nt_xent_loss(z1, z2, temperature=0.07)
assert loss.numpy() > 0
print(f"    NT-Xent loss: {loss.numpy():.4f}  OK")

# ── 3. Build sequences ────────────────────────────────────────────────────────
print("\n[3] Building pretrain sequences...")
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
combined = pd.concat(all_X_dfs, ignore_index=True)
scaler.fit(combined.values)

X_all = build_pretrain_sequences(all_X_dfs, feature_cols, scaler, LOOKBACK)
assert X_all.shape == (N_STOCKS * (ROWS_PER - LOOKBACK), LOOKBACK, FEATURES)
print(f"    X_all shape : {X_all.shape}  OK")

# ── 4. Build TCN encoder ──────────────────────────────────────────────────────
print("\n[4] Building TCNPredictor + encoder sub-model...")
tcn = TCNPredictor(feature_cols)
tcn.scaler = scaler
tcn.model  = tcn._build_model(FEATURES)
encoder    = tcn.get_encoder_model()

test_in  = tf.random.normal((4, LOOKBACK, FEATURES))
test_out = encoder(test_in, training=False)
print(f"    Encoder input : {test_in.shape}")
print(f"    Encoder output: {test_out.shape}  OK")

# ── 5. TS-TCC Pretrainer (3 epochs, tiny batch) ───────────────────────────────
print("\n[5] Running TSTCCPretrainer (3 quick epochs)...")
pretrainer = TSTCCPretrainer(
    tcn_predictor    = tcn,
    n_features       = FEATURES,
    temperature      = 0.07,
    lambda_temporal  = 0.5,
    gru_units        = 16,
    proj_hidden_dim  = 32,
    proj_output_dim  = 16,
    lr               = 3e-4,
    warmup_steps     = 5,
)

pretrainer.pretrain(X_all, epochs=3, batch_size=16)
print("    Pre-training loop  OK")

# ── 6. Save encoder ───────────────────────────────────────────────────────────
print("\n[6] Testing save/load encoder weights...")
save_path = "ts_tcc_test_encoder.weights.h5"
pretrainer.save_encoder(save_path)
tcn2   = TCNPredictor(feature_cols)
tcn2.model = tcn2._build_model(FEATURES)
tcn2.load_pretrained_encoder(save_path)
os.remove(save_path)
print(f"    Save/load weights  OK")

print("\n" + "=" * 55)
print("  ALL TS-TCC SMOKE TESTS PASSED")
print("=" * 55)
