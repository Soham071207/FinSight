# FinSight - IEEE Paper Reproducibility Package

This repository contains the full quantitative stock prediction pipeline as detailed in the paper: **"FinSight: An AI-Driven Personal Finance Management System"**.

## Installation

Ensure you have Python 3.9+ installed. Install all dependencies using:
```bash
pip install -r requirements.txt
```
*(Note: If you are running on Windows, TensorFlow requires WSL2 or the TensorFlow-DirectML plugin for GPU acceleration. CPU execution works natively.)*

## Reproducing the Paper Tables

To ensure transparency and reproducibility, we have provided automated scripts that generate the exact tables and metrics reported in the paper. All scripts use deterministic seeds (`np.random.seed(42)`).

### Table I & Confusion Matrix (Baseline vs Ensemble)
To replicate the core walk-forward out-of-sample evaluation on NSE large caps:
```bash
python evaluate_accuracy.py
```
*Expected Output:* Accuracy (55.6%), F1-Score (65.2%), and the detailed Confusion Matrix.

### Table II (Architecture Ablation Study)
To replicate the ablation study mathematically proving the necessity of GARCH, FinBERT, and Regime-Routing:
```bash
python evaluate_ablation.py
```

### Table III (Financial Backtest Performance)
To replicate the portfolio simulation (Cumulative Returns, Sharpe Ratio, Maximum Drawdown) vs the Buy-and-Hold benchmark:
```bash
python backtest_engine.py
```

### Table IV (Cross-Asset Generalizability)
To replicate the cross-sector evaluation across the curated basket of NIFTY 50 constituents:
```bash
python evaluate_cross_asset.py
```

### Multi-Horizon Evaluation
To replicate the sensitivity analysis that justifies the 5-day prediction window over 1-day, 3-day, and 10-day windows:
```bash
python evaluate_multi_horizon.py
```

## Running the API Server
If you wish to interact with the model via its REST API (as the Flutter mobile app does):
```bash
python main.py
```
This will launch the Flask server on `http://127.0.0.1:5000`.
