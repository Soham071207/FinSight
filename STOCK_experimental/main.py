"""
main.py — Orchestrator for the Stock Prediction System.

Ties together all modules:
  1. DataPipeline  → fetch & clean data
  2. FeatureEngine → compute technical indicators
  3. SentimentEngine → score news sentiment
  4. GARCHModel    → extract conditional volatility
  5. TCNPredictor  → next-day return probability
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
# Configure root logger once at module load to prevent duplicate handlers
if not logging.getLogger().handlers:
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
from tcn_model import TCNPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner
from backtest_engine import BacktestEngine
from output_engine import OutputEngine
from graph_model import GCNRefinementModule, build_returns_df, get_nse_sector_map


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
        self.gcn_module       = None   # Built in _step_gcn_refine() if gcn_enabled

        # Per-ticker storage
        self.data         = {}   # ticker → cleaned DataFrame with all features
        self.markets      = {}   # ticker → market string
        self.currencies   = {}   # ticker → currency string
        self.sentiments   = {}   # ticker → sentiment dict
        self.models       = {}   # ticker → dict of trained models
        self.results      = {}   # ticker → final output dict
        self.raw_signals  = {}   # ticker → pre-GCN signal_info (for comparison)

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

            # Create binary label for TCN: 1 if next-day close > today's close
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
        """Train TCN, LightGBM, and MetaLearner for each ticker."""
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

            # ── 6b. TCN ─────────────────────────────────────────────
            print(f"  Tuning & Training TCN …")
            tcn = TCNPredictor(feature_cols)
            tcn.tune(df.iloc[train_idx], df.iloc[train_idx]["label_binary"], trials=10)
            tcn.fit(df.iloc[train_idx], df.iloc[train_idx]["label_binary"])

            # Get TCN predictions for full dataset (train uses in-sample, test uses OOS)
            tcn_probs = tcn.predict(df)
            df["tcn_prob"] = tcn_probs
            self.data[ticker] = df

            # ── Re-derive train slice with new columns ────────────────
            df_train = df.iloc[train_idx]

            # ── 6c. LightGBM (regime-specific) ───────────────────────
            print(f"  Tuning & Training LightGBM (regime-aware) …")

            # Add tcn_prob to features for LightGBM (garch_vol already in feature_cols)
            lgbm_features = list(dict.fromkeys(feature_cols + ["tcn_prob", "garch_vol"]))
            lgbm_features = [c for c in lgbm_features if c in df.columns]

            lgbm = LGBMSignalClassifier(lgbm_features)
            labels = lgbm.create_labels(df_train)
            regimes = df_train["regime"] if "regime" in df_train.columns else pd.Series(0, index=df_train.index)
            
            lgbm.tune(df_train, labels, regimes, trials=10)
            lgbm.fit(df_train, labels, regimes)

            # ── 6d. Meta-Learner ──────────────────────────────────────
            print(f"  Training Meta-Learner …")

            # Get predictions on validation portion of training data
            val_start = max(0, len(df_train) - CONFIG["test_size_days"])
            df_val = df_train.iloc[val_start:]

            tcn_val   = tcn.predict(df_val).values
            val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
            lgbm_preds = lgbm.predict_batch(df_val, val_regimes)

            # Extract LightGBM probabilities
            prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
            lgbm_prob_vals = lgbm_preds[prob_cols].values

            # Actual next-day returns for meta-learner target
            next_rets = df_val["Close"].pct_change().shift(-1).values

            meta = MetaLearner()
            meta.fit(tcn_val, lgbm_prob_vals, next_rets)

            # Store models
            self.models[ticker] = {
                "tcn": tcn,
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

            tcn   = m["tcn"]
            lgbm  = m["lgbm"]
            meta  = m["meta"]
            lgbm_feats = m["lgbm_features"]

            # ── Generate signals for full test period ─────────────────
            regimes = df["regime"] if "regime" in df.columns else pd.Series(0, index=df.index)
            lgbm_preds = lgbm.predict_batch(df, regimes)

            # Compute confidence scores
            tcn_all = tcn.predict(df).values
            prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
            lgbm_prob_all = lgbm_preds[prob_cols].values

            confidences = meta.predict_batch(tcn_all, lgbm_prob_all)
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
            tcn_prob, tcn_uncertainty = tcn.predict_with_uncertainty(df, n_iter=50)
            confidence = meta.predict(tcn_prob, lgbm_probs)

            signal_info = self.output_engine.compute_final_signal(
                lgbm_signal, confidence, regime, atr, close
            )
            
            # Inject epistemic uncertainty
            signal_info["uncertainty"] = tcn_uncertainty
            if tcn_uncertainty > 0.15:
                signal_info["signal"] = "HIGH RISK " + signal_info["signal"]

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

            # ── SHAP Explainability ───────────────────────────────────
            out_path = f"{self.output_engine.output_dir}/{ticker}_shap_summary.png"
            lgbm.explain(df, regimes, out_path)

            # Store pre-GCN signal for ablation comparison
            self.raw_signals[ticker] = signal_info.copy()

            # Store results
            self.results[ticker] = {
                "signal": signal_info,
                "sentiment": self.sentiments[ticker],
                "backtest": bt_result,
                "importance": importance,
            }

    # ══════════════════════════════════════════════════════
    #  STEP 8: GCN CROSS-STOCK REFINEMENT (NEW)
    # ══════════════════════════════════════════════════════

    def _step_gcn_refine(self):
        """
        Apply GCN-Augmented Ensemble refinement across all queried stocks.

        This step runs ONLY when 2+ tickers are being analysed simultaneously
        (single ticker analysis cannot benefit from cross-stock message passing).

        The GCN:
          1. Builds a correlation graph from 252-day rolling Pearson correlations.
          2. Runs a 2-layer GCN forward pass to propagate confidence signals
             between correlated stocks.
          3. Applies a ±MAX_ADJUSTMENT refinement to each stock's MetaLearner score.

        If GCN is disabled in config (gcn_enabled=False) or < 2 tickers, this step
        prints a skip message and returns.
        """
        if not CONFIG.get("gcn_enabled", True):
            print("\n  ⏸  STEP 8: GCN Refinement SKIPPED (gcn_enabled=False in config)")
            return

        if len(self.tickers) < 2:
            print("\n  ⏸  STEP 8: GCN Refinement SKIPPED (need ≥2 tickers for graph)")
            return

        print("\n" + "═" * 55)
        print("  🕸️  STEP 8: GCN Cross-Stock Correlation Refinement")
        print("═" * 55)

        try:
            # ── 8a. Build returns DataFrame ─────────────────────
            returns_df = build_returns_df(self.data)
            if returns_df.empty:
                print("  ⚠ GCN: Could not build returns DataFrame. Skipping.")
                return

            # ── 8b. Build sector map ──────────────────────────
            sector_map = get_nse_sector_map()  # Covers NSE tickers; others get no sector prior

            # ── 8c. Build node feature matrices ─────────────────
            meta_scores     = {}
            tcn_probs       = {}
            lgbm_bull_probs = {}   # NEW: 4th node feature
            garch_vols      = {}

            for ticker in self.tickers:
                r = self.results.get(ticker)
                if r is None:
                    continue
                meta_scores[ticker] = r["signal"]["confidence"]
                df = self.data[ticker]
                m  = self.models.get(ticker)
                if m:
                    tcn_probs[ticker]  = m["tcn"].predict_single(df)
                    garch_vols[ticker] = float(df["garch_vol"].iloc[-1]) if "garch_vol" in df.columns else 0.0
                    # Extract LGBM bull probability from the last prediction
                    lgbm = m["lgbm"]
                    regime = int(df["regime"].iloc[-1]) if "regime" in df.columns else 0
                    _, lgbm_probs_last = lgbm.predict(df.iloc[[-1]], regime)
                    # lgbm_probs_last: (1, 4) → Strong Buy + Buy = bull
                    lgbm_bull_probs[ticker] = float(lgbm_probs_last[0, 0] + lgbm_probs_last[0, 1])
                else:
                    tcn_probs[ticker]       = 0.5
                    lgbm_bull_probs[ticker] = 0.5
                    garch_vols[ticker]      = 0.0

            # ── 8d. Initialise and fit GCN module ───────────────
            self.gcn_module = GCNRefinementModule(
                tickers=self.tickers,
                sector_map=sector_map,
                correlation_window=CONFIG.get("gcn_correlation_window", 252),
                edge_threshold=CONFIG.get("gcn_edge_threshold", 0.4),
                hidden_dim=CONFIG.get("gcn_hidden_dim", 32),
                out_dim=CONFIG.get("gcn_out_dim", 16),
                dropout=CONFIG.get("gcn_dropout", 0.2),
                lr=CONFIG.get("gcn_lr", 0.01),
            )
            self.gcn_module.MAX_ADJUSTMENT = CONFIG.get("gcn_max_adjustment", 10.0)

            # Labels: last observed next-day return per stock (normalized to [-1, 1])
            labels = np.array([
                float(self.data[t]["Close"].pct_change().dropna().iloc[-1])
                if t in self.data else 0.0
                for t in self.tickers
            ], dtype=np.float32)
            labels = np.clip(labels, -0.1, 0.1) / 0.1   # Normalize to [-1, 1]

            self.gcn_module.fit(
                returns_df=returns_df,
                meta_scores=meta_scores,
                tcn_probs=tcn_probs,
                lgbm_bull_probs=lgbm_bull_probs,
                garch_vols=garch_vols,
                labels=labels,
                epochs=CONFIG.get("gcn_epochs", 150),
            )

            # ── 8e. Refine scores ────────────────────────────
            refined_scores = self.gcn_module.refine_scores(
                meta_scores, tcn_probs, lgbm_bull_probs, garch_vols
            )

            # ── 8f. Update results with GCN-adjusted scores ──────
            print("\n  GCN Score Adjustments:")
            for ticker, new_score in refined_scores.items():
                old_score = meta_scores.get(ticker, 50.0)
                delta     = new_score - old_score
                icon      = "🟢" if delta >= 0 else "🔴"
                print(f"    {icon} {ticker}: {old_score:.1f} → {new_score:.1f} (GCN Δ={delta:+.2f})")

                # Update the stored result signal
                if ticker in self.results:
                    self.results[ticker]["signal"]["confidence_gcn_raw"]  = old_score
                    self.results[ticker]["signal"]["confidence"]           = new_score
                    self.results[ticker]["signal"]["gcn_delta"]            = delta

            # Print graph summary for the paper's experiments section
            gs = self.gcn_module.get_graph_summary()
            print(f"\n  Graph: {gs['num_nodes']} nodes | {gs['num_edges']} edges | "
                  f"Density={gs['graph_density']:.3f} | "
                  f"Mean|r|={gs['mean_abs_corr']:.3f}")

        except Exception as e:
            logger.exception(f"  [GCN] Refinement failed: {e}. Proceeding with original scores.")
            print(f"  ⚠ GCN refinement failed: {e}. Original scores retained.")


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
        self._step_gcn_refine()   # Step 8: GCN cross-stock refinement

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
                icon = "🟢" if "BUY" in s["signal"] else ("🔴" if "SELL" in s["signal"] else "🟡")
                print(f"\n  {ticker}:")
                print(f"    {icon} {s['signal']} | Confidence: {s['confidence']:.1f}% | "
                      f"Regime: {s['regime_label']}")
                print(f"    Uncertainty: {s.get('uncertainty', 0.0):.4f} "
                      f"({'⚠️ HIGH' if s.get('uncertainty', 0.0) > 0.15 else 'STABLE'})")
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
