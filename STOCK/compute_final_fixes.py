"""
compute_final_fixes.py — Computes the remaining data for the 7 IEEE paper fixes.
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np

def run_cibil_correction():
    print("=" * 70)
    print("  FIX 2: CIBIL Bias Correction")
    print("=" * 70)
    
    # Load dataset
    internal = pd.read_excel("Internal_Bank_Dataset.xlsx")
    external = pd.read_excel("External_Cibil_Dataset.xlsx")
    merged = pd.merge(internal, external, on="PROSPECTID", how="inner")
    merged.replace(-99999, np.nan, inplace=True)
    
    # Feature mapping
    merged['util_pct'] = merged['CC_utilization'].clip(0, 100)
    total_accounts = (merged['num_std'].fillna(0) + merged['num_sub'].fillna(0) + 
                      merged['num_dbt'].fillna(0) + merged['num_lss'].fillna(0))
    merged['otp_pct'] = np.where(total_accounts > 0,
                                 (merged['num_std'].fillna(0) / total_accounts * 100).clip(0, 100), 50)
    merged['missed'] = merged['num_times_30p_dpd'].fillna(0).clip(0, 12).astype(int)
    merged['inquiries'] = merged['tot_enq'].fillna(0).clip(0, 10).astype(int)
    merged['credit_age'] = (merged['Time_With_Curr_Empr'].fillna(0) / 12).clip(0, 30)
    merged['has_cc'] = (merged['CC_Flag'].fillna(0) > 0).astype(int)
    merged['has_secured'] = (merged['HL_Flag'].fillna(0) > 0).astype(int)
    merged['has_unsecured'] = ((merged['PL_Flag'].fillna(0) > 0) | (merged['GL_Flag'].fillna(0) > 0)).astype(int)
    
    def cibil_formula(row):
        BASE = 300
        payment = max(0, min(210, row['otp_pct'] * 2.1 - row['missed'] * 15.0))
        u = row['util_pct'] if not np.isnan(row['util_pct']) else 30
        if u <= 10: utilization = 180
        elif u <= 30: utilization = 180 - ((u - 10) / 20 * 40)
        elif u <= 50: utilization = 140 - ((u - 30) / 20 * 60)
        elif u <= 75: utilization = 80 - ((u - 50) / 25 * 50)
        else: utilization = max(0, 30 - ((u - 75) / 25 * 30))
        age = min(90, row['credit_age'] * 6)
        mix = (row['has_cc'] + row['has_secured'] + row['has_unsecured']) * 20
        inq = max(0, 60 - row['inquiries'] * 10)
        return max(300, min(900, BASE + payment + utilization + age + mix + inq))
    
    valid = merged.dropna(subset=['Credit_Score', 'util_pct', 'otp_pct']).copy()
    valid['formula_score'] = valid.apply(cibil_formula, axis=1)
    
    actual = valid['Credit_Score'].values
    raw_pred = valid['formula_score'].values
    
    # Correction
    bias = np.mean(raw_pred - actual)
    corrected_pred = raw_pred - bias
    corrected_pred = np.clip(corrected_pred, 300, 900)
    
    raw_mae = np.mean(np.abs(raw_pred - actual))
    corr_mae = np.mean(np.abs(corrected_pred - actual))
    
    def band(score):
        if score >= 850: return 4
        if score >= 750: return 3
        if score >= 650: return 2
        if score >= 550: return 1
        return 0
        
    actual_band = np.array([band(s) for s in actual])
    raw_band = np.array([band(s) for s in raw_pred])
    corr_band = np.array([band(s) for s in corrected_pred])
    
    raw_exact = np.mean(actual_band == raw_band) * 100
    raw_adj = np.mean(np.abs(actual_band - raw_band) <= 1) * 100
    corr_exact = np.mean(actual_band == corr_band) * 100
    corr_adj = np.mean(np.abs(actual_band - corr_band) <= 1) * 100
    
    print(f"  Raw MAE: {raw_mae:.1f} | Corrected MAE: {corr_mae:.1f}")
    print(f"  Raw Exact Band: {raw_exact:.1f}% | Corrected Exact Band: {corr_exact:.1f}%")
    print(f"  Raw Adj Band: {raw_adj:.1f}% | Corrected Adj Band: {corr_adj:.1f}%")
    print(f"  Bias correction factor: -{bias:.1f} points")

def run_other_fixes():
    from config import CONFIG, ALL_FEATURES
    from data_pipeline import DataPipeline
    from feature_engine import FeatureEngine
    from garch_model import GARCHModel
    from lstm_model import LSTMPredictor
    from lgbm_model import LGBMSignalClassifier
    from meta_learner import MetaLearner
    from sentiment_engine import SentimentEngine
    from sklearn.metrics import accuracy_score, f1_score
    from backtest_engine import BacktestEngine
    
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()
    
    print("\n" + "=" * 70)
    print("  FIX 4: Mid-Cap Generalization (YESBANK.NS)")
    print("=" * 70)
    
    try:
        df, market, _ = dp.process("YESBANK.NS")
        df = fe.compute_all(df, forex_series=dp.fetch_forex_rate("USD", "INR"), 
                            nifty_series=dp.fetch_index_data("^NSEI"), 
                            vix_series=dp.fetch_index_data("^INDIAVIX"), is_indian=True)
        df = se.get_historical_features(df, {})
        df = garch.fit_transform(df)
        
        fwd_ret = df["Close"].pct_change(5).shift(-5)
        df["label_5d"] = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
        df.dropna(subset=["label_5d"] + [c for c in ALL_FEATURES if c in df.columns], inplace=True)
        df["label_5d"] = df["label_5d"].astype(int)
        
        train_df = df.iloc[:-252].copy()
        test_df = df.iloc[-252:].copy()
        
        av_cols = [c for c in ALL_FEATURES if c in df.columns]
        lstm = LSTMPredictor(av_cols)
        lstm.fit(train_df, train_df["label_5d"])
        
        lgbm = LGBMSignalClassifier(av_cols)
        lgbm.fit(train_df, lgbm.create_labels(train_df), train_df.get("regime", pd.Series(0, index=train_df.index)))
        
        lstm_test = lstm.predict(pd.concat([train_df.iloc[-lstm.lookback:], test_df])).loc[test_df.index]
        lgbm_test = lgbm.predict_batch(test_df, test_df.get("regime", pd.Series(0, index=test_df.index)))
        
        val_start = max(0, len(train_df) - 252)
        lstm_val = lstm.predict(train_df.iloc[val_start:]).values
        lgbm_val = lgbm.predict_batch(train_df.iloc[val_start:], train_df.iloc[val_start:].get("regime", pd.Series(0, index=train_df.iloc[val_start:].index)))
        
        meta = MetaLearner()
        meta.fit(lstm_val, lgbm_val[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values, 
                 train_df["Close"].iloc[val_start:].pct_change(5).shift(-5).values)
        
        conf = meta.predict_batch(lstm_test.values, lgbm_test[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values)
        y_true = test_df["label_5d"].values
        sigs = (conf >= 25.0).astype(int)
        
        print(f"  YESBANK.NS Accuracy: {accuracy_score(y_true, sigs)*100:.1f}%")
        print(f"  YESBANK.NS F1: {f1_score(y_true, sigs, zero_division=0)*100:.1f}%")
    except Exception as e:
        print(f"  YESBANK Error: {e}")

    print("\n" + "=" * 70)
    print("  FIX 3, 6, 8: Transaction Costs, Threshold Sensitivity, Bootstrapping")
    print("=" * 70)
    
    # Reload RELIANCE data for backtest and stats
    df, _, _ = dp.process("RELIANCE.NS")
    df = fe.compute_all(df, forex_series=dp.fetch_forex_rate("USD", "INR"), 
                        nifty_series=dp.fetch_index_data("^NSEI"), 
                        vix_series=dp.fetch_index_data("^INDIAVIX"), is_indian=True)
    df = se.get_historical_features(df, {})
    df = garch.fit_transform(df)
    
    fwd_ret = df["Close"].pct_change(5).shift(-5)
    df["label_5d"] = np.where(fwd_ret > 0.005, 1, np.where(fwd_ret < -0.005, 0, np.nan))
    df.dropna(subset=["label_5d"] + [c for c in ALL_FEATURES if c in df.columns], inplace=True)
    df["label_5d"] = df["label_5d"].astype(int)
    
    train_df = df.iloc[:-252].copy()
    test_df = df.iloc[-252:].copy()
    
    lstm = LSTMPredictor(av_cols)
    lstm.fit(train_df, train_df["label_5d"])
    lgbm = LGBMSignalClassifier(av_cols)
    lgbm.fit(train_df, lgbm.create_labels(train_df), train_df.get("regime", pd.Series(0, index=train_df.index)))
    
    lstm_test = lstm.predict(pd.concat([train_df.iloc[-lstm.lookback:], test_df])).loc[test_df.index]
    lgbm_test = lgbm.predict_batch(test_df, test_df.get("regime", pd.Series(0, index=test_df.index)))
    
    lstm_val = lstm.predict(train_df.iloc[val_start:]).values
    lgbm_val = lgbm.predict_batch(train_df.iloc[val_start:], train_df.iloc[val_start:].get("regime", pd.Series(0, index=train_df.iloc[val_start:].index)))
    
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_val[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values, 
             train_df["Close"].iloc[val_start:].pct_change(5).shift(-5).values)
    
    conf = meta.predict_batch(lstm_test.values, lgbm_test[["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]].values)
    y_true = test_df["label_5d"].values
    
    # 6. Threshold Sensitivity
    print("  Threshold Sensitivity:")
    for th in [20, 25, 30]:
        s = (conf >= th).astype(int)
        acc = accuracy_score(y_true, s)*100
        f1 = f1_score(y_true, s, zero_division=0)*100
        print(f"    Thresh {th}: Acc={acc:.1f}% | F1={f1:.1f}%")
        
    # 8. Bootstrap
    print("\n  Bootstrapping 95% CI (1000 resamples):")
    np.random.seed(42)
    accs = []
    sigs25 = (conf >= 25).astype(int)
    for _ in range(1000):
        idx = np.random.choice(len(y_true), len(y_true), replace=True)
        accs.append(accuracy_score(y_true[idx], sigs25[idx]))
    lower = np.percentile(accs, 2.5) * 100
    upper = np.percentile(accs, 97.5) * 100
    print(f"    95% CI: [{lower:.1f}%, {upper:.1f}%] (mean: {np.mean(accs)*100:.1f}%)")
    
    # 3. Transaction Costs
    print("\n  Backtest with Transaction Costs:")
    signals_series = pd.Series(["Buy" if c >= 25 else "Hold" for c in conf], index=test_df.index)
    conf_series = pd.Series(conf, index=test_df.index)
    
    engine = BacktestEngine()
    engine.tx_cost = 0.000  # 0%
    gross_res = engine.run_single(test_df, signals_series, conf_series)["metrics"]
    
    engine.tx_cost = 0.001  # 0.1%
    net_res = engine.run_single(test_df, signals_series, conf_series)["metrics"]
    
    print(f"    Gross Return (0% fee):   {gross_res['total_return']:+.2f}% | Sharpe: {gross_res['sharpe']:.2f} | MDD: {gross_res['max_drawdown']:.2f}%")
    print(f"    Net Return (0.1% fee):   {net_res['total_return']:+.2f}% | Sharpe: {net_res['sharpe']:.2f} | MDD: {net_res['max_drawdown']:.2f}%")
    print(f"    Number of trades:        {net_res['n_trades']}")

if __name__ == "__main__":
    run_cibil_correction()
    run_other_fixes()
