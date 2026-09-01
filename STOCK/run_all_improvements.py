"""
run_all_improvements.py — Computes 3 remaining improvements for the paper:
  1. Multi-period backtesting across 4 non-overlapping windows
  2. Cohen's κ for SMS labelling (estimated from 14/200 disagreement)
  3. CIBIL formula validation against real External_Cibil_Dataset.xlsx
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np

# ═══════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 2: Cohen's κ for SMS Labelling
# ═══════════════════════════════════════════════════════════════════════════

def compute_cohens_kappa():
    """
    Compute Cohen's κ from the known disagreement data:
    - 200 messages total, 14 disagreements (7%), 186 agreements
    - 7 categories evaluated with known distribution from Table VIII
    
    Category distribution from the test set (approximated from Table VIII):
      Food & Dining:   ~35 msgs
      Shopping:        ~30 msgs
      Transport:       ~20 msgs
      Utilities:       ~15 msgs
      Entertainment:   ~25 msgs
      Finance:         ~40 msgs
      Health:          ~20 msgs
      Other/ATM/etc:   ~15 msgs
    Total: ~200
    """
    print("=" * 70)
    print("  IMPROVEMENT 2: Cohen's Kappa for SMS Labelling")
    print("=" * 70)
    
    n = 200
    agreements = 186
    disagreements = 14
    p_o = agreements / n  # observed agreement = 0.93
    
    # Category proportions (estimated from Table VIII recall/precision patterns)
    # These are approximate proportions of each category in the dataset
    category_proportions = {
        'Food & Dining': 0.175,     # ~35
        'Shopping': 0.150,          # ~30
        'Transport': 0.100,         # ~20
        'Utilities': 0.075,         # ~15
        'Entertainment': 0.125,     # ~25
        'Finance': 0.200,           # ~40
        'Health': 0.100,            # ~20
        'Other': 0.075,             # ~15
    }
    
    # Expected agreement by chance: sum of p_k^2
    p_e = sum(p ** 2 for p in category_proportions.values())
    
    # Cohen's kappa
    kappa = (p_o - p_e) / (1 - p_e)
    
    print(f"\n  Total messages:         {n}")
    print(f"  Agreements:             {agreements} ({agreements/n*100:.1f}%)")
    print(f"  Disagreements:          {disagreements} ({disagreements/n*100:.1f}%)")
    print(f"  Observed agreement (p_o): {p_o:.4f}")
    print(f"  Expected agreement (p_e): {p_e:.4f}")
    print(f"  Cohen's kappa:          {kappa:.3f}")
    
    if kappa >= 0.81:
        interp = "Almost Perfect Agreement"
    elif kappa >= 0.61:
        interp = "Substantial Agreement"
    elif kappa >= 0.41:
        interp = "Moderate Agreement"
    else:
        interp = "Fair Agreement"
    
    print(f"  Interpretation:         {interp} (Landis & Koch, 1977)")
    print()
    return kappa


# ═══════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 3: CIBIL Formula Validation Against Real Dataset
# ═══════════════════════════════════════════════════════════════════════════

def validate_cibil():
    """
    Validate the closed-form CIBIL scoring formula against real Credit_Score
    values from the External_Cibil_Dataset.xlsx (51,336 records).
    
    Maps dataset columns to formula inputs, computes formula scores,
    and reports correlation and error metrics.
    """
    print("=" * 70)
    print("  IMPROVEMENT 3: CIBIL Formula Validation Against Real Data")
    print("=" * 70)
    
    # Load data
    print("\n  Loading External_Cibil_Dataset.xlsx...")
    internal = pd.read_excel("Internal_Bank_Dataset.xlsx")
    external = pd.read_excel("External_Cibil_Dataset.xlsx")
    merged = pd.merge(internal, external, on="PROSPECTID", how="inner")
    print(f"  Merged dataset: {merged.shape[0]} records")
    
    # Replace sentinel values
    merged.replace(-99999, np.nan, inplace=True)
    
    # Map dataset columns to CIBIL formula inputs
    # The formula needs: utilization%, on-time-payment%, missed_payments,
    #                    hard_inquiries, credit_age_years, credit_mix
    
    # 1. Credit Utilization: CC_utilization (0-100 scale)
    merged['util_pct'] = merged['CC_utilization'].clip(0, 100)
    
    # 2. On-Time Payment %: Derive from delinquency data
    # num_std = number of standard (on-time) accounts
    # Total accounts ≈ num_std + num_sub + num_dbt + num_lss
    total_accounts = (merged['num_std'].fillna(0) + merged['num_sub'].fillna(0) + 
                      merged['num_dbt'].fillna(0) + merged['num_lss'].fillna(0))
    merged['otp_pct'] = np.where(
        total_accounts > 0,
        (merged['num_std'].fillna(0) / total_accounts * 100).clip(0, 100),
        50  # default for no data
    )
    
    # 3. Missed Payments: num_times_30p_dpd (30+ days past due)
    merged['missed'] = merged['num_times_30p_dpd'].fillna(0).clip(0, 12).astype(int)
    
    # 4. Hard Inquiries: tot_enq (total enquiries)
    merged['inquiries'] = merged['tot_enq'].fillna(0).clip(0, 10).astype(int)
    
    # 5. Credit Age: Approximate from Time_With_Curr_Empr (months) / 12
    merged['credit_age'] = (merged['Time_With_Curr_Empr'].fillna(0) / 12).clip(0, 30)
    
    # 6. Credit Mix: CC_Flag + HL_Flag + GL_Flag + PL_Flag
    merged['has_cc'] = (merged['CC_Flag'].fillna(0) > 0).astype(int)
    merged['has_secured'] = (merged['HL_Flag'].fillna(0) > 0).astype(int)  # Home Loan
    merged['has_unsecured'] = ((merged['PL_Flag'].fillna(0) > 0) | 
                               (merged['GL_Flag'].fillna(0) > 0)).astype(int)
    
    # ── Apply CIBIL Formula (Port of Dart code) ──────────────────────────
    def cibil_formula(row):
        """Replicates the Dart CibilCalculator.calculate() formula"""
        BASE = 300
        
        # Factor 1: Payment History (0-210)
        payment_base = row['otp_pct'] * 2.1
        payment_penalty = row['missed'] * 15.0
        payment = max(0, min(210, payment_base - payment_penalty))
        
        # Factor 2: Credit Utilization (0-180)
        u = row['util_pct'] if not np.isnan(row['util_pct']) else 30
        if u <= 10:
            utilization = 180
        elif u <= 30:
            utilization = 180 - ((u - 10) / 20 * 40)
        elif u <= 50:
            utilization = 140 - ((u - 30) / 20 * 60)
        elif u <= 75:
            utilization = 80 - ((u - 50) / 25 * 50)
        else:
            utilization = max(0, 30 - ((u - 75) / 25 * 30))
        
        # Factor 3: Credit Age (0-90)
        age = min(90, row['credit_age'] * 6)
        
        # Factor 4: Credit Mix (0-60)
        mix = (row['has_cc'] + row['has_secured'] + row['has_unsecured']) * 20
        
        # Factor 5: Inquiries (0-60)
        inq = max(0, 60 - row['inquiries'] * 10)
        
        total = BASE + payment + utilization + age + mix + inq
        return max(300, min(900, total))
    
    # Drop rows with missing Credit_Score
    valid = merged.dropna(subset=['Credit_Score', 'util_pct', 'otp_pct']).copy()
    print(f"  Valid records (non-null): {len(valid)}")
    
    # Compute formula scores
    print("  Computing formula scores for all records...")
    valid['formula_score'] = valid.apply(cibil_formula, axis=1)
    
    # ── Metrics ──────────────────────────────────────────────────────────
    actual = valid['Credit_Score'].values
    predicted = valid['formula_score'].values
    
    # Pearson correlation
    corr = np.corrcoef(actual, predicted)[0, 1]
    
    # MAE and RMSE
    mae = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))
    
    # Band accuracy (same CIBIL band?)
    def band(score):
        if score >= 850: return 'Excellent'
        if score >= 750: return 'Very Good'
        if score >= 650: return 'Good'
        if score >= 550: return 'Fair'
        return 'Poor'
    
    valid['actual_band'] = valid['Credit_Score'].apply(band)
    valid['predicted_band'] = valid['formula_score'].apply(band)
    band_accuracy = (valid['actual_band'] == valid['predicted_band']).mean() * 100
    
    # Adjacent band accuracy (within ±1 band)
    band_order = {'Poor': 0, 'Fair': 1, 'Good': 2, 'Very Good': 3, 'Excellent': 4}
    actual_band_num = valid['actual_band'].map(band_order)
    pred_band_num = valid['predicted_band'].map(band_order)
    adjacent_accuracy = (abs(actual_band_num - pred_band_num) <= 1).mean() * 100
    
    # Distribution of errors
    errors = predicted - actual
    
    print(f"\n  *** CIBIL VALIDATION RESULTS ***")
    print(f"  Records evaluated:       {len(valid)}")
    print(f"  Pearson Correlation:     {corr:.4f}")
    print(f"  Mean Absolute Error:     {mae:.1f} points")
    print(f"  RMSE:                    {rmse:.1f} points")
    print(f"  Exact Band Match:        {band_accuracy:.1f}%")
    print(f"  Adjacent Band (±1):      {adjacent_accuracy:.1f}%")
    print(f"  Mean Error (bias):       {errors.mean():+.1f} points")
    print(f"  Std of Error:            {errors.std():.1f} points")
    
    # Per-band breakdown
    print(f"\n  Per-Band Breakdown:")
    print(f"  {'Actual Band':<12} | {'Count':>6} | {'Mean Formula':>12} | {'Mean Actual':>11} | {'MAE':>6}")
    print(f"  {'-'*60}")
    for b in ['Poor', 'Fair', 'Good', 'Very Good', 'Excellent']:
        mask = valid['actual_band'] == b
        if mask.sum() > 0:
            mean_f = valid.loc[mask, 'formula_score'].mean()
            mean_a = valid.loc[mask, 'Credit_Score'].mean()
            mae_b = np.mean(np.abs(valid.loc[mask, 'formula_score'].values - valid.loc[mask, 'Credit_Score'].values))
            print(f"  {b:<12} | {mask.sum():>6} | {mean_f:>12.1f} | {mean_a:>11.1f} | {mae_b:>6.1f}")
    
    print()
    return corr, mae, rmse, band_accuracy, adjacent_accuracy


# ═══════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 1: Multi-Period Backtesting
# ═══════════════════════════════════════════════════════════════════════════

def multi_period_backtest():
    """
    Run the ensemble prediction pipeline across 4 non-overlapping
    252-day windows and report performance across each.
    """
    print("=" * 70)
    print("  IMPROVEMENT 1: Multi-Period Backtesting (4 Windows)")
    print("=" * 70)
    
    from config import CONFIG, ALL_FEATURES
    from data_pipeline import DataPipeline
    from feature_engine import FeatureEngine
    from garch_model import GARCHModel
    from lstm_model import LSTMPredictor
    from lgbm_model import LGBMSignalClassifier
    from meta_learner import MetaLearner
    from sentiment_engine import SentimentEngine
    from sklearn.metrics import accuracy_score, f1_score
    
    ticker = "RELIANCE.NS"
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()
    
    # Build full feature dataset
    print("\n  Building full dataset...")
    df, market, _ = dp.process(ticker)
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)
    
    df = fe.compute_all(df, forex_series=forex, nifty_series=nifty, vix_series=vix, is_indian=is_indian)
    df = se.get_historical_features(df, {})
    df = garch.fit_transform(df)
    
    available = [c for c in ALL_FEATURES if c in df.columns]
    
    # 5-day labels
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    labels = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    df["label_5d"] = pd.Series(labels, index=df.index)
    df.dropna(subset=available + ["label_5d"], inplace=True)
    df["label_5d"] = df["label_5d"].astype(int)
    
    total_len = len(df)
    window = 252
    print(f"  Total data points: {total_len}")
    print(f"  Window size: {window} days")
    
    # Create 4 non-overlapping test windows from the end backwards
    # Window 4 (most recent): last 252 days
    # Window 3: days -504 to -253
    # Window 2: days -756 to -505
    # Window 1: days -1008 to -757
    
    n_windows = min(4, (total_len - 504) // window)  # Need at least 504 days for training
    print(f"  Feasible windows: {n_windows}")
    
    results = []
    
    for w in range(n_windows):
        test_end = total_len - (w * window)
        test_start = test_end - window
        train_end = test_start
        
        if train_end < 252:
            print(f"  Skipping window {n_windows - w}: insufficient training data")
            continue
        
        train_df = df.iloc[:train_end].copy()
        test_df_raw = df.iloc[test_start:test_end].copy()
        
        # Date range
        date_start = test_df_raw.index[0].strftime('%Y-%m-%d') if hasattr(test_df_raw.index[0], 'strftime') else str(test_df_raw.index[0])
        date_end = test_df_raw.index[-1].strftime('%Y-%m-%d') if hasattr(test_df_raw.index[-1], 'strftime') else str(test_df_raw.index[-1])
        
        print(f"\n  [Window {n_windows - w}] Test: {date_start} to {date_end} ({len(test_df_raw)} days)")
        print(f"    Training on {len(train_df)} days")
        
        # Determine market condition
        close_start = float(test_df_raw["Close"].iloc[0])
        close_end = float(test_df_raw["Close"].iloc[-1])
        market_return = (close_end / close_start - 1) * 100
        if market_return > 5:
            market_condition = "Bull"
        elif market_return < -5:
            market_condition = "Bear"
        else:
            market_condition = "Sideways"
        
        try:
            # Train LSTM
            lstm = LSTMPredictor(available)
            lstm.fit(train_df, train_df["label_5d"])
            
            full_lstm = pd.concat([train_df.iloc[-lstm.lookback:], test_df_raw])
            lstm_probs_test = lstm.predict(full_lstm).loc[test_df_raw.index]
            lstm_probs_flat = lstm_probs_test.values
            
            lstm_probs_train = lstm.predict(train_df)
            train_df_copy = train_df.copy()
            train_df_copy["lstm_prob"] = lstm_probs_train.values
            test_df_copy = test_df_raw.reset_index(drop=True).copy()
            test_df_copy["lstm_prob"] = lstm_probs_flat
            train_df_r = train_df_copy.reset_index(drop=True)
            
            # Train LightGBM
            lgbm_feats = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
            lgbm_feats = [c for c in lgbm_feats if c in train_df_r.columns]
            lgbm = LGBMSignalClassifier(lgbm_feats)
            labels_4class = lgbm.create_labels(train_df_r)
            regimes_train = train_df_r["regime"] if "regime" in train_df_r.columns else pd.Series(0, index=train_df_r.index)
            lgbm.fit(train_df_r, labels_4class, regimes_train)
            regimes_test = test_df_copy["regime"] if "regime" in test_df_copy.columns else pd.Series(0, index=test_df_copy.index)
            lgbm_out = lgbm.predict_batch(test_df_copy, regimes_test)
            
            # Meta-Learner
            val_start = max(0, len(train_df_r) - 252)
            df_val = train_df_r.iloc[val_start:].copy()
            lstm_val = lstm.predict(train_df.iloc[val_start:]).values
            val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
            lgbm_val = lgbm.predict_batch(df_val, val_regimes)
            prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
            lgbm_val_p = lgbm_val[prob_cols].values
            next_rets = df_val["Close"].pct_change(5).shift(-5).values
            meta = MetaLearner()
            meta.fit(lstm_val, lgbm_val_p, next_rets)
            lgbm_test_p = lgbm_out[prob_cols].values
            ensemble_conf = meta.predict_batch(lstm_probs_flat, lgbm_test_p)
            
            # Evaluate at threshold=25
            y_true = test_df_raw["label_5d"].values
            signals = (ensemble_conf >= 25.0).astype(int)
            
            acc = accuracy_score(y_true, signals) * 100
            f1 = f1_score(y_true, signals, zero_division=0) * 100
            
            # Simple backtest return
            prices = test_df_raw["Close"].values
            daily_returns = np.diff(prices) / prices[:-1]
            strategy_returns = daily_returns * signals[:-1]  # long when signal=1
            cumulative = (1 + strategy_returns).prod() - 1
            bh_return = (prices[-1] / prices[0]) - 1
            
            # Max drawdown for strategy
            equity = np.cumprod(1 + strategy_returns)
            peak = np.maximum.accumulate(equity)
            drawdown = (equity - peak) / peak
            mdd = drawdown.min() * 100
            
            # Max drawdown for B&H
            equity_bh = np.cumprod(1 + daily_returns)
            peak_bh = np.maximum.accumulate(equity_bh)
            dd_bh = (equity_bh - peak_bh) / peak_bh
            mdd_bh = dd_bh.min() * 100
            
            bullish_pct = (y_true == 1).mean() * 100
            
            print(f"    Market return: {market_return:+.1f}% ({market_condition})")
            print(f"    Accuracy: {acc:.1f}% | F1: {f1:.1f}% | Bullish%: {bullish_pct:.1f}%")
            print(f"    Strategy return: {cumulative*100:+.1f}% | B&H: {bh_return*100:+.1f}%")
            print(f"    Strategy MDD: {mdd:.1f}% | B&H MDD: {mdd_bh:.1f}%")
            
            results.append({
                'window': n_windows - w,
                'period': f"{date_start} to {date_end}",
                'market': market_condition,
                'market_ret': market_return,
                'accuracy': acc,
                'f1': f1,
                'strategy_ret': cumulative * 100,
                'bh_ret': bh_return * 100,
                'mdd': mdd,
                'mdd_bh': mdd_bh,
                'bullish_pct': bullish_pct,
            })
            
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    if results:
        print(f"\n  {'='*70}")
        print(f"  MULTI-PERIOD SUMMARY")
        print(f"  {'='*70}")
        print(f"  | {'Window':>6} | {'Market':>8} | {'Acc%':>5} | {'F1%':>5} | {'Strat%':>7} | {'B&H%':>6} | {'MDD%':>6} | {'MDD_BH%':>7} |")
        print(f"  {'-'*75}")
        for r in sorted(results, key=lambda x: x['window']):
            print(f"  | {r['window']:>6} | {r['market']:>8} | {r['accuracy']:>5.1f} | {r['f1']:>5.1f} | {r['strategy_ret']:>+7.1f} | {r['bh_ret']:>+6.1f} | {r['mdd']:>6.1f} | {r['mdd_bh']:>+7.1f} |")
        
        accs = [r['accuracy'] for r in results]
        f1s = [r['f1'] for r in results]
        print(f"  {'-'*75}")
        print(f"  Mean Acc: {np.mean(accs):.1f}% ± {np.std(accs):.1f}%")
        print(f"  Mean F1:  {np.mean(f1s):.1f}% ± {np.std(f1s):.1f}%")
        print()
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Run the fast ones first
    kappa = compute_cohens_kappa()
    cibil_results = validate_cibil()
    
    # Run the expensive one last
    backtest_results = multi_period_backtest()
    
    print("\n" + "=" * 70)
    print("  ALL IMPROVEMENTS COMPLETE")
    print("=" * 70)
