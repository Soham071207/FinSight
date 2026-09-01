"""
stock_api.py — REST API wrapper for the STOCK Prediction System.

Run this in the STOCK/ directory with:
    python stock_api.py

The Flutter app connects to this server to get AI-driven stock signals.

Endpoints:
  GET  /health          → { "status": "ok" }
  POST /predict         → run full pipeline for given tickers
"""

import warnings
warnings.filterwarnings("ignore")

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

from flask import Flask, request, jsonify
from flask_cors import CORS

# Local imports from same STOCK directory
sys.path.insert(0, os.path.dirname(__file__))
from config import CONFIG
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from sentiment_engine import SentimentEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from backtest_engine import BacktestEngine
from output_engine import OutputEngine

import numpy as np
import pandas as pd

app = Flask(__name__)
CORS(app)


def _run_ticker(ticker: str) -> dict:
    """Run the full prediction pipeline for a single ticker. Returns a result dict."""
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    gm = GARCHModel()
    be = BacktestEngine()
    oe = OutputEngine()

    # Step 1: Fetch data
    df, market, currency = dp.process(ticker)

    # Step 2: Features
    forex = pd.Series(dtype=float)
    if market in ("NSE", "BSE"):
        forex = dp.fetch_forex_rate("USD", "INR")
    df = fe.compute_all(df, forex, market in ("NSE", "BSE"))

    # Step 3: Sentiment
    sent = se.fetch_and_score(ticker, market)
    df = se.get_historical_features(df, sent)

    # Step 4: GARCH
    df = gm.fit_transform(df)

    # Step 5: Prepare
    from config import ALL_FEATURES
    available = [c for c in ALL_FEATURES if c in df.columns]
    df["label_binary"] = (df["Close"].pct_change().shift(-1) > 0).astype(int)
    df.dropna(subset=available + ["label_binary"], inplace=True)

    # Step 6: Train
    splits = be.get_splits(df)
    if not splits:
        raise RuntimeError("Insufficient data for walk-forward splits")

    train_idx, test_idx = splits[-1]
    df_train = df.iloc[train_idx]

    garch2 = GARCHModel()
    df = garch2.fit_walk_forward(df, len(train_idx))

    lstm = LSTMPredictor(available)
    lstm.fit(df.iloc[train_idx], df.iloc[train_idx]["label_binary"])
    lstm_probs = lstm.predict(df)
    df["lstm_prob"] = lstm_probs

    df_train = df.iloc[train_idx]
    lgbm_features = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
    lgbm_features = [c for c in lgbm_features if c in df.columns]

    lgbm = LGBMSignalClassifier(lgbm_features)
    labels = lgbm.create_labels(df_train)
    regimes = df_train["regime"] if "regime" in df_train.columns else pd.Series(0, index=df_train.index)
    lgbm.fit(df_train, labels, regimes)

    val_start = max(0, len(df_train) - CONFIG["test_size_days"])
    df_val = df_train.iloc[val_start:]
    lstm_val = lstm.predict(df_val).values
    val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
    lgbm_preds_val = lgbm.predict_batch(df_val, val_regimes)
    prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    lgbm_prob_vals = lgbm_preds_val[prob_cols].values
    next_rets = df_val["Close"].pct_change().shift(-1).values
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_prob_vals, next_rets)

    # Step 7: Backtest + Signal
    regimes_all = df["regime"] if "regime" in df.columns else pd.Series(0, index=df.index)
    lgbm_preds = lgbm.predict_batch(df, regimes_all)
    lstm_all = lstm.predict(df).values
    lgbm_prob_all = lgbm_preds[prob_cols].values
    confidences = meta.predict_batch(lstm_all, lgbm_prob_all)
    conf_series = pd.Series(confidences, index=df.index, name="confidence")

    bt_result = be.walk_forward(df, lgbm_preds["signal"], conf_series)

    latest = df.iloc[[-1]]
    regime_val = int(latest["regime"].iloc[0]) if "regime" in latest.columns else 0
    atr = float(latest["atr_14"].iloc[0]) if "atr_14" in latest.columns else 0.02
    close = float(latest["Close"].iloc[0])

    lgbm_signal, lgbm_probs_latest = lgbm.predict(latest, regime_val)
    lstm_prob_latest = lstm.predict_single(df)
    confidence = meta.predict(lstm_prob_latest, lgbm_probs_latest)

    signal_info = oe.compute_final_signal(lgbm_signal, confidence, regime_val, atr, close)

    cm = bt_result["combined_metrics"]
    cur_map = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$"}

    chart_equity = oe.plot_equity_curve(bt_result["combined_equity"], bt_result["combined_dates"], ticker, cm, return_base64=True)
    chart_sharpe = oe.plot_rolling_sharpe(bt_result["combined_equity"], bt_result["combined_dates"], ticker, return_base64=True)
    chart_sentiment = oe.plot_sentiment_overlay(df, ticker, return_base64=True) if "daily_sentiment_score" in df.columns else ""
    importance = lgbm.get_feature_importance()
    chart_importance = oe.plot_feature_importance(importance, ticker, return_base64=True) if importance is not None else ""

    return {
        "ticker":         ticker,
        "market":         market,
        "currency":       currency,
        "currencySymbol": cur_map.get(currency, "$"),
        "signal":         signal_info["signal"],
        "confidence":     round(signal_info["confidence"], 1),
        "regimeLabel":    signal_info["regime_label"],
        "entryPrice":     round(signal_info["entry_price"], 2),
        "stopLoss":       round(signal_info["stop_loss"], 2),
        "targetPrice":    round(signal_info["target_price"], 2),
        "riskReward":     round(signal_info.get("risk_reward", 0), 2),
        "sentimentLabel": sent["sentiment_label"],
        "sentimentScore": round(sent["daily_sentiment_score"], 4),
        "topHeadline":    sent.get("top_headline", "N/A"),
        "topLink":        sent.get("top_link", ""),
        "backtestReturn": round(cm["total_return"], 2),
        "backtestSharpe": round(cm["sharpe"], 3),
        "maxDrawdown":    round(cm["max_drawdown"], 2),
        "winRate":        round(cm["win_rate"], 1),
        "chartEquity":    chart_equity,
        "chartSharpe":    chart_sharpe,
        "chartSentiment": chart_sentiment,
        "chartImportance": chart_importance,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Stock Prediction API", "version": "1.0.0"})


@app.route("/predict", methods=["POST"])
def predict():
    """
    Body: { "tickers": ["RELIANCE.NS", "AAPL", "HSBA.L"] }
    Returns: { "results": [ { ticker, signal, confidence, ... }, ... ], "errors": {...} }
    """
    body = request.json or {}
    tickers = body.get("tickers", [])
    if not tickers:
        return jsonify({"error": "tickers list is required"}), 400
    if len(tickers) > 5:
        return jsonify({"error": "Maximum 5 tickers per request"}), 400

    results = []
    errors = {}

    for raw_ticker in tickers:
        ticker = raw_ticker.strip().upper()
        try:
            logger.info(f"Processing ticker: {ticker}")
            result = _run_ticker(ticker)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed {ticker}: {e}")
            errors[ticker] = str(e)

    if not results and errors:
        return jsonify({"error": "All tickers failed", "details": errors}), 422

    return jsonify({"results": results, "errors": errors})


if __name__ == "__main__":
    print("=" * 60)
    print("  FinSight Stock Prediction API")
    print("  Running on http://0.0.0.0:5051")
    print("  Supports: NSE (.NS), BSE (.BO), US, UK (.L), EU")
    print("  Keep this window open while using the app!")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5051, debug=False)
