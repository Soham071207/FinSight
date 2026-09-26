"""
run_significance_tests.py
Phase 1.2 -- McNemar, Diebold-Mariano, Wilcoxon tests for Section V.B.
Run after: python run_offline_evaluation.py
Output: significance_results.json
"""
import warnings, os, json
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import false_discovery_control
from sklearn.metrics import roc_auc_score
from dm_test_clustered import clustered_dm_test

def mcnemar_test(correct_a, correct_b):
    b = int(np.sum(correct_a & ~correct_b))
    c = int(np.sum(~correct_a & correct_b))
    n = b + c
    if n == 0:
        return b, c, 0.0, 1.0
    if n >= 25:
        stat = (abs(b - c) - 1.0) ** 2 / n
        p    = 1 - stats.chi2.cdf(stat, df=1)
    else:
        stat = abs(b - c)
        p    = float(stats.binom_test(min(b, c), n, 0.5)) * 2
    return b, c, float(stat), float(p)

import pandas as pd
from dm_test_clustered import clustered_dm_test

def wilcoxon_auc(auc_a, auc_b):
    if len(auc_a) < 5:
        return None, None
    stat, p = stats.wilcoxon(auc_a, auc_b, alternative="greater")
    return float(stat), float(p)

def main():
    arrays_path = "per_ticker_predictions.json"
    if not os.path.exists(arrays_path):
        print(f"[INFO] {arrays_path} not found. Run run_offline_evaluation.py first.")
        if os.path.exists("true_metrics.json"):
            with open("true_metrics.json") as f:
                m = json.load(f)
            print("\nAggregate metrics from true_metrics.json:")
            for model, mdict in m.items():
                parts = []
                for k, v in mdict.items():
                    if isinstance(v, dict):
                        parts.append(f"{k}={v.get('mean',0):.4f}+-{v.get('std',0):.4f}")
                    else:
                        parts.append(f"{k}={float(v):.4f}")
                print(f"  {model:22s}  {'  '.join(parts)}")
        return

    with open(arrays_path) as f:
        arrays = json.load(f)
    per_ticker = arrays.get("per_ticker", [])
    if not per_ticker:
        print("[ERROR] per_ticker key missing."); return

    baselines = [k for k in per_ticker[0].keys()
                 if k not in ("y_true", "FinSight", "ticker", "dates", "closes", "atrs", "regimes", "finsight_scores_raw")]
    results = {}
    print("=" * 70)
    print("  Statistical Significance Tests")
    print("=" * 70)

    for baseline in baselines:
        print(f"\nFinSight vs {baseline}:")
        all_corr_fs, all_corr_bl = [], []
        auc_fs, auc_bl = [], []
        panel_rows = []

        for td in per_ticker:
            tk   = td.get("ticker", "unknown")
            y    = np.array(td["y_true"])
            p_fs = np.array(td["FinSight"])
            p_bl = np.array(td.get(baseline, [0.5]*len(y)))
            dates = td.get("dates", [])
            
            if len(p_bl) != len(y) or len(dates) != len(y): continue
            
            all_corr_fs.extend(((p_fs >= 0.5) == y).tolist())
            all_corr_bl.extend(((p_bl >= 0.5) == y).tolist())
            
            for i in range(len(y)):
                panel_rows.append({
                    "date": dates[i], 
                    "ticker": tk, 
                    "loss_fs": (y[i] - p_fs[i])**2, 
                    "loss_bl": (y[i] - p_bl[i])**2
                })

            if len(np.unique(y)) >= 2:
                try:
                    auc_fs.append(roc_auc_score(y, p_fs))
                    auc_bl.append(roc_auc_score(y, p_bl))
                except Exception: pass

        b, c, stat, p = mcnemar_test(np.array(all_corr_fs, bool), np.array(all_corr_bl, bool))
        print(f"  McNemar: b={b}, c={c}, chi2={stat:.3f}, p={p:.4f}  ({'SIGNIFICANT' if p<0.05 else 'not significant'})")
        ws, wp = wilcoxon_auc(auc_fs, auc_bl)
        if wp is not None:
            print(f"  Wilcoxon AUC: stat={ws:.1f}, p={wp:.4f}")

        # Fix B5: Conditional vs Unconditional Accuracy
        try:
            valid_tds = [td for td in per_ticker if len(td.get(baseline, [])) == len(td["y_true"]) and len(td["FinSight"]) == len(td["y_true"])]
            if valid_tds:
                all_p_fs_np = np.concatenate([np.array(td["FinSight"]) for td in valid_tds])
                all_y_np = np.concatenate([np.array(td["y_true"]) for td in valid_tds])
                
                # Abstentions are exactly 0.5
                abstained = (all_p_fs_np == 0.5)
                total_preds = len(all_y_np)
                n_abstained = abstained.sum()
                
                non_abstained = ~abstained
                correct_cond = ((all_p_fs_np[non_abstained] > 0.5) == all_y_np[non_abstained]).sum()
                cond_acc = correct_cond / max(1, non_abstained.sum())
                
                correct_uncond = ((all_p_fs_np > 0.5) == all_y_np).sum()
                uncond_acc = correct_uncond / total_preds
                
                print(f"  Accuracy (Conditional on non-abstention): {cond_acc:.4f} (N={non_abstained.sum()})")
                print(f"  Accuracy (Unconditional / All-in): {uncond_acc:.4f} (N={total_preds}, Abstained={n_abstained})")
            else:
                cond_acc, uncond_acc, n_abstained = 0.0, 0.0, 0
        except Exception as e:
            cond_acc, uncond_acc, n_abstained = 0.0, 0.0, 0

        entry = {"mcnemar_b": b, "mcnemar_c": c, "mcnemar_stat": stat, "mcnemar_p": p,
                 "significant_at_005": p < 0.05,
                 "mean_auc_finsight": float(np.mean(auc_fs)) if auc_fs else None,
                 "mean_auc_baseline": float(np.mean(auc_bl)) if auc_bl else None,
                 "wilcoxon_stat": ws, "wilcoxon_p": wp,
                 "cond_acc": float(cond_acc), "uncond_acc": float(uncond_acc), "n_abstained": int(n_abstained)}

        if baseline in ("StandaloneLightGBM", "XGBoost", "RandomForest"):
            df_panel = pd.DataFrame(panel_rows)
            res = clustered_dm_test(df_panel, "date", "loss_fs", "loss_bl", h=5)
            dm_stat, dm_p = res.dm_stat, res.p_value
            print(f"  Clustered DM (Brier, h=5): stat={dm_stat:.3f}, p={dm_p:.4g} (N_dates={res.n_dates})")
            entry.update({"dm_stat": float(dm_stat), "dm_p": float(dm_p), "finsight_better_calibration": bool(dm_stat<0 and dm_p<0.05)})

        results[f"FinSight_vs_{baseline}"] = entry

    # Fix B6: Benjamini-Hochberg FDR Correction
    mcnemar_ps = []
    dm_ps = []
    baselines_mcnemar = []
    baselines_dm = []
    
    for k, v in results.items():
        if "mcnemar_p" in v:
            mcnemar_ps.append(v["mcnemar_p"])
            baselines_mcnemar.append(k)
        if "dm_p" in v:
            dm_ps.append(v["dm_p"])
            baselines_dm.append(k)
            
    mcnemar_ps_bh = false_discovery_control(mcnemar_ps)
    dm_ps_bh = false_discovery_control(dm_ps)
    
    for i, k in enumerate(baselines_mcnemar):
        results[k]["mcnemar_p_bh"] = float(mcnemar_ps_bh[i])
    for i, k in enumerate(baselines_dm):
        results[k]["dm_p_bh"] = float(dm_ps_bh[i])
        
    print(f"\n  FDR Corrected McNemar p-values: {np.round(mcnemar_ps_bh, 4)}")
    print(f"  FDR Corrected DM p-values: {np.round(dm_ps_bh, 4)}")

    with open("significance_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print("\nSaved: significance_results.json")

if __name__ == "__main__":
    main()
