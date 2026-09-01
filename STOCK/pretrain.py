"""
pretrain.py — Multi-ticker pre-training for the Attention-LSTM.

Trains the LSTM on a large basket of NIFTY 50 stocks to learn universal 
market patterns and prevent overfitting, before fine-tuning on the target stock.
"""

import warnings
warnings.filterwarnings("ignore")

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
import logging
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping

from config import ALL_FEATURES, CONFIG
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Basket of 10 NIFTY 50 stocks covering different sectors
BASKET = [
    "RELIANCE.NS",   # Energy
    "TCS.NS",        # IT
    "HDFCBANK.NS",   # Banking
    "ITC.NS",        # FMCG
    "LT.NS",         # Engineering
    "INFY.NS",       # IT
    "ICICIBANK.NS",  # Banking
    "SBIN.NS",       # Banking
    "BHARTIARTL.NS", # Telecom
    "SUNPHARMA.NS"   # Pharma
]

def make_5day_labels(df):
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    return np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))

def build_pretrain_dataset():
    dp = DataPipeline()
    fe = FeatureEngine()
    garch = GARCHModel()
    
    all_X = []
    all_y = []
    common_features = []
    
    # Pre-fetch macro data
    logger.info("Fetching macro indices...")
    forex = dp.fetch_forex_rate("USD", "INR")
    nifty = dp.fetch_index_data("^NSEI")
    vix = dp.fetch_index_data("^INDIAVIX")

    for ticker in BASKET:
        try:
            logger.info(f"Processing {ticker}...")
            # 1. Fetch
            df, market, curr = dp.process(ticker)
            
            # 2. Features
            df = fe.compute_all(
                df, forex_series=forex, nifty_series=nifty, vix_series=vix, is_indian=True
            )
            df = garch.fit_transform(df)
            
            # 3. Labels
            df["label_5d"] = make_5day_labels(df)
            
            # Find available features for this ticker
            available = [c for c in ALL_FEATURES if c in df.columns]
            if not common_features:
                common_features = available
            else:
                # Keep intersection of features
                common_features = [c for c in common_features if c in available]
                
            df.dropna(subset=common_features + ["label_5d"], inplace=True)
            
            if len(df) > 100:
                all_X.append(df[common_features])
                all_y.append(df["label_5d"])
                
        except Exception as e:
            logger.warning(f"Skipped {ticker}: {e}")

    return all_X, all_y, common_features

def run_pretraining():
    logger.info("=== Starting Multi-Ticker Pre-training ===")
    all_X_dfs, all_y_series, feature_cols = build_pretrain_dataset()
    
    if not all_X_dfs:
        logger.error("No data collected.")
        return

    logger.info(f"Combined {len(all_X_dfs)} stocks.")
    logger.info(f"Feature columns ({len(feature_cols)}): {feature_cols}")

    # Concatenate all DataFrames into one massive dataset
    # Note: LSTMPredictor._create_sequences must not cross ticker boundaries.
    # So we'll use LSTMPredictor to scale and sequence EACH ticker, then combine.
    
    lstm = LSTMPredictor(feature_cols)
    
    # 1. Fit scaler on the ENTIRE combined dataset to normalize correctly
    combined_X = pd.concat(all_X_dfs, ignore_index=True)
    lstm.scaler.fit(combined_X.values)
    
    X_seqs = []
    y_seqs = []
    
    for X_df, y_series in zip(all_X_dfs, all_y_series):
        # Scale this ticker
        X_scaled = lstm.scaler.transform(X_df.values)
        y_vals = y_series.values.astype(float)
        
        # Sequence this ticker
        X_seq, y_seq = lstm._create_sequences(X_scaled, y_vals)
        if len(X_seq) > 0:
            X_seqs.append(X_seq)
            y_seqs.append(y_seq)
            
    # Combine sequences
    X_train = np.vstack(X_seqs)
    y_train = np.concatenate(y_seqs)
    
    # Shuffle the sequences (it's safe to shuffle sequences of shape (lookback, features) 
    # for training, as the temporal structure INSIDE the sequence is preserved)
    indices = np.arange(len(X_train))
    np.random.shuffle(indices)
    X_train = X_train[indices]
    y_train = y_train[indices]
    
    logger.info(f"Total training sequences: {X_train.shape}")
    
    # Build model
    n_features = X_train.shape[2]
    lstm.model = lstm._build_model(n_features)
    
    # Callbacks
    early_stop = EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)
    checkpoint = ModelCheckpoint("lstm_pretrained.weights.h5", monitor="val_loss", save_best_only=True, save_weights_only=True)
    
    # Train
    logger.info("Training Attention-LSTM...")
    lstm.model.fit(
        X_train, y_train,
        epochs=50,
        batch_size=64,  # larger batch size for massive dataset
        validation_split=0.15,
        shuffle=True,   # sequences are pre-built, safe to shuffle
        callbacks=[early_stop, checkpoint],
        verbose=1
    )
    
    logger.info("Pre-training complete! Weights saved to lstm_pretrained.weights.h5")

if __name__ == "__main__":
    run_pretraining()
