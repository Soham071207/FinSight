"""
config.py — Central configuration for Stock Prediction System.
All parameters in one place. No magic numbers anywhere else.
"""

import os
from pathlib import Path
import random
import numpy as np

def set_deterministic_seeds(seed=42):
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    try:
        import tensorflow as tf
        tf.random.set_seed(seed)
    except ImportError:
        pass

# ─── Try to load .env file ───────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars

# ═══════════════════════════════════════════════════════════════════════════════
#  MASTER CONFIGURATION DICT
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    # ─── Data Pipeline ───────────────────────────────────────────────────
    "history_years": 5,
    "min_rows": 500,

    # ─── Market Detection (suffix → exchange name) ───────────────────────
    "market_suffixes": {
        ".NS": "NSE",
        ".BO": "BSE",
        ".L":  "LSE",
        ".PA": "EURONEXT",
        ".DE": "XETRA",
        ".TO": "TSX",
    },
    "default_market": "NYSE",

    # ─── Feature Engineering ─────────────────────────────────────────────
    "rsi_period":        14,
    "atr_period":        14,
    "ema_periods":       [9, 21, 50],
    "adx_period":        14,
    "bollinger_period":  20,
    "bollinger_std":     2,
    "macd_fast":         12,
    "macd_slow":         26,
    "macd_signal":       9,
    "stochastic_period": 14,
    "rolling_return_windows": [5, 10, 20],

    # ─── GARCH ───────────────────────────────────────────────────────────
    "garch_p": 1,
    "garch_q": 1,

    # ─── TCN Sequence Engine (Hyper-tuned) ───────────────────────────────
    "tcn_lookback":       60,
    "tcn_filters":        32,
    "tcn_dropout":        0.2,
    "tcn_epochs":         30,
    "tcn_batch_size":     32,
    "tcn_learning_rate":  0.001,
    "tcn_dense_units":    16,

    # ─── LightGBM Regime Stacker (Hyper-tuned) ───────────────────────────
    "lgbm_num_leaves":      31,
    "lgbm_max_depth":       6,
    "lgbm_learning_rate":   0.01,
    "lgbm_n_estimators":    600,
    "lgbm_subsample":       0.7,
    "lgbm_reg_lambda":      0.5,
    "lgbm_reg_alpha":       0.5,
    "lgbm_early_stopping":  50,
    "lgbm_classes":         ["Strong Buy", "Buy", "Hold", "Sell"],

    # ─── Meta-Learner (Stacker) ──────────────────────────────────────────
    "meta_optimal_threshold": 0.20,  # Found via F1-maximization logic

    # ─── Sentiment ───────────────────────────────────────────────────────
    "use_finbert":               os.getenv("USE_FINBERT", "true").lower() == "true",
    "vader_weight":              0.3,
    "finbert_weight":            0.7,
    "sentiment_rolling_windows": [3, 7],
    "max_headlines":             50,

    # ─── Walk-Forward Validation ─────────────────────────────────────────
    "n_splits":        3,
    "test_size_days":  252,          # ~1 trading year per fold

    # ─── Risk Management ─────────────────────────────────────────────────
    "initial_capital":     100_000,
    "atr_stop_multiplier": 2.0,
    "max_position_pct":    0.10,     # 10 % max per stock
    "transaction_cost":    0.001,    # 10 bps
    "debounce_days":       2,        # consecutive same signals required

    # ─── Regime Labels ───────────────────────────────────────────────────
    "regime_labels": {
        0: "Bull Trending",
        1: "Bull Ranging",
        2: "Bear Trending",
        3: "Bear Ranging",
    },

    # ─── API Keys (sourced from .env, never hardcoded) ───────────────────
    "news_api_key":          os.getenv("NEWS_API_KEY", ""),
    "reddit_client_id":      os.getenv("REDDIT_CLIENT_ID", ""),
    "reddit_client_secret":  os.getenv("REDDIT_CLIENT_SECRET", ""),
    "reddit_user_agent":     os.getenv("REDDIT_USER_AGENT", "StockPrediction/1.0"),

    # ─── Training Target Config ──────────────────────────────────────────────
    "train_tickers": [
        # IT / Tech
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "TECHM.NS", "WIPRO.NS",
        # Banking / Financials
        "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "BAJFINANCE.NS", "AXISBANK.NS", "KOTAKBANK.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS",
        # Energy / Auto
        "RELIANCE.NS", "M&M.NS", "ONGC.NS", "MARUTI.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "BPCL.NS",
        # Pharma / FMCG
        "SUNPHARMA.NS", "ITC.NS", "HINDUNILVR.NS", "NESTLEIND.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "BRITANNIA.NS", "TATACONSUM.NS",
        # Metals / Infra / Utilities / Conglomerates
        "TATASTEEL.NS", "LT.NS", "NTPC.NS", "POWERGRID.NS", "ULTRACEMCO.NS", "GRASIM.NS", "BHARTIARTL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "SHREECEM.NS", "UPL.NS",
        # Consumer
        "ASIANPAINT.NS", "TITAN.NS"
    ],

    # ─── Output ──────────────────────────────────────────────────────────
    "output_dir": "output",
    "chart_dpi":  150,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  FEATURE COLUMN REGISTRIES
# ═══════════════════════════════════════════════════════════════════════════════

TECHNICAL_FEATURES = [
    # Momentum
    "rsi_14", "macd", "macd_signal_line", "macd_diff",
    "stoch_k", "stoch_d",
    # Volatility
    "atr_14", "bb_high", "bb_low", "bb_width", "bb_pband",
    # Trend
    "ema_9", "ema_21", "ema_50", "adx",
    # Volume
    "obv", "vwap_ratio",
    # Derived
    "price_roc", "rolling_ret_5", "rolling_ret_10", "rolling_ret_20",
]

SENTIMENT_FEATURES = [
    "daily_sentiment_score",
    "sentiment_3d_rolling",
    "sentiment_7d_rolling",
    "sentiment_momentum",
    "news_volume",
]

MODEL_FEATURES = [
    "garch_vol",
]

ALL_FEATURES = TECHNICAL_FEATURES + SENTIMENT_FEATURES + MODEL_FEATURES
