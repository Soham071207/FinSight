"""
run_backtest_final.py -- Phase 5: Connect evaluation results to BacktestEngine.

Reads: per_ticker_predictions.json (saved by run_offline_evaluation.py)
Reads: NSEI.parquet for Buy-and-Hold benchmark
Output: backtest_results.json
"""
import warnings, os, json
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import scipy.stats as st
from backtest_engine import BacktestEngine

SIGNAL_THRESHOLD_BUY  = 60.0  # score > 60 -> Buy
SIGNAL_THRESHOLD_SELL = 40.0  # score < 40 -> Sell

def score_to_signal(score):
    if score > SIGNAL_THRESHOLD_BUY:
        return "Strong Buy" if score > 75 else "Buy"
    if score < SIGNAL_THRESHOLD_SELL:
        return "Sell"
    return "Hold"

def run_benchmark():
    bench_path = os.path.join("data", "NSEI.parquet")
    if not os.path.exists(bench_path): return None
    df = pd.read_parquet(bench_path)
    df.index = pd.to_datetime(df.index)
    engine = BacktestEngine()
    equity = df["Close"].values / df["Close"].values[0] * engine.initial_capital
    return engine._compute_metrics(equity)

def main():
    arrays_path = "per_ticker_predictions.json"
    if not os.path.exists(arrays_path):
        print(f"[INFO] {arrays_path} not found. Ensure run_offline_evaluation.py saves it.")
        return

    with open(arrays_path) as f:
        arr = json.load(f)

    engine = BacktestEngine()
    results = {}
    all_sharpe = []

    print("=" * 70)
    print("  Walk-forward Backtest Simulation")
    print("=" * 70)

    for ticker_data in arr.get("per_ticker", []):
        ticker = ticker_data.get("ticker", "unknown")
        # 0-100 MetaLearner score before thresholding
        scores = np.array(ticker_data.get("finsight_scores_raw", []))
        y      = np.array(ticker_data.get("y_true", []))
        dates  = ticker_data.get("dates", [])
        closes = np.array(ticker_data.get("closes", []))
        atrs   = np.array(ticker_data.get("atrs", []))

        if len(scores) == 0 or len(closes) == 0:
            continue

        signals = pd.Series([score_to_signal(s) for s in scores])
        confs   = pd.Series(scores)

        df_bt = pd.DataFrame({
            "Close": closes,
            "Open": closes,
            "atr_14": atrs if len(atrs) == len(closes) else [closes.mean() * 0.02] * len(closes)
        })
        if dates:
            df_bt.index = pd.to_datetime(dates)

        try:
            result = engine.run_single(df_bt, signals, confs)
            m = result["metrics"]
            all_sharpe.append(m["sharpe"])
            results[ticker] = m
            print(f"  {ticker:15s}  Sharpe={m['sharpe']:.3f}  Return={m['total_return']:+.1f}%  MaxDD={m['max_drawdown']:.1f}%")
        except Exception as e:
            print(f"  {ticker:15s}  Backtest error: {e}")

    results["aggregate"] = {
        "mean_sharpe": float(np.mean(all_sharpe)) if all_sharpe else None,
        "std_sharpe":  float(np.std(all_sharpe))  if all_sharpe else None,
        "n_tickers":   len(all_sharpe),
    }

    # B7: Deflated Sharpe Ratio
    if all_sharpe:
        try:
            mean_sr = np.mean(all_sharpe)
            T_days = 252 * 5  # 5 years
            N_trials = 50     # Assumption
            sr_daily = mean_sr / np.sqrt(252)
            emc = 0.5772156649
            max_z = (1 - emc) * st.norm.ppf(1 - 1.0/N_trials) + emc * st.norm.ppf(1 - 1.0/(N_trials * np.e))
            sr0_daily = max_z / np.sqrt(T_days)
            num = (sr_daily - sr0_daily) * np.sqrt(T_days - 1)
            den = np.sqrt(1 + (3.0 - 1)/4.0 * (sr_daily**2)) # skew=0, kurtosis=3 (normal)
            dsr_prob = float(st.norm.cdf(num / den))
            results["aggregate"]["dsr_prob"] = dsr_prob
            print(f"  Deflated Sharpe Probability (N={N_trials}): {dsr_prob:.4f}")
        except Exception as e:
            print(f"  Failed to compute DSR: {e}")

    bnh = run_benchmark()
    if bnh:
        results["buy_and_hold_NIFTY"] = bnh
        print(f"\nBuy-and-Hold NIFTY: Sharpe={bnh['sharpe']:.3f} Return={bnh['total_return']:+.1f}% MaxDD={bnh['max_drawdown']:.1f}%")

    with open("backtest_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print("\nSaved: backtest_results.json")
    if all_sharpe:
        print(f"Mean FinSight Sharpe: {np.mean(all_sharpe):.3f} ± {np.std(all_sharpe):.3f}")

if __name__ == "__main__":
    main()
