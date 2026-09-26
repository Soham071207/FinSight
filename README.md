# FinSight — Multi-Scale Deep Ensemble for Stock Market Prediction

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/Paper-SCI_Journal-red.svg)](FinSight_SCI_Journal_Paper.docx)

**FinSight** is a comprehensive multi-scale deep ensemble framework for stock market prediction, evaluated on the NIFTY-50 universe. It combines seven synergistic architectural innovations to address the fundamental small-data challenge in emerging market equity prediction.

---

## Architecture Overview

```
OHLCV + Technical Features (32-dim)
         │
   ┌─────▼──────┐    ┌──────────────┐
   │  TCN-MHA   │    │   ST-GCN     │
   │ (5 blocks, │    │ (Cross-Asset │
   │  4-head SA)│    │  Correlation)│
   └─────┬──────┘    └──────┬───────┘
         │                  │
         └──────┬───────────┘
                │
      ┌─────────▼──────────┐
      │  LightGBM Regime-  │
      │  Adaptive Classifier│
      └─────────┬──────────┘
                │
      ┌─────────▼──────────┐
      │  Bayesian Meta-    │
      │  Learner (MC=30)   │  ← Veto if uncertainty > threshold
      └─────────┬──────────┘
                │
         Final Signal: {Strong Buy / Buy / Hold / Sell}
```

## Key Results

| Metric | FinSight | LightGBM | XGBoost | GRU |
|--------|----------|----------|---------|-----|
| Accuracy | **51.10%** | — | 50.5% | 50.6% |
| AUC-ROC | 0.5140 | 0.5275 | 0.5079 | 0.5162 |
| F1 (Macro) | **0.5679** | — | 0.5513 | 0.5507 |
| Bear Trending AUC | **0.5750** | 0.5524 | — | — |

**Statistical significance:** Diebold-Mariano DM = 6.305, p = 2.98e-10 vs. LightGBM.

---

## Project Structure

```
├── generate_finsight_paper.py          ← Master paper generator (self-contained)
├── FinSight_SCI_Journal_Paper.docx     ← Final SCI Journal Paper
│
├── STOCK_experimental/                 ← Full ML Pipeline
│   ├── main.py                         ← Flask API server
│   ├── config.py                       ← All hyperparameters
│   ├── data_pipeline.py                ← OHLCV + feature engineering
│   ├── feature_engine.py               ← 32 technical features
│   ├── tcn_model.py                    ← TCN-MHA architecture
│   ├── lgbm_model.py                   ← Regime-adaptive LightGBM
│   ├── meta_learner.py                 ← Bayesian MC meta-learner
│   ├── graph_model.py                  ← ST-GCN cross-asset model
│   ├── sentiment_engine.py             ← VADER + FinBERT fusion
│   ├── garch_model.py                  ← GARCH(1,1) volatility
│   ├── ts_tcc.py                       ← TS-TCC self-supervised pre-training
│   ├── pretrain.py                     ← Pre-training entry point
│   ├── backtest_engine.py              ← Walk-forward backtest
│   │
│   ├── run_fast_ablation.py            ← Runs ablation study (5 tickers)
│   ├── run_regime_analysis.py          ← Runs regime robustness analysis
│   ├── run_backtest_final.py           ← Runs full NIFTY backtest
│   ├── run_significance_tests.py       ← McNemar / DM / Wilcoxon tests
│   │
│   ├── ablation_results.json           ← Ablation empirical results
│   ├── regime_results.json             ← Regime decomposition results
│   ├── backtest_results.json           ← Per-ticker backtest results
│   ├── significance_results.json       ← Statistical test results
│   └── true_metrics.json              ← Baseline comparison metrics
│
├── lib/                                ← Flutter frontend source
├── android/                            ← Android build
└── assets/                             ← Mobile app assets
```

---

## Quick Start: Reproduce Paper Results

> **Requirements:** Python 3.9+, Windows/Linux/macOS. GPU not required.

### 1. Install dependencies

```bash
cd STOCK_experimental
pip install -r requirements.txt
```

### 2. Download data (NSE NIFTY-50, 5 years)

```bash
python download_static_data.py
```

### 3. Run TS-TCC Self-Supervised Pre-Training

```bash
python pretrain.py
```
*Expected time: ~20 minutes on CPU. Saves `ts_tcc_encoder.weights.h5`.*

### 4. Run Full Pipeline Evaluation

```bash
python run_offline_evaluation.py
```
*Runs walk-forward evaluation on all 49 tickers. Expected time: ~45-90 minutes.*

### 5. Run Statistical Significance Tests

```bash
python run_significance_tests.py
```
*Saves `significance_results.json` with McNemar, Wilcoxon, and DM test results.*

### 6. Run Ablation Study (5-ticker fast version)

```bash
python run_fast_ablation.py
```
*Saves `ablation_results.json`. Expected time: ~10 minutes.*

### 7. Run Market Regime Analysis

```bash
python run_regime_analysis.py
```

### 8. Run Walk-Forward Backtest

```bash
python run_backtest_final.py
```

### 9. Regenerate Paper (Self-Contained)

```bash
cd ..  # back to project root
python generate_finsight_paper.py
```
*Opens `FinSight_SCI_Journal_Paper.docx` — automatically reads all JSON result files.*

---

## API Server

```bash
cd STOCK_experimental
python main.py
```

REST API runs at `http://127.0.0.1:5000`. Key endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict/<ticker>` | GET | 4-class prediction for a ticker |
| `/health` | GET | Server health check |
| `/regime/<ticker>` | GET | Current market regime |
| `/uncertainty/<ticker>` | GET | MC uncertainty estimate |

---

## Reproducibility

All stochastic operations use `np.random.seed(42)`. Results are deterministic given:
- Fixed seed (42)
- Identical feature standardization (fit on train split only)
- Identical walk-forward splits (70/10/20 chronological)
- Internet access for Yahoo Finance historical data download

**Environment:** Tested on Python 3.13.1, Windows 11. All dependencies pinned in `requirements.txt`.

---

## Citation

```bibtex
@article{bhagat2024finsight,
  title   = {FinSight: A Multi-Scale Deep Ensemble Framework for Stock Market Prediction
             with Self-Supervised Pre-Training, Graph Neural Networks, and
             Bayesian Uncertainty Quantification},
  author  = {Bhagat, Dhananjay and Shauryavardhan and Shelkar, Soham and
             Shevale, Harshraj and Shinde, Manas},
  journal = {Expert Systems with Applications / IEEE Transactions on Neural Networks},
  year    = {2024},
  institution = {Vishwakarma Institute of Technology, Pune, India}
}
```

---

## Team

| Name | Role |
|------|------|
| Dhananjay Bhagat | ML Architecture, TCN-MHA, Meta-Learner |
| Shauryavardhan | ST-GCN, Graph Model, Pre-Training |
| Soham Shelkar | LightGBM Pipeline, Feature Engineering |
| Harshraj Shevale | Sentiment Engine, FinBERT Integration |
| Manas Shinde | Backtest Engine, API, Flutter App |

**Institution:** Department of Engineering, Sciences and Humanities (DESH),  
Vishwakarma Institute of Technology, Pune, Maharashtra, India.
