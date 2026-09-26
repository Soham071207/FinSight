"""
run_regime_analysis.py -- Phase 7.2: Per-regime AUC breakdown for Table IX.

Reads: per_ticker_predictions.json
Output: regime_results.json
"""
import warnings, os, json
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from dm_test_clustered import clustered_dm_test

REGIME_MAP = {
    0: "Bull Trending",
    1: "Bull Ranging",
    2: "Bear Trending",
    3: "Bear Ranging"
}

def main():
    path = "per_ticker_predictions.json"
    if not os.path.exists(path):
        print(f"[INFO] {path} not found. Run run_offline_evaluation.py first.")
        return

    with open(path) as f:
        arr = json.load(f)
    pt = arr.get("per_ticker", [])

    regime_data = {name: {"finsight": [], "lgbm": []} for name in REGIME_MAP.values()}
    regime_data["All Regimes"] = {"finsight": [], "lgbm": []}

    bear_panel_rows = []

    for td in pt:
        y    = np.array(td["y_true"])
        p_fs = np.array(td["FinSight"])
        p_bl = np.array(td.get("StandaloneLightGBM", [0.5]*len(y)))
        regs = np.array(td.get("regimes", [0]*len(y)))
        dates = td.get("dates", [])

        if len(y) < 10 or len(np.unique(y)) < 2 or len(dates) != len(y):
            continue
            
        for i in range(len(y)):
            if regs[i] == 2:  # Bear Trending
                bear_panel_rows.append({
                    "date": dates[i],
                    "loss_fs": (y[i] - p_fs[i])**2,
                    "loss_bl": (y[i] - p_bl[i])**2
                })

        try:
            regime_data["All Regimes"]["finsight"].append(roc_auc_score(y, p_fs))
            regime_data["All Regimes"]["lgbm"].append(roc_auc_score(y, p_bl))
        except:
            pass

        for rid, rname in REGIME_MAP.items():
            mask = (regs == rid)
            if mask.sum() < 10 or len(np.unique(y[mask])) < 2:
                continue
            try:
                regime_data[rname]["finsight"].append(roc_auc_score(y[mask], p_fs[mask]))
                regime_data[rname]["lgbm"].append(roc_auc_score(y[mask], p_bl[mask]))
            except:
                pass

    results = {}
    print("=" * 70)
    print("  Regime-conditioned AUC")
    print("=" * 70)

    for rname, rdata in regime_data.items():
        if not rdata["finsight"]:
            continue
        fs_mean = float(np.mean(rdata["finsight"]))
        fs_std  = float(np.std(rdata["finsight"]))
        bl_mean = float(np.mean(rdata["lgbm"])) if rdata["lgbm"] else None
        delta   = round(fs_mean - bl_mean, 4) if bl_mean else None

        lgbm_str = f"{bl_mean:.4f}" if bl_mean else "0.0000"
        print(f"  {rname:16s} FinSight={fs_mean:.4f}±{fs_std:.4f}  LGBM={lgbm_str}  Delta={delta}")

        results[rname] = {
            "finsight_auc_mean": fs_mean,
            "finsight_auc_std": fs_std,
            "lgbm_auc_mean": bl_mean,
            "delta": delta,
            "n_tickers": len(rdata["finsight"])
        }

    # B4: Bear Trending DM test
    if bear_panel_rows:
        df_bear = pd.DataFrame(bear_panel_rows)
        res = clustered_dm_test(df_bear, "date", "loss_fs", "loss_bl", h=5)
        print(f"\n  Bear Trending Clustered DM: stat={res.dm_stat:.3f}, p={res.p_value:.4g} (N_dates={res.n_dates})")
        results["Bear Trending"]["dm_stat"] = float(res.dm_stat)
        results["Bear Trending"]["dm_p"] = float(res.p_value)

    with open("regime_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print("\nSaved: regime_results.json")

if __name__ == "__main__":
    main()
