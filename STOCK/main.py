"""
main.py — Orchestrator for the Stock Prediction System.

Ties together all modules:
  1. DataPipeline  → fetch & clean data
  2. FeatureEngine → compute technical indicators
  3. SentimentEngine → score news sentiment
  4. GARCHModel    → extract conditional volatility
  5. LSTMPredictor → next-day return probability
  6. LGBMSignalClassifier → 4-class signal per regime
  7. MetaLearner   → blend into final confidence
  8. BacktestEngine → walk-forward validation
  9. OutputEngine  → charts, signals, reports

Example:
  python main.py
  > Enter tickers: RELIANCE.NS, AAPL, HSBA.L
"""

import warnings
warnings.filterwarnings("ignore")

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import sys
import io

# Force UTF-8 on Windows to avoid cp1252 encoding errors with Unicode chars
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import logging
import numpy as np
import pandas as pd

# ── Setup logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Local imports ─────────────────────────────────────────────────────────────
from config import CONFIG, TECHNICAL_FEATURES, SENTIMENT_FEATURES, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from sentiment_engine import SentimentEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from backtest_engine import BacktestEngine
from output_engine import OutputEngine


class StockPredictionSystem:
    """
    End-to-end stock prediction system.
    Supports NSE (.NS), BSE (.BO), US, UK (.L), EU markets.
    """

    def __init__(self, tickers: list):
        self.tickers = [t.strip().upper() for t in tickers if t.strip()]
        if not self.tickers:
            raise ValueError("No valid tickers provided.")

        # Initialise all modules
        self.data_pipeline    = DataPipeline()
        self.feature_engine   = FeatureEngine()
        self.sentiment_engine = SentimentEngine()
        self.garch_model      = GARCHModel()
        self.backtest_engine  = BacktestEngine()
        self.output_engine    = OutputEngine()

        # Per-ticker storage
        self.data       = {}   # ticker → cleaned DataFrame with all features
        self.markets    = {}   # ticker → market string
        self.currencies = {}   # ticker → currency string
        self.sentiments = {}   # ticker → sentiment dict
        self.models     = {}   # ticker → dict of trained models
        self.results    = {}   # ticker → final output dict

    # ══════════════════════════════════════════════════════════════════════
    #  STEP 1: DATA PIPELINE
    # ══════════════════════════════════════════════════════════════════════

    def _step_fetch_data(self):
        """Fetch and clean OHLCV data for all tickers."""
        print("\n" + "═" * 55)
        print("  📥  STEP 1: Fetching Market Data")
        print("═" * 55)

        failed = []
        for ticker in self.tickers:
            try:
                df, market, currency = self.data_pipeline.process(ticker)
                self.data[ticker]       = df
                self.markets[ticker]    = market
                self.currencies[ticker] = currency
                print(f"  ✓ {ticker}: {len(df)} rows | {market} | {currency}")
            except Exception as e:
                print(f"  ✗ {ticker}: {e}")
                failed.append(ticker)

        # Remove failed tickers
        for t in failed:
            self.tickers.remove(t)

        if not self.tickers:
            raise RuntimeError("No tickers with sufficient data.")

    # ══════════════════════════════════════════════════════════════════════
    #  STEP 2: FEATURE ENGINEERING
    # ══════════════════════════════════════════════════════════════════════

    def _step_features(self):
        """Compute all technical features for each ticker."""
        print("\n" + "═" * 55)
        print("  🔧  STEP 2: Feature Engineering")
        print("═" * 55)

        for ticker in self.tickers:
            df     = self.data[ticker]
            market = self.markets[ticker]
            is_indian = market in ("NSE", "BSE")

            # Fetch forex rate for Indian stocks
            forex = pd.Series(dtype=float)
            if is_indian:
                forex = self.data_pipeline.fetch_forex_rate("USD", "INR")

            # Compute all technical features
            df = self.feature_engine.compute_all(df, forex, is_indian)
            self.data[ticker] = df
            print(f"  ✓ {ticker}: {len(self.feature_engine.feature_names)} features computed")

    # ══════════════════════════════════════════════════════════════════════
    #  STEP 3: SENTIMENT ANALYSIS
    # ══════════════════════════════════════════════════════════════════════

    def _step_sentiment(self):
        """Fetch and score news sentiment for each ticker."""
        print("\n" + "═" * 55)
        print("  📰  STEP 3: Sentiment Analysis")
        print("═" * 55)

        for ticker in self.tickers:
            market = self.markets[ticker]

            # Fetch current sentiment
            sent = self.sentiment_engine.fetch_and_score(ticker, market)
            self.sentiments[ticker] = sent

            # Add historical sentiment features to DataFrame
            df = self.data[ticker]
            df = self.sentiment_engine.get_historical_features(df, sent)
            self.data[ticker] = df

            label = sent["sentiment_label"]
            score = sent["daily_sentiment_score"]
            icon  = "😊" if label == "Bullish" else ("😟" if label == "Bearish" else "😐")
            print(f"  {icon} {ticker}: {label} ({score:+.4f}) | "
                  f"Headlines: {sent['top_headline']} | "
                  f"Link: {sent.get('top_link', 'N/A')}")

    # ══════════════════════════════════════════════════════════════════════
    #  STEP 4: GARCH VOLATILITY
    # ══════════════════════════════════════════════════════════════════════

    def _step_garch(self):
        """Fit GARCH(1,1) and add conditional volatility feature."""
        print("\n" + "═" * 55)
        print("  📈  STEP 4: GARCH Volatility Modelling")
        print("═" * 55)

        for ticker in self.tickers:
            df = self.data[ticker]
            df = self.garch_model.fit_transform(df)
            self.data[ticker] = df
            print(f"  ✓ {ticker}: {self.garch_model.get_summary()}")

    # ══════════════════════════════════════════════════════════════════════
    #  STEP 5: PREPARE DATA & DROP NaN
    # ══════════════════════════════════════════════════════════════════════

    def _step_prepare(self):
        """Drop NaN rows, create labels, prepare feature matrix."""
        print("\n" + "═" * 55)
        print("  🧹  STEP 5: Preparing Data Matrices")
        print("═" * 55)

        for ticker in self.tickers:
            df = self.data[ticker]

            # Determine available feature columns
            available = [c for c in ALL_FEATURES if c in df.columns]
            self.feature_cols = available

            # Create binary label for LSTM: 1 if next-day close > today's close
            # shift(-1) ensures no data leakage
            df["label_binary"] = (df["Close"].pct_change().shift(-1) > 0).astype(int)

            # Drop NaN rows from feature computation warm-up
            df.dropna(subset=available + ["label_binary"], inplace=True)

            self.data[ticker] = df
            print(f"  ✓ {ticker}: {len(df)} rows | {len(available)} features ready")

    # ══════════════════════════════════════════════════════════════════════
    #  STEP 6: TRAIN MODELS (Walk-Forward)
    # ══════════════════════════════════════════════════════════════════════

    def _step_train(self):
        """Train LSTM, LightGBM, and MetaLearner for each ticker."""
        print("\n" + "═" * 55)
        print("  🤖  STEP 6: Training Models (Walk-Forward)")
        print("═" * 55)

        for ticker in self.tickers:
            df = self.data[ticker]
            print(f"\n  ── {ticker} ──")

            # Get walk-forward splits
            splits = self.backtest_engine.get_splits(df)
            if not splits:
                print(f"  ⚠ Not enough data for walk-forward splits")
                continue

            # Use the FIRST split for model training (largest training set)
            train_idx, test_idx = splits[-1]  # last split has most training data

            df_train = df.iloc[train_idx]
            df_test  = df.iloc[test_idx]

            feature_cols = self.feature_cols

            # ── 6a. GARCH walk-forward ────────────────────────────────
            garch = GARCHModel()
            df = garch.fit_walk_forward(df, len(train_idx))
            self.data[ticker] = df

            # ── 6b. LSTM ─────────────────────────────────────────────
            print(f"  Training LSTM …")
            lstm = LSTMPredictor(feature_cols)
            lstm.fit(df.iloc[train_idx], df.iloc[train_idx]["label_binary"])

            # Get LSTM predictions for full dataset (train uses in-sample, test uses OOS)
            lstm_probs = lstm.predict(df)
            df["lstm_prob"] = lstm_probs
            self.data[ticker] = df

            # ── Re-derive train slice with new columns ────────────────
            df_train = df.iloc[train_idx]

            # ── 6c. LightGBM (regime-specific) ───────────────────────
            print(f"  Training LightGBM (regime-aware) …")

            # Add lstm_prob to features for LightGBM (garch_vol already in feature_cols)
            lgbm_features = list(dict.fromkeys(feature_cols + ["lstm_prob", "garch_vol"]))
            lgbm_features = [c for c in lgbm_features if c in df.columns]

            lgbm = LGBMSignalClassifier(lgbm_features)
            labels = lgbm.create_labels(df_train)
            regimes = df_train["regime"] if "regime" in df_train.columns else pd.Series(0, index=df_train.index)
            lgbm.fit(df_train, labels, regimes)

            # ── 6d. Meta-Learner ──────────────────────────────────────
            print(f"  Training Meta-Learner …")

            # Get predictions on validation portion of training data
            val_start = max(0, len(df_train) - CONFIG["test_size_days"])
            df_val = df_train.iloc[val_start:]

            lstm_val  = lstm.predict(df_val).values
            val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
            lgbm_preds = lgbm.predict_batch(df_val, val_regimes)

            # Extract LightGBM probabilities
            prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
            lgbm_prob_vals = lgbm_preds[prob_cols].values

            # Actual next-day returns for meta-learner target
            next_rets = df_val["Close"].pct_change().shift(-1).values

            meta = MetaLearner()
            meta.fit(lstm_val, lgbm_prob_vals, next_rets)

            # Store models
            self.models[ticker] = {
                "lstm": lstm,
                "lgbm": lgbm,
                "meta": meta,
                "garch": garch,
                "feature_cols": feature_cols,
                "lgbm_features": lgbm_features,
            }
            print(f"  ✓ {ticker}: All models trained")

    # ══════════════════════════════════════════════════════════════════════
    #  STEP 7: GENERATE SIGNALS + WALK-FORWARD BACKTEST
    # ══════════════════════════════════════════════════════════════════════

    def _step_backtest_and_signal(self):
        """Walk-forward backtest and generate final signals."""
        print("\n" + "═" * 55)
        print("  📊  STEP 7: Walk-Forward Backtest & Signal Generation")
        print("═" * 55)

        for ticker in self.tickers:
            df = self.data[ticker]
            m  = self.models.get(ticker)
            if m is None:
                continue

            lstm  = m["lstm"]
            lgbm  = m["lgbm"]
            meta  = m["meta"]
            lgbm_feats = m["lgbm_features"]

            # ── Generate signals for full test period ─────────────────
            regimes = df["regime"] if "regime" in df.columns else pd.Series(0, index=df.index)
            lgbm_preds = lgbm.predict_batch(df, regimes)

            # Compute confidence scores
            lstm_all = lstm.predict(df).values
            prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
            lgbm_prob_all = lgbm_preds[prob_cols].values

            confidences = meta.predict_batch(lstm_all, lgbm_prob_all)
            conf_series = pd.Series(confidences, index=df.index, name="confidence")

            # ── Walk-forward backtest ─────────────────────────────────
            print(f"\n  ── {ticker}: Walk-Forward Backtest ──")
            bt_result = self.backtest_engine.walk_forward(
                df, lgbm_preds["signal"], conf_series
            )

            cm = bt_result["combined_metrics"]
            print(f"\n  Combined: Return={cm['total_return']:+.2f}% | "
                  f"Sharpe={cm['sharpe']:.3f} | MaxDD={cm['max_drawdown']:.2f}% | "
                  f"WinRate={cm['win_rate']:.1f}%")

            # ── Final signal (latest data point) ──────────────────────
            latest = df.iloc[[-1]]
            regime = int(latest["regime"].iloc[0]) if "regime" in latest.columns else 0
            atr    = float(latest["atr_14"].iloc[0]) if "atr_14" in latest.columns else 0.02
            close  = float(latest["Close"].iloc[0])

            lgbm_signal, lgbm_probs = lgbm.predict(latest, regime)
            lstm_prob = lstm.predict_single(df)
            confidence = meta.predict(lstm_prob, lgbm_probs)

            signal_info = self.output_engine.compute_final_signal(
                lgbm_signal, confidence, regime, atr, close
            )

            # ── Generate charts ───────────────────────────────────────
            print(f"\n  🎨 Generating charts for {ticker} …")
            importance = lgbm.get_feature_importance()

            self.output_engine.generate_dashboard(
                ticker, df, signal_info, self.sentiments[ticker],
                bt_result, importance, currency=self.currencies.get(ticker, "USD")
            )

            # ── Print signal to console ───────────────────────────────
            self.output_engine.print_signal(
                ticker, signal_info, self.sentiments[ticker], currency=self.currencies.get(ticker, "USD")
            )

            # Store results
            self.results[ticker] = {
                "signal": signal_info,
                "sentiment": self.sentiments[ticker],
                "backtest": bt_result,
                "importance": importance,
            }

    # ══════════════════════════════════════════════════════════════════════
    #  RUN FULL PIPELINE
    # ══════════════════════════════════════════════════════════════════════

    def run(self):
        """Execute the complete prediction pipeline."""
        print("\n" + "═" * 55)
        print("  🚀  STOCK PREDICTION SYSTEM v1.0")
        print(f"  Tickers: {', '.join(self.tickers)}")
        print("═" * 55)

        self._step_fetch_data()
        self._step_features()
        self._step_sentiment()
        self._step_garch()
        self._step_prepare()
        self._step_train()
        self._step_backtest_and_signal()

        # ── Final Summary ─────────────────────────────────────────────
        print("\n" + "═" * 55)
        print("  🏁  FINAL RESULTS")
        print("═" * 55)

        for ticker in self.tickers:
            r = self.results.get(ticker)
            if r:
                s  = r["signal"]
                st = r["sentiment"]
                m  = r["backtest"]["combined_metrics"]

                cur = self.currencies.get(ticker, "USD")
                sym = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$"}.get(cur, "$")
                icon = "🟢" if s["signal"] == "BUY" else ("🔴" if s["signal"] == "SELL" else "🟡")
                print(f"\n  {ticker}:")
                print(f"    {icon} {s['signal']} | Confidence: {s['confidence']:.1f}% | "
                      f"Regime: {s['regime_label']}")
                print(f"    Entry: {sym}{s['entry_price']:.2f} | "
                      f"Stop: {sym}{s['stop_loss']:.2f} | "
                      f"Target: {sym}{s['target_price']:.2f}")
                print(f"    Backtest Sharpe: {m['sharpe']:.3f} | "
                      f"Return: {m['total_return']:+.2f}% | "
                      f"Max DD: {m['max_drawdown']:.2f}%")
                print(f"    Sentiment: {st['sentiment_label']} "
                      f"({st['daily_sentiment_score']:+.4f})")

        print(f"\n  📁 Charts and reports saved to: {self.output_engine.output_dir}/")
        print("═" * 55)
        print("  ✅ Execution Complete!")
        print("═" * 55 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "─" * 55)
    print("  STOCK PREDICTION SYSTEM")
    print("  Supports: NSE (.NS), BSE (.BO), US, UK (.L), EU")
    print("─" * 55)

    user_input = input(
        "\n  Enter stock tickers (comma-separated):\n"
        "    NSE : RELIANCE.NS, TCS.NS, INFY.NS\n"
        "    US  : AAPL, MSFT, GOOGL\n"
        "    UK  : HSBA.L, VOD.L\n"
        "  > "
    )

    tickers = [t.strip() for t in user_input.split(",") if t.strip()]

    if not tickers:
        print("  ❌ No tickers entered. Exiting.")
        sys.exit(1)

    system = StockPredictionSystem(tickers)
    system.run()
