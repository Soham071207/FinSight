import os
import pandas as pd
import numpy as np

# Apply seeds at the absolute highest level
from config import set_deterministic_seeds
set_deterministic_seeds(42)

from evaluate_accuracy import evaluate_models
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score

TICKERS = [
    "TCS.NS", "RELIANCE.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBI.NS",
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"
]

def run_full_pipeline(run_name="run1"):
    print(f"=== Starting Reproducible Run: {run_name} ===")
    all_y_true = []
    all_y_pred_proba = []

    for ticker in TICKERS:
        print(f"\nProcessing {ticker}...")
        try:
            y_true, ensemble_conf = evaluate_models(ticker)
            all_y_true.extend(y_true)
            all_y_pred_proba.extend(ensemble_conf)
        except Exception as e:
            print(f"Failed on {ticker}: {e}")

    # Create predictions DataFrame
    df_preds = pd.DataFrame({
        "y_true": all_y_true,
        "y_pred_proba": all_y_pred_proba
    })

    # Save to disk for bit-for-bit verification
    os.makedirs("output", exist_ok=True)
    out_file = f"output/predictions_{run_name}.csv"
    df_preds.to_csv(out_file, index=False)
    print(f"\nSaved {len(df_preds)} predictions to {out_file}")

    if len(df_preds) == 0:
        print("No predictions generated.")
        return

    # Evaluate global metrics
    y_true_arr = np.array(all_y_true)
    y_prob_arr = np.array(all_y_pred_proba)
    
    auc = roc_auc_score(y_true_arr, y_prob_arr)
    print(f"\nGlobal AUC (over {len(y_true_arr)} samples): {auc:.4f}")

    # Threshold sweep to find max F1 (simulating the paper's tuning method)
    thresholds = np.arange(20, 80, 2.5)
    f1s = [f1_score(y_true_arr, (y_prob_arr >= t).astype(int), zero_division=0) for t in thresholds]
    best_t = thresholds[np.argmax(f1s)]
    
    y_pred_bin = (y_prob_arr >= best_t).astype(int)
    
    acc = accuracy_score(y_true_arr, y_pred_bin)
    prec = precision_score(y_true_arr, y_pred_bin, zero_division=0)
    rec = recall_score(y_true_arr, y_pred_bin, zero_division=0)
    f1 = f1_score(y_true_arr, y_pred_bin, zero_division=0)
    
    tn, fp, fn, tp = confusion_matrix(y_true_arr, y_pred_bin).ravel()
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0

    print(f"Best Threshold (F1-maximized): {best_t:.1f}")
    print(f"Accuracy:    {acc*100:.1f}%")
    print(f"Precision:   {prec*100:.1f}%")
    print(f"Recall:      {rec*100:.1f}%")
    print(f"Specificity: {spec*100:.2f}%")
    print(f"F1 Score:    {f1*100:.1f}%")
    print(f"\nConfusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")

if __name__ == "__main__":
    import sys
    run_name = sys.argv[1] if len(sys.argv) > 1 else "run1"
    run_full_pipeline(run_name)
