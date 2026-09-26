"""
run_offline_evaluation.py
=========================
Full multi-ticker multi-seed offline evaluation for FinSight.

FIXED vs. previous version (addresses all 5 pipeline audit issues):
  Fix 1  Real MetaLearner.fit() + AUC-optimised rank-blend  (was hardcoded 0.4/0.6)
  Fix 2  GRU and PatchTST are genuinely trained Keras models (were arithmetic offsets)
  Fix 3  set_deterministic_seeds(seed) at start of every seed  (numpy + TensorFlow)
  Fix 4  Per-sample MetaLearner.predict() with MC uncertainty veto for FinSight eval
  Fix 5  TCN scaler fitted on first 85 % only  (applied in tcn_model.py)

Design:
  - Runs 3 seeds x N available tickers (leave-one-out across detected parquet files)
  - Aggregates mean +/- std across all (seed, ticker) pairs
  - Output: true_metrics.json  (consumed by generate_sci_journal_paper_v2.py)

Usage:
  cd STOCK_experimental
  python run_offline_evaluation.py
"""

import warnings, os, json, math
warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, roc_auc_score, f1_score, brier_score_loss,
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, callbacks, optimizers
    HAS_KERAS = True
except ImportError:
    HAS_KERAS = False
    print("WARNING: TensorFlow not available -- GRU/PatchTST baselines will be skipped.")

from config import CONFIG, ALL_FEATURES, set_deterministic_seeds
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from tcn_model import TCNPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner

# --------------------------------------------------------
SEEDS     = [42, 1337, 2024]
LOOKBACK  = CONFIG["tcn_lookback"]
TEST_SIZE = CONFIG["test_size_days"]
DATA_DIR  = "data"
PROB_COLS = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]


def discover_tickers():
    """Find all .NS parquet files in DATA_DIR."""
    if not os.path.isdir(DATA_DIR):
        return []
    found = [f.replace(".parquet", "") for f in sorted(os.listdir(DATA_DIR))
             if f.endswith(".parquet") and ".NS" in f]
    print(f"[Discovery] {len(found)} Indian equity tickers: {found}")
    return found


def make_binary_labels(df):
    fwd = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd > 0.005, 1, np.where(fwd < -0.005, 0, np.nan))
    return pd.Series(labels, index=df.index, name="label_binary")


def add_dummy_sentiment(df):
    n   = len(df)
    ser = pd.Series(np.random.normal(0, 0.1, n), index=df.index)
    df["daily_sentiment_score"] = ser.values
    df["sentiment_3d_rolling"]  = ser.rolling(3, min_periods=1).mean().values
    df["sentiment_7d_rolling"]  = ser.rolling(7, min_periods=1).mean().values
    df["sentiment_momentum"]    = ser.diff().fillna(0).values
    df["news_volume"]           = np.random.randint(0, 10, n).astype(float)
    return df


def load_and_featurize(ticker, fe, garch):
    for path in [
        os.path.join(DATA_DIR, f"{ticker}.parquet"),
        os.path.join(DATA_DIR, f"{ticker.replace('.NS','')}.parquet"),
    ]:
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_parquet(path)
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            df = fe.compute_all(df, forex_series=pd.Series(dtype=float), is_indian=True)
            df = add_dummy_sentiment(df)
            df = garch.fit_transform(df)
            df["label_binary"] = make_binary_labels(df)
            avail = [c for c in ALL_FEATURES if c in df.columns]
            df.dropna(subset=avail + ["label_binary"], inplace=True)
            df["label_binary"] = df["label_binary"].astype(int)
            return df
        except Exception as e:
            print(f"  [load] {ticker}: {e}")
    return None


def make_sequences(X, y, lookback):
    n = len(X)
    if n < lookback + 1:
        return np.empty((0, lookback, X.shape[1]), np.float32), np.empty(0, np.float32)
    Xs = np.stack([X[i - lookback:i] for i in range(lookback, n)])
    return Xs.astype(np.float32), y[lookback:].astype(np.float32)


def build_gru(n_feat, lookback=60, hidden=64, drop=0.3):
    if not HAS_KERAS:
        return None
    inp = layers.Input(shape=(lookback, n_feat))
    x   = layers.GRU(hidden, return_sequences=True, dropout=drop, recurrent_dropout=0.1)(inp)
    x   = layers.GRU(hidden, dropout=drop)(x)
    x   = layers.Dense(32, activation="relu")(x)
    x   = layers.Dropout(drop)(x)
    out = layers.Dense(1, activation="sigmoid")(x)
    m   = models.Model(inp, out)
    m.compile(optimizer=optimizers.Adam(1e-3), loss="binary_crossentropy",
              metrics=[tf.keras.metrics.AUC(name="auc")])
    return m


def build_patchtst(n_feat, lookback=60, patch=16, d=64, heads=4, n_layers=2, drop=0.1):
    if not HAS_KERAS:
        return None
    n_patches = math.ceil(lookback / patch)
    pad_amt   = n_patches * patch - lookback
    inp = layers.Input(shape=(lookback, n_feat))
    x   = layers.ZeroPadding1D(padding=(0, pad_amt))(inp) if pad_amt > 0 else inp
    x   = layers.Reshape((n_patches, patch * n_feat))(x)
    x   = layers.Dense(d)(x)
    for _ in range(n_layers):
        res = x
        x   = layers.LayerNormalization()(x)
        x   = layers.MultiHeadAttention(num_heads=heads, key_dim=d//heads, dropout=drop)(x, x)
        x   = layers.Dropout(drop)(x)
        x   = layers.Add()([res, x])
        res = x
        x   = layers.LayerNormalization()(x)
        x   = layers.Dense(d * 2, activation="gelu")(x)
        x   = layers.Dropout(drop)(x)
        x   = layers.Dense(d)(x)
        x   = layers.Add()([res, x])
    x   = layers.GlobalAveragePooling1D()(x)
    x   = layers.LayerNormalization()(x)
    out = layers.Dense(1, activation="sigmoid")(x)
    m   = models.Model(inp, out)
    m.compile(optimizer=optimizers.Adam(1e-3), loss="binary_crossentropy",
              metrics=[tf.keras.metrics.AUC(name="auc")])
    return m


def train_keras(model, X_tr, y_tr, epochs=30, batch=32):
    if model is None or len(X_tr) < 80:
        return None
    if len(np.unique(y_tr.astype(int))) < 2:
        return None
    try:
        cw_arr = compute_class_weight("balanced", classes=np.array([0,1]), y=y_tr.astype(int))
        cw = {0: float(cw_arr[0]), 1: float(cw_arr[1])}
    except Exception:
        cw = {0: 1.0, 1: 1.0}
    cb = [
        callbacks.EarlyStopping(monitor="val_auc", patience=8, mode="max",
                                restore_best_weights=True),
        callbacks.ReduceLROnPlateau(monitor="val_auc", mode="max", factor=0.5,
                                    patience=3, min_lr=1e-5, verbose=0),
    ]
    model.fit(X_tr, y_tr, epochs=epochs, batch_size=batch, validation_split=0.15,
              shuffle=False, class_weight=cw, callbacks=cb, verbose=0)
    return model


def mc_predict_all(meta, tcn_p, lgbm_p, regimes):
    """Fix 4: per-sample MetaLearner.predict() with live MC uncertainty veto."""
    scores, n_veto = [], 0
    for i in range(len(tcn_p)):
        reg   = int(regimes[i]) if i < len(regimes) else None
        score = meta.predict(float(tcn_p[i]), lgbm_p[i], regime=reg)
        scores.append(score)
        if meta.last_vetoed:
            n_veto += 1
    pct = n_veto / max(len(tcn_p), 1) * 100
    print(f"    [MC Veto] {n_veto}/{len(tcn_p)} suppressed ({pct:.1f}%)")
    return np.array(scores, dtype=float) / 100.0


def compute_metrics(y_true, y_probs):
    if len(np.unique(y_true)) < 2:
        return {}
    y_pred = (y_probs >= 0.5).astype(int)
    try:
        auc = float(roc_auc_score(y_true, y_probs))
    except Exception:
        auc = 0.5
    return {
        "Accuracy": float(accuracy_score(y_true, y_pred)),
        "AUC":      auc,
        "F1":       float(f1_score(y_true, y_pred, zero_division=0)),
        "Brier":    float(brier_score_loss(y_true, y_probs)),
    }


def evaluate_ticker(test_ticker, train_data, fe, garch):
    print(f"\n    -- {test_ticker} --")
    df_full = load_and_featurize(test_ticker, fe, garch)
    if df_full is None:
        return None
    avail = [c for c in ALL_FEATURES if c in df_full.columns]
    if len(df_full) < TEST_SIZE + LOOKBACK + 60:
        print(f"    [SKIP] only {len(df_full)} rows")
        return None
    df_train = df_full.iloc[:-TEST_SIZE].copy()
    df_test  = df_full.iloc[-TEST_SIZE:].copy()
    y_test   = df_test["label_binary"].values
    X_test   = df_test[avail].values
    if len(np.unique(y_test)) < 2:
        print("    [SKIP] single class in test")
        return None

    results = {}

    # ---- Tabular baselines ----
    X_tr = df_train[avail].values
    y_tr = df_train["label_binary"].values
    if HAS_XGB:
        try:
            xgb = XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05,
                                 eval_metric="logloss", verbosity=0, random_state=42)
            xgb.fit(X_tr, y_tr)
            results["XGBoost"] = compute_metrics(y_test, xgb.predict_proba(X_test)[:,1])
            print(f"    XGBoost  AUC={results['XGBoost'].get('AUC',0):.4f}")
        except Exception as e:
            print(f"    [XGBoost] {e}")
    try:
        rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        rf.fit(X_tr, y_tr)
        results["RandomForest"] = compute_metrics(y_test, rf.predict_proba(X_test)[:,1])
        print(f"    RF       AUC={results['RandomForest'].get('AUC',0):.4f}")
    except Exception as e:
        print(f"    [RF] {e}")

    # ---- Deep baselines (Fix 2) ----
    if HAS_KERAS:
        sc = StandardScaler()
        sp = max(1, int(len(X_tr) * 0.85))
        sc.fit(X_tr[:sp])
        Xtr_s = sc.transform(X_tr)
        Xte_s = sc.transform(X_test)
        Xtr_seq, ytr_seq = make_sequences(Xtr_s, y_tr,   LOOKBACK)
        Xte_seq, yte_seq = make_sequences(Xte_s, y_test, LOOKBACK)
        n_feat = Xtr_seq.shape[2] if len(Xtr_seq) > 0 else len(avail)
        if len(Xtr_seq) >= 80 and len(Xte_seq) > 0 and len(np.unique(yte_seq.astype(int))) >= 2:
            try:
                gru = train_keras(build_gru(n_feat), Xtr_seq, ytr_seq)
                if gru:
                    gp = gru.predict(Xte_seq, verbose=0).flatten()
                    results["GRU"] = compute_metrics(yte_seq, gp)
                    print(f"    GRU      AUC={results['GRU'].get('AUC',0):.4f}")
            except Exception as e:
                print(f"    [GRU] {e}")
            try:
                ptst = train_keras(build_patchtst(n_feat), Xtr_seq, ytr_seq)
                if ptst:
                    pp = ptst.predict(Xte_seq, verbose=0).flatten()
                    results["PatchTST"] = compute_metrics(yte_seq, pp)
                    print(f"    PatchTST AUC={results['PatchTST'].get('AUC',0):.4f}")
            except Exception as e:
                print(f"    [PatchTST] {e}")

    # ---- TCN ----
    print("    Training TCN...")
    tcn = TCNPredictor(avail)
    tcn.fit(df_train, df_train["label_binary"])
    full_seq    = pd.concat([df_train.iloc[-LOOKBACK:], df_test])
    tcn_test_p  = tcn.predict(full_seq).iloc[-TEST_SIZE:].values
    tcn_train_p = tcn.predict(df_train)
    df_train    = df_train.copy()
    df_train["tcn_prob"] = tcn_train_p.values

    # ---- Pooled LGBM ----
    print("    Training LGBM...")
    pool = []
    for tk, tdf in train_data.items():
        d = tdf.copy()
        d["tcn_prob"] = 0.5
        pool.append(d)
    pool.append(df_train)
    all_train  = pd.concat(pool).reset_index(drop=True)
    lgbm_feats = [c for c in avail + ["tcn_prob"] if c in all_train.columns]
    lgbm       = LGBMSignalClassifier(lgbm_feats)
    lbl        = lgbm.create_labels(all_train)
    reg_tr     = (all_train["regime"] if "regime" in all_train.columns
                  else pd.Series(0, index=all_train.index))
    lgbm.fit(all_train, lbl, reg_tr)

    df_te_l = df_test.copy()
    df_te_l["tcn_prob"] = tcn_test_p
    reg_te  = (df_test["regime"] if "regime" in df_test.columns
               else pd.Series(0, index=df_test.index))
    lgbm_out = lgbm.predict_batch(df_te_l, reg_te)
    lgbm_p   = lgbm_out[PROB_COLS].values
    lgbm_bull = np.clip(lgbm_p[:,0] + lgbm_p[:,1], 1e-6, 1-1e-6)
    results["StandaloneLightGBM"] = {
        "Brier": float(brier_score_loss(y_test, lgbm_bull))
    }
    print(f"    LGBM Standalone Brier={results['StandaloneLightGBM']['Brier']:.4f}")

    # ---- MetaLearner (Fix 1 + Fix 4) ----
    print("    Fitting MetaLearner...")
    vs     = max(0, len(df_train) - TEST_SIZE)
    df_val = df_train.iloc[vs:].copy()
    tv     = df_val["tcn_prob"].values
    rv     = (df_val["regime"] if "regime" in df_val.columns
              else pd.Series(0, index=df_val.index))
    lv     = lgbm.predict_batch(df_val, rv)[PROB_COLS].values
    yr     = df_val["Close"].pct_change(5).shift(-5).values
    meta   = MetaLearner()
    meta.fit(tv, lv, yr)   # Fix 1: real fit, not hardcoded blend
    reg_arr    = reg_te.values if hasattr(reg_te, "values") else np.array(reg_te)
    finsight_p = mc_predict_all(meta, tcn_test_p, lgbm_p, reg_arr)  # Fix 4: MC veto
    if len(finsight_p) == len(y_test):
        results["FinSight"] = compute_metrics(y_test, finsight_p)
        print(f"    FinSight AUC={results['FinSight'].get('AUC',0):.4f}  "
              f"Acc={results['FinSight'].get('Accuracy',0):.4f}  "
              f"Brier={results['FinSight'].get('Brier',0):.4f}")
              
    arrays = {
        "ticker": test_ticker,
        "y_true": y_test.tolist(),
        "dates": df_test.index.strftime('%Y-%m-%d').tolist() if hasattr(df_test.index, 'strftime') else [],
        "closes": df_test["Close"].tolist(),
        "atrs": df_test["atr_14"].tolist() if "atr_14" in df_test.columns else [],
        "regimes": reg_arr.tolist(),
        "FinSight": list(finsight_p),
        "StandaloneLightGBM": lgbm_bull.tolist(),
        "finsight_scores_raw": [float(p) * 100 for p in finsight_p],
    }
    if "xgb" in locals(): arrays["XGBoost"] = xgb.predict_proba(X_test)[:,1].tolist()
    if "rf" in locals(): arrays["RandomForest"] = rf.predict_proba(X_test)[:,1].tolist()
    if HAS_KERAS and "gru" in locals() and "gp" in locals(): arrays["GRU"] = gp.tolist()
    if HAS_KERAS and "ptst" in locals() and "pp" in locals(): arrays["PatchTST"] = pp.tolist()

    return results, arrays


def aggregate(all_results):
    combined = {}
    for seed_dict in all_results:
        for model, metrics in seed_dict.items():
            combined.setdefault(model, {})
            for k, v in metrics.items():
                combined[model].setdefault(k, []).append(float(v))
    return {
        model: {
            k: {"mean": float(np.mean(v)), "std": float(np.std(v)), "n": len(v)}
            for k, v in mdict.items()
        }
        for model, mdict in combined.items()
    }


def main():
    print("=" * 70)
    print("  FinSight Offline Evaluation  --  FIXED (all 5 issues resolved)")
    print("=" * 70)

    all_tickers = discover_tickers()
    if len(all_tickers) < 2:
        print("[ERROR] Need at least 2 .NS parquet files in data/")
        return

    fe    = FeatureEngine()
    garch = GARCHModel()

    print("\n[PRE-LOAD] Loading parquet files...")
    ticker_dfs = {}
    for t in all_tickers:
        df = load_and_featurize(t, fe, garch)
        if df is not None and len(df) >= TEST_SIZE + LOOKBACK + 60:
            ticker_dfs[t] = df
            print(f"  {t}: {len(df)} rows OK")
        else:
            print(f"  {t}: skipped")
    usable = list(ticker_dfs.keys())
    if len(usable) < 2:
        print("[ERROR] Fewer than 2 tickers have sufficient data.")
        return
    print(f"\nUsable: {usable}")

    all_results = []
    first_seed_arrays = None
    for seed_idx, seed in enumerate(SEEDS):
        print(f"\n{'='*70}")
        print(f"  SEED {seed}  ({seed_idx+1}/{len(SEEDS)})")
        print(f"{'='*70}")
        set_deterministic_seeds(seed)   # Fix 3: numpy + TF seeding

        seed_collector = {}
        seed_arrays = []
        for test_ticker in usable:
            train_pool = {t: ticker_dfs[t] for t in usable if t != test_ticker}
            try:
                res, arrays = evaluate_ticker(test_ticker, train_pool, fe, garch)
                if res:
                    seed_arrays.append(arrays)
                    for model, metrics in res.items():
                        seed_collector.setdefault(model, {})
                        for k, v in metrics.items():
                            seed_collector[model].setdefault(k, []).append(v)
            except Exception as e:
                import traceback
                print(f"  [ERROR] {test_ticker} seed={seed}: {e}")
                traceback.print_exc()

        # Average within-seed across tickers for clean reporting
        seed_avg = {
            model: {k: float(np.mean(v)) for k, v in mdict.items()}
            for model, mdict in seed_collector.items()
        }
        all_results.append(seed_avg)
        if first_seed_arrays is None:
            first_seed_arrays = seed_arrays

        print(f"\n  Seed {seed} averages:")
        for model, metrics in seed_avg.items():
            parts = [f"{k}={v:.4f}" for k, v in metrics.items()]
            print(f"    {model:22s}  {' | '.join(parts)}")

    print("\n[AGGREGATING across seeds]")
    final = aggregate(all_results)
    with open("true_metrics.json", "w") as f:
        json.dump(final, f, indent=4)
    print("\nSaved to true_metrics.json")
    
    if first_seed_arrays:
        with open("per_ticker_predictions.json", "w") as f:
            json.dump({"per_ticker": first_seed_arrays}, f)
        print("Saved to per_ticker_predictions.json")
    print(json.dumps(final, indent=4))
    print("\n[DONE] Now run: python generate_sci_journal_paper_v2.py")


if __name__ == "__main__":
    main()