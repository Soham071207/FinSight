# Financial ML/DL Technical Roadmap

This document serves as the roadmap for technical improvements to the deep learning architecture. It also outlines the current end-to-end pipeline for academic review.

---

## Current System Architecture Overview

The current algorithmic trading system uses an advanced ensemble of Deep Learning, Graph Neural Networks, and Gradient Boosting to process financial time-series data:

1. **Data Pipeline & Feature Engineering (`data_pipeline.py`, `feature_engine.py`)**
   - Fetches historical OHLCV data.
   - Computes advanced technical indicators (RSI, MACD, Bollinger Bands, ATR).
   - Incorporates GARCH volatility modeling and daily sentiment scores.
2. **Deep Sequence Extractor (`tcn_model.py`)**
   - Uses a **Temporal Convolutional Network (TCN)** to extract localized patterns from time-series sequences.
   - Enhanced with **Sine-Cosine Positional Encoding** and **Multi-Head Self-Attention (MHA)** to weigh the most critical temporal signals instead of using flat average pooling.
   - **TS-TCC Self-Supervised Pre-training (`ts_tcc.py`)**: Uses contrastive learning (NT-Xent Loss) and temporal cross-prediction to learn robust market embeddings from unlabeled price histories.
3. **Cross-Asset Correlation Network (`graph_model.py`)**
   - Uses a **Spatial-Temporal Graph Convolutional Network (ST-GCN)** implemented as a Bilinear Graph Attention Network (GAT).
   - Dynamically builds a stock correlation graph, allowing the model to refine predictions based on simultaneous movements of related stocks in the market.
4. **Sentiment Analysis Layer (`sentiment.py`)**
   - Fetches real-time financial news and extracts actionable signals using VADER sentiment analysis (soon upgrading to confidence-gated FinBERT).
5. **Meta-Learner Decision Engine (`lgbm_model.py`, `meta_learner.py`)**
   - A **LightGBM Gradient Boosting Classifier** acts as the final decision layer.
   - It fuses the embeddings from the TCN, the structural attention weights from the GNN, and the raw tabular technical features to output the final BUY/SELL probability.

---

## Phase 1: Completed Core Architecture Upgrades
✅ **Rank 1 — Spatial-Temporal Graph Neural Network (ST-GCN) for Cross-Asset Correlation**
- **Status:** Implemented as a Bilinear Graph Attention Network (GAT).
- **Details:** The model builds a Stock Correlation Graph dynamically and uses node features to compute attention weights, refining meta-learner predictions using cross-asset interactions.

✅ **Rank 2 — Replace GlobalAveragePooling with Multi-Head Self-Attention (TCN-MHA)**
- **Status:** Implemented in `tcn_model.py`.
- **Details:** Replaced average pooling with a multi-head self-attention layer preceded by a Sine-Cosine Positional Encoding layer, allowing the model to focus on the most important temporal signals.

---

## Phase 2: Upcoming Modeling Refinements
✅ **Rank 3 — Bayesian Meta-Learner with Uncertainty Quantification**
- **Status:** Implemented in `meta_learner.py`.
- **Details:** MetaLearner now runs 30 Monte Carlo Dropout passes per prediction. Epistemic uncertainty (std of score distribution) is computed per trade. Trades with uncertainty > 0.12 are automatically vetoed and returned as a neutral HOLD (score=50.0).

✅ **Rank 4 — Regime-Adaptive Dynamic Loss Function for LightGBM**
- **Status:** Implemented in `lgbm_model.py`.
- **Details:** Replaced `class_weight='balanced'` with per-sample `sample_weight` arrays computed at training time. In Bear regimes, Sell-class samples receive a 3x penalty to prevent buying into crashes. In Bull regimes, Strong Buy-class samples receive a 2x penalty to prevent missing rallies.

---

## Phase 3: Future System Enhancements
✅ **Rank 5 — Hierarchical Sentiment Fusion (Confidence-Gated VADER + FinBERT)**
- **Status:** Implemented in `sentiment_engine.py`.
- **Details:** Replaced the fixed weighted average with a 3-tier confidence gate. FinBERT now returns its raw logit confidence alongside its score. High confidence (>=0.80) => FinBERT overrides VADER. Low confidence (<0.55) => fall back to VADER only. Mid confidence => proportional blend. All headlines are aggregated using a recency-weighted Exponential Moving Average (EMA alpha=0.85) so breaking news matters more than week-old articles.

✅ **Rank 6 — Walk-Forward Online Learning (Concept Drift Adaptation)**
- **Status:** Implemented in `lgbm_model.py` as `online_update()` and `online_update_from_buffer()`.
- **Details:** Uses LightGBM's `init_model` to continue training from the existing model checkpoint without retraining from scratch. Applies a rolling 120-day window to focus on recent market behavior, adds 50 new trees per update cycle, and preserves all regime-adaptive sample weights from the original training.

✅ **Rank 7 — Temporal Contrastive Pre-training (Self-Supervised Learning)**
- **Status:** Implemented in `ts_tcc.py` and integrated via `pretrain.py`.
- **Goal:** Improve embeddings for stocks with short trading histories.
- **Action:** Implement TS-TCC pre-training on unlabeled stock data to learn robust representations before fine-tuning on the BUY/SELL downstream task.
