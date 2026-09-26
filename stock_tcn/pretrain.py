"""
pretrain.py — TS-TCC Self-Supervised Pre-training for the TCN-MHA Encoder.

Replaces the previous supervised multi-ticker pre-training with a fully
unsupervised contrastive pre-training approach using the TS-TCC framework.

Key Advantages Over Supervised Pre-training:
  1. NO LABELS REQUIRED — Uses ALL available price history, not just rows
     with clean BUY/SELL labels. This means 3-5x more training data.
  2. UNIVERSAL REPRESENTATIONS — The encoder learns market structure
     (momentum patterns, volatility regimes, candlestick formations) that
     transfer across stocks, sectors, and even markets.
  3. BETTER GENERALISATION — Contrastive pre-training is regularised by
     design (representations must survive aggressive augmentation).

Usage:
    python pretrain.py
        → Downloads 25-ticker data
        → Runs 50-epoch TS-TCC pre-training
        → Saves encoder to ts_tcc_encoder.weights.h5

For fine-tuning downstream (in main.py / compare scripts):
    from ts_tcc import fine_tune_from_pretrained
    fine_tune_from_pretrained(tcn_predictor, "ts_tcc_encoder.weights.h5",
                              X_train_df, y_train)
"""

import warnings
warnings.filterwarnings("ignore")

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import numpy as np
import pandas as pd
import logging

from config import CONFIG
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from tcn_model import TCNPredictor
from ts_tcc import TSTCCPretrainer, build_pretrain_sequences

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

PRETRAIN_TICKERS = [
    # NIFTY 50 coverage across all major sectors
    "RELIANCE.NS",   "TCS.NS",        "HDFCBANK.NS",  "INFY.NS",       "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS",       "BHARTIARTL.NS","ITC.NS",        "KOTAKBANK.NS",
    "LT.NS",         "AXISBANK.NS",   "BAJFINANCE.NS","ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS",  "TITAN.NS",      "ULTRACEMCO.NS","WIPRO.NS",      "TATASTEEL.NS",
    "HCLTECH.NS",    "BAJAJFINSV.NS", "NTPC.NS",      "POWERGRID.NS",  "INDUSINDBK.NS",
    "NESTLEIND.NS",  "M&M.NS",        "GRASIM.NS",    "TECHM.NS",      "JSWSTEEL.NS",
    "CIPLA.NS",      "ADANIENT.NS",   "ADANIPORTS.NS","TATAMOTORS.NS", "HDFCLIFE.NS",
    "SBILIFE.NS",    "ONGC.NS",       "HINDALCO.NS",  "DRREDDY.NS",    "EICHERMOT.NS",
    "BAJAJ-AUTO.NS", "DIVISLAB.NS",   "BRITANNIA.NS", "APOLLOHOSP.NS", "COALINDIA.NS",
    "TATACONSUM.NS", "HEROMOTOCO.NS", "UPL.NS",       "BPCL.NS",       "LTIM.NS"
]

PRETRAIN_WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ts_tcc_encoder.weights.h5"
)

# TS-TCC hyperparameters (tuned for financial data)
PRETRAIN_CONFIG = {
    "epochs":          50,
    "batch_size":      64,
    "base_lr":         3e-4,
    "temperature":     0.07,     # Lower than vision SSL (0.5) — financial embeddings are denser
    "lambda_temporal": 0.5,      # Equal weight for temporal and contextual losses
    "gru_units":       64,
    "proj_hidden_dim": 256,
    "proj_output_dim": 128,
}


# ── Data Collection ───────────────────────────────────────────────────────────

def collect_pretrain_data():
    """
    Download and engineer features for all pre-training tickers.
    Returns: (all_X_dfs, feature_cols, scaler_fitted_on_all)
    NOTE: No labels are collected — this is unsupervised.
    """
    dp = DataPipeline()
    fe = FeatureEngine()

    all_X_dfs    = []
    feature_cols = None

    print(f"\n  [PRETRAIN] Collecting data for {len(PRETRAIN_TICKERS)} tickers...")

    for ticker in PRETRAIN_TICKERS:
        try:
            raw = dp.fetch_data(ticker)
            if raw is None or len(raw) < 100:
                logger.warning(f"  Skipping {ticker}: insufficient data.")
                continue

            df = fe.compute_all(raw)
            df = df.dropna()

            if len(df) < 80:
                logger.warning(f"  Skipping {ticker}: too few rows after feature engineering.")
                continue

            # Determine feature columns from first valid ticker
            if feature_cols is None:
                exclude = {"Date", "Target", "regime", "garch_vol", "daily_sentiment_score"}
                feature_cols = [c for c in df.columns if c not in exclude]

            # Keep only common features
            available = [c for c in feature_cols if c in df.columns]
            all_X_dfs.append(df[available])
            print(f"    {ticker}: {len(df)} rows")

        except Exception as e:
            logger.warning(f"  Skipping {ticker}: {e}")

    if not all_X_dfs:
        raise RuntimeError("No data collected for pre-training.")

    # Re-align to common features
    common_cols = list(set.intersection(*[set(df.columns) for df in all_X_dfs]))
    all_X_dfs   = [df[common_cols] for df in all_X_dfs]
    feature_cols = common_cols

    total_rows = sum(len(df) for df in all_X_dfs)
    print(f"\n  [PRETRAIN] {len(all_X_dfs)} tickers | {total_rows:,} total rows "
          f"| {len(feature_cols)} features")

    return all_X_dfs, feature_cols


# ── Main ──────────────────────────────────────────────────────────────────────

def run_pretraining():
    print("=" * 65)
    print("  TS-TCC Self-Supervised Pre-training for TCN-MHA Encoder")
    print("=" * 65)

    # 1. Collect data
    all_X_dfs, feature_cols = collect_pretrain_data()

    # 2. Build a TCNPredictor to get a fresh encoder + scaler
    tcn = TCNPredictor(feature_cols)

    # 3. Fit scaler on ALL data (combined across all tickers)
    combined_X = pd.concat(all_X_dfs, ignore_index=True)
    tcn.scaler.fit(combined_X[feature_cols].values)
    print(f"  [PRETRAIN] Scaler fitted on {len(combined_X):,} rows.")

    # 4. Build the TCN-MHA model (required before get_encoder_model())
    n_features = len(feature_cols)
    tcn.model  = tcn._build_model(n_features)
    print(f"  [PRETRAIN] TCN-MHA model built ({tcn.model.count_params():,} params).")

    # 5. Build the pre-training sequence dataset (no labels, no look-ahead)
    X_all = build_pretrain_sequences(
        all_X_dfs=all_X_dfs,
        feature_cols=feature_cols,
        scaler=tcn.scaler,
        lookback=tcn.lookback,
    )
    print(f"  [PRETRAIN] Sequence dataset: {X_all.shape} (N, lookback, features)")

    if len(X_all) < PRETRAIN_CONFIG["batch_size"]:
        raise RuntimeError(f"Too few sequences ({len(X_all)}) for pre-training. "
                           f"Need at least {PRETRAIN_CONFIG['batch_size']}.")

    # 6. Initialise and run the TS-TCC pretrainer
    pretrainer = TSTCCPretrainer(
        tcn_predictor    = tcn,
        n_features       = n_features,
        temperature      = PRETRAIN_CONFIG["temperature"],
        lambda_temporal  = PRETRAIN_CONFIG["lambda_temporal"],
        gru_units        = PRETRAIN_CONFIG["gru_units"],
        proj_hidden_dim  = PRETRAIN_CONFIG["proj_hidden_dim"],
        proj_output_dim  = PRETRAIN_CONFIG["proj_output_dim"],
    )

    pretrainer.pretrain(
        X_all      = X_all,
        epochs     = PRETRAIN_CONFIG["epochs"],
        batch_size = PRETRAIN_CONFIG["batch_size"],
        base_lr    = PRETRAIN_CONFIG["base_lr"],
    )

    # 7. Save the encoder weights
    pretrainer.save_encoder(PRETRAIN_WEIGHTS_PATH)

    print(f"\n  [PRETRAIN] Done. Use 'load_pretrained_encoder()' in TCNPredictor")
    print(f"  [PRETRAIN] or 'fine_tune_from_pretrained()' from ts_tcc.py")
    print(f"  [PRETRAIN] with weights at: {PRETRAIN_WEIGHTS_PATH}")
    print("=" * 65)


if __name__ == "__main__":
    run_pretraining()
