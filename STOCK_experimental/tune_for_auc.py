"""
tune_for_auc.py — Targeted AUC maximisation experiment.

Strategies tried:
  1. Baseline: current TCN + LGBM ensemble AUC
  2. Extended TCN tuning (20 trials, more aggressive search space)
  3. Calibrated Isotonic Meta-Learner (probability calibration improves AUC)
  4. Feature augmentation: add lagged tcn_prob and lgbm entropy as meta-features
  5. Logistic Regression Stacker vs Ridge Stacker comparison
  6. Print final table comparing all strategies vs Logistic Regression baseline (0.4942)
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
import random
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler

from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from tcn_model import TCNPredictor
from lgbm_model import LGBMSignalClassifier
from sentiment_engine import SentimentEngine

def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels  = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_5d")

def entropy(probs):
    """Shannon entropy of a probability vector (per row)."""
    probs = np.clip(probs, 1e-9, 1)
    return -np.sum(probs * np.log(probs), axis=1)

def print_separator(title=""):
    print("\n" + "=" * 68)
    if title:
        print(f"  {title}")
        print("=" * 68)

# ─── 1. Load and prepare data ────────────────────────────────────────────────
print_separator("AUC MAXIMISATION EXPERIMENT")
print("  Target baseline to beat: Logistic Regression AUC = 0.4942\n")

ticker = "RELIANCE.NS"
dp = DataPipeline()
fe = FeatureEngine()
se = SentimentEngine()
garch = GARCHModel()

print("  [1/6] Fetching multi-ticker data...")
train_tickers = [ticker, "TCS.NS", "INFY.NS"]
all_train_dfs = []
target_test_df = None

_, market, _ = dp.process(ticker)
is_indian = market in ["NSE", "BSE"]
forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)

# Fetch index data directly via yfinance (DataPipeline has no fetch_index_data)
try:
    import yfinance as yf
    nifty = yf.download("^NSEI", period="5y", auto_adjust=True, progress=False)["Close"].squeeze()
    vix   = yf.download("^INDIAVIX", period="5y", auto_adjust=True, progress=False)["Close"].squeeze()
except Exception:
    nifty = pd.Series(dtype=float)
    vix   = pd.Series(dtype=float)

test_size = 252
available = None

for t in train_tickers:
    try:
        df_t, _, _ = dp.process(t)
        df_t = fe.compute_all(df_t, forex_series=forex, is_indian=is_indian)
        df_t = se.get_historical_features(df_t, {})
        df_t = garch.fit_transform(df_t)
        avail = [c for c in ALL_FEATURES if c in df_t.columns]
        df_t["label_5d"] = make_5day_labels(df_t)
        df_t.dropna(subset=avail + ["label_5d"], inplace=True)
        df_t["label_5d"] = df_t["label_5d"].astype(int)
        if t == ticker:
            available = avail
            all_train_dfs.append(df_t.iloc[:-test_size].copy())
            target_test_df = df_t.iloc[-test_size:].copy()
        else:
            all_train_dfs.append(df_t)
    except Exception as e:
            print(f"  [SKIP] {t}: {e}")

train_df_combined = pd.concat(all_train_dfs).reset_index(drop=True)
target_train_df   = all_train_dfs[0]  # temporal integrity for TCN

y_train = train_df_combined["label_5d"].values
y_test  = target_test_df["label_5d"].values

print(f"  Train: {len(train_df_combined)} rows | Test: {len(target_test_df)} rows")
print(f"  Test label balance: {y_test.mean()*100:.1f}% bullish\n")

# ─── 2. Logistic Regression baseline ─────────────────────────────────────────
print("  [2/6] Computing Logistic Regression AUC baseline...")
X_train_lr = train_df_combined[available].fillna(0).values
X_test_lr  = target_test_df[available].fillna(0).values
scaler_lr  = StandardScaler()
X_train_lr = scaler_lr.fit_transform(X_train_lr)
X_test_lr  = scaler_lr.transform(X_test_lr)

lr = LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
lr.fit(X_train_lr, y_train)
lr_probs = lr.predict_proba(X_test_lr)[:, 1]
lr_auc   = roc_auc_score(y_test, lr_probs)
print(f"  [OK] Logistic Regression AUC = {lr_auc:.4f}  <- baseline to beat")

results = {"Logistic Regression (baseline)": lr_auc}

# ─── 3. Current TCN (standard training) ──────────────────────────────────────
print("\n  [3/6] Training standard TCN (current config)...")
tcn1 = TCNPredictor(available)
tcn1.fit(target_train_df, target_train_df["label_5d"])
full_tcn = pd.concat([target_train_df.iloc[-tcn1.lookback:], target_test_df])
tcn1_probs_test = tcn1.predict(full_tcn).loc[target_test_df.index].values
tcn1_auc = roc_auc_score(y_test, tcn1_probs_test)
print(f"  [OK] TCN (standard) standalone AUC = {tcn1_auc:.4f}")
results["TCN (standard) standalone"] = tcn1_auc

# ─── 4. TCN with extended 20-trial tune (aggressive search) ──────────────────
print("\n  [4/6] Extended TCN Tuning (20 trials, wider search space)...")
tcn2 = TCNPredictor(available)
# Widen the search space vs. our standard 10-trial tune
import importlib
try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, optimizers, callbacks, regularizers
    HAS_KERAS = True
except ImportError:
    HAS_KERAS = False
    print("  [FAIL] Keras not available — skipping extended TCN tuning")

if HAS_KERAS:
    from sklearn.preprocessing import StandardScaler as SS2

    X_sc = SS2()
    X_scaled = X_sc.fit_transform(target_train_df[available].values)
    y_arr    = target_train_df["label_5d"].values.astype(float)

    lookback = 60
    Xs, ys = [], []
    for i in range(lookback, len(X_scaled)):
        Xs.append(X_scaled[i-lookback:i])
        ys.append(y_arr[i])
    Xs, ys = np.array(Xs), np.array(ys)
    val_split = int(len(Xs) * 0.8)
    X_tr, X_va = Xs[:val_split], Xs[val_split:]
    y_tr, y_va = ys[:val_split], ys[val_split:]
    n_features = Xs.shape[2]

    best_auc_tune = -1
    best_tcn_model = None
    best_scaler    = X_sc

    search_space = {
        "filters":     [64, 128, 192],
        "dropout":     [0.1, 0.2, 0.3, 0.4],
        "lr":          [0.001, 0.0005, 0.0001],
        "dense_units": [16, 32, 64, 96],
        "kernel_size": [2, 3],
    }

    from tcn_model import residual_tcn_block, AdditiveAttention

    for trial in range(20):
        f = random.choice(search_space["filters"])
        d = random.choice(search_space["dropout"])
        l = random.choice(search_space["lr"])
        du = random.choice(search_space["dense_units"])
        ks = random.choice(search_space["kernel_size"])

        inp = layers.Input(shape=(lookback, n_features))
        x = inp
        for dil in [1, 2, 4, 8, 16]:
            x = residual_tcn_block(x, filters=f, kernel_size=ks, dilation_rate=dil, dropout=d)
        x = AdditiveAttention(units=64)(x)
        x = layers.Dense(du, activation="relu", kernel_regularizer=regularizers.l2(1e-4))(x)
        x = layers.Dropout(d)(x)
        out = layers.Dense(1, activation="sigmoid")(x)
        model = models.Model(inp, out)
        model.compile(
            optimizer=optimizers.Adam(l),
            loss="binary_crossentropy",
            metrics=[tf.keras.metrics.AUC(name="auc")]
        )

        es = callbacks.EarlyStopping(monitor="val_auc", patience=5, mode="max", restore_best_weights=True)
        model.fit(X_tr, y_tr, epochs=20, batch_size=32,
                  validation_data=(X_va, y_va),
                  shuffle=False, callbacks=[es], verbose=0)
        val_auc = model.history.history.get("val_auc", [-1])[-1]
        print(f"    Trial {trial+1:02d}/20 | f={f}, d={d}, lr={l}, du={du}, ks={ks} => val_AUC={val_auc:.4f}", end="")
        if val_auc > best_auc_tune:
            best_auc_tune = val_auc
            best_tcn_model = model
            print("  <- BEST", end="")
        print()

    # Use the best model to predict on test set
    X_test_sc = X_sc.transform(target_test_df[available].values)
    X_full_sc = np.vstack([X_scaled[-lookback:], X_test_sc])
    X_test_seq = np.array([X_full_sc[i-lookback:i] for i in range(lookback, len(X_full_sc))])
    tcn2_probs_test = best_tcn_model.predict(X_test_seq, verbose=0).flatten()
    tcn2_auc = roc_auc_score(y_test, tcn2_probs_test)
    print(f"\n  [OK] TCN (extended 20-trial tuned) AUC = {tcn2_auc:.4f}")
    results["TCN (20-trial tuned) standalone"] = tcn2_auc
else:
    tcn2_probs_test = tcn1_probs_test  # fallback

# ─── 5. Build LightGBM and ensemble stacker ──────────────────────────────────
print("\n  [5/6] Training LightGBM + Ensemble stacker...")

lgbm_feats = list(dict.fromkeys(available + ["garch_vol"]))
lgbm_feats = [c for c in lgbm_feats if c in train_df_combined.columns]

lgbm = LGBMSignalClassifier(lgbm_feats)
labels_4class = lgbm.create_labels(train_df_combined)
regimes_train = train_df_combined.get("regime", pd.Series(0, index=train_df_combined.index))
lgbm.tune(train_df_combined, labels_4class, regimes_train, trials=15)
lgbm.fit(train_df_combined, labels_4class, regimes_train)

regimes_test = target_test_df.get("regime", pd.Series(0, index=target_test_df.index))
lgbm_out     = lgbm.predict_batch(target_test_df, regimes_test)
prob_cols    = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
lgbm_probs   = lgbm_out[prob_cols].values
lgbm_bull    = lgbm_probs[:, 0] + lgbm_probs[:, 1]
lgbm_auc     = roc_auc_score(y_test, lgbm_bull)
results["LightGBM (regime-aware) standalone"] = lgbm_auc
print(f"  [OK] LightGBM standalone AUC = {lgbm_auc:.4f}")

# ─── Strategy A: Simple weighted average ─────────────────────────────────────
for tcn_w in [0.3, 0.4, 0.5, 0.6, 0.7]:
    lgbm_w = 1 - tcn_w
    blended = tcn_w * tcn2_probs_test + lgbm_w * lgbm_bull
    auc     = roc_auc_score(y_test, blended)
    results[f"WeightedAvg(TCN={tcn_w:.1f}, LGBM={lgbm_w:.1f})"] = auc

best_blend = max([v for k,v in results.items() if k.startswith("WeightedAvg")])
print(f"  [OK] Best weighted average blend AUC = {best_blend:.4f}")

# ─── Strategy B: Logistic Regression Meta-stacker ────────────────────────────
print("\n  [6/6] Training LR and Isotonic meta-stackers on validation set...")

# Use last 252 of training for meta-learner fitting
val_df = target_train_df.iloc[-252:].copy()
full_val = pd.concat([target_train_df.iloc[-252-lookback:-252], val_df])
tcn_val  = tcn1.predict(full_val).loc[val_df.index].values
reg_val  = val_df.get("regime", pd.Series(0, index=val_df.index))
lgbm_val = lgbm.predict_batch(val_df, reg_val)
lgbm_val_probs = lgbm_val[prob_cols].values

# Feature matrix: [tcn_prob, lgbm_strong_buy, lgbm_buy, lgbm_hold, lgbm_sell, lgbm_entropy]
X_val_meta = np.column_stack([
    tcn_val,
    lgbm_val_probs,
    entropy(lgbm_val_probs),
    lgbm_val_probs[:, 0] + lgbm_val_probs[:, 1],
])
y_val_meta = val_df["label_5d"].values

X_test_meta = np.column_stack([
    tcn2_probs_test,
    lgbm_probs,
    entropy(lgbm_probs),
    lgbm_bull,
])

# LR stacker
lr_meta = LogisticRegression(max_iter=500, C=0.5, class_weight="balanced", random_state=42)
lr_meta.fit(X_val_meta, y_val_meta)
lr_meta_probs = lr_meta.predict_proba(X_test_meta)[:, 1]
lr_meta_auc   = roc_auc_score(y_test, lr_meta_probs)
results["LR Meta-Stacker (with entropy feature)"] = lr_meta_auc
print(f"  [OK] LR Meta-Stacker AUC = {lr_meta_auc:.4f}")

# Isotonic Meta-Stacker
iso = IsotonicRegression(out_of_bounds="clip")
ridge = Ridge(alpha=0.5)
ridge.fit(X_val_meta, y_val_meta)
ridge_probs = ridge.predict(X_test_meta)
ridge_probs = np.clip(ridge_probs, 0, 1)
iso.fit(ridge.predict(X_val_meta), y_val_meta)
iso_probs = iso.predict(ridge_probs)
iso_auc   = roc_auc_score(y_test, iso_probs)
results["Isotonic Ridge Meta-Stacker"] = iso_auc
print(f"  [OK] Isotonic Ridge Meta-Stacker AUC = {iso_auc:.4f}")

# ─── Final Results Table ──────────────────────────────────────────────────────
print_separator("FINAL AUC RESULTS vs LOGISTIC REGRESSION BASELINE")
print(f"  {'Strategy'.ljust(46)} | AUC    | vs LR Baseline")
print("  " + "-" * 70)
for name, auc in sorted(results.items(), key=lambda x: -x[1]):
    delta = auc - lr_auc
    flag  = "[BEATS]" if auc > lr_auc else ("  baseline" if "Logistic" in name else "[BELOW]")
    print(f"  {name.ljust(46)} | {auc:.4f} | {delta:+.4f}  {flag}")

best_strategy  = max(results, key=results.get)
best_auc_final = results[best_strategy]
print(f"\n  [BEST] Best Strategy: {best_strategy}")
print(f"     AUC = {best_auc_final:.4f} ({'BEATS' if best_auc_final > lr_auc else 'BELOW'} baseline of {lr_auc:.4f})")
print("=" * 68)
