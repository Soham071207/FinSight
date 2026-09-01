import pandas as pd
import numpy as np
from config import CONFIG, ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from sentiment_engine import SentimentEngine
from garch_model import GARCHModel
from lstm_model import LSTMPredictor
from lgbm_model import LGBMSignalClassifier
from meta_learner import MetaLearner

def make_5day_labels(df):
    return (df["Close"].pct_change(5).shift(-5) > 0).astype(int)

def backtest(ticker="RELIANCE.NS"):
    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()
    
    train_tickers = [ticker, "TCS.NS", "INFY.NS"] if ticker.endswith(".NS") else [ticker]
    all_train_dfs = []
    
    try:
        _, market, _ = dp.process(ticker)
    except Exception as e:
        print(f"Failed initial fetch: {e}")
        return
        
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)

    test_size = 252
    print("Generating data and features...")

    for t in train_tickers:
        df_t, _, _ = dp.process(t)
        df_t = fe.compute_all(df_t, forex_series=forex, nifty_series=nifty, vix_series=vix, is_indian=is_indian)
        df_t = se.get_historical_features(df_t, {})
        df_t = garch.fit_transform(df_t)

        available = [c for c in ALL_FEATURES if c in df_t.columns]
        df_t["label_5d"] = make_5day_labels(df_t)
        df_t.dropna(subset=available + ["label_5d"], inplace=True)
        df_t["label_5d"] = df_t["label_5d"].astype(int)

        if t == ticker:
            target_train_df = df_t.iloc[:-test_size].copy()
            target_test_df = df_t.iloc[-test_size:].copy()
            target_available = available
            all_train_dfs.append(target_train_df)
        else:
            all_train_dfs.append(df_t)

    # 4. LSTM
    print("Training LSTM...")
    lstm = LSTMPredictor(target_available)
    lstm.fit(target_train_df, target_train_df["label_5d"])
    
    full_lstm = pd.concat([target_train_df.iloc[-lstm.lookback:], target_test_df])
    lstm_probs_test = lstm.predict(full_lstm).loc[target_test_df.index]
    
    lstm_probs_train_list = [lstm.predict(df_t) for df_t in all_train_dfs]
        
    train_df = pd.concat(all_train_dfs).reset_index(drop=True)
    test_df = target_test_df.reset_index(drop=True)
    y_true = test_df["label_5d"].values
    available = target_available
    
    train_df["lstm_prob"] = pd.concat(lstm_probs_train_list).reset_index(drop=True).values
    test_df["lstm_prob"]  = lstm_probs_test.values

    # 5. LightGBM
    print("Training LightGBM...")
    lgbm_feats = list(dict.fromkeys(available + ["lstm_prob", "garch_vol"]))
    lgbm_feats = [c for c in lgbm_feats if c in train_df.columns]
    
    CONFIG["lgbm_num_leaves"] = 31
    CONFIG["lgbm_learning_rate"] = 0.01
    CONFIG["lgbm_n_estimators"] = 600
    lgbm = LGBMSignalClassifier(lgbm_feats)
    if hasattr(lgbm, "model"):
        lgbm.model.set_params(subsample=0.7, reg_alpha=0.5, reg_lambda=0.1)
        
    labels_4class = lgbm.create_labels(train_df)
    regimes_train = train_df["regime"] if "regime" in train_df.columns else pd.Series(0, index=train_df.index)
    lgbm.fit(train_df, labels_4class, regimes_train)

    regimes_test = test_df["regime"] if "regime" in test_df.columns else pd.Series(0, index=test_df.index)
    lgbm_out = lgbm.predict_batch(test_df, regimes_test)

    # 6. MetaLearner
    print("Training Meta-Learner...")
    val_start = max(0, len(train_df) - 252)
    df_val = train_df.iloc[val_start:].copy()
    lstm_val = lstm.predict(df_val).values
    val_regimes = df_val["regime"] if "regime" in df_val.columns else pd.Series(0, index=df_val.index)
    lgbm_val = lgbm.predict_batch(df_val, val_regimes)
    
    prob_cols = ["prob_strong_buy", "prob_buy", "prob_hold", "prob_sell"]
    lgbm_val_p = lgbm_val[prob_cols].values
    next_rets = df_val["Close"].pct_change(5).shift(-5).values
    
    meta = MetaLearner()
    meta.fit(lstm_val, lgbm_val_p, next_rets)
    
    lgbm_test_p = lgbm_out[prob_cols].values
    ensemble_conf = meta.predict_batch(lstm_probs_test.values, lgbm_test_p)
    
    best_t_acc = 25.0
    signals = (ensemble_conf >= best_t_acc).astype(int)
    
    # --- Financial Backtest ---
    print("Simulating trading portfolio...")
    daily_returns = target_test_df["Close"].pct_change().fillna(0).values
    
    # We shift signal by 1 day because signal generated at t uses Close at t to trade at t+1 Open.
    shifted_signals = np.roll(signals, shift=1)
    shifted_signals[0] = 0
    
    strategy_returns = shifted_signals * daily_returns
    bh_returns = daily_returns
    
    def calc_sharpe(ret_series, risk_free=0.07):
        ann_ret = np.prod(1 + ret_series) - 1
        ann_vol = np.std(ret_series) * np.sqrt(252)
        if ann_vol == 0: return 0
        return (ann_ret - risk_free) / ann_vol
        
    def calc_max_dd(ret_series):
        cum_ret = np.cumprod(1 + ret_series)
        peak = np.maximum.accumulate(cum_ret)
        drawdown = (cum_ret - peak) / peak
        return np.min(drawdown)
        
    strat_cum = np.prod(1 + strategy_returns) - 1
    bh_cum = np.prod(1 + bh_returns) - 1
    
    strat_sharpe = calc_sharpe(strategy_returns)
    bh_sharpe = calc_sharpe(bh_returns)
    
    strat_mdd = calc_max_dd(strategy_returns)
    bh_mdd = calc_max_dd(bh_returns)
    
    print("\n" + "="*60)
    print("  FINANCIAL BACKTEST PERFORMANCE (Out-of-Sample: 252 Days)")
    print("="*60)
    print(f"| Metric           | Ensemble Strategy | Buy & Hold      |")
    print("-" * 60)
    print(f"| Cumulative Ret   | {strat_cum*100:>16.1f}% | {bh_cum*100:>14.1f}% |")
    print(f"| Annualised Vol   | {np.std(strategy_returns)*np.sqrt(252)*100:>16.1f}% | {np.std(bh_returns)*np.sqrt(252)*100:>14.1f}% |")
    print(f"| Sharpe Ratio     | {strat_sharpe:>17.2f} | {bh_sharpe:>15.2f} |")
    print(f"| Max Drawdown     | {strat_mdd*100:>16.1f}% | {bh_mdd*100:>14.1f}% |")
    print("="*60 + "\n")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    backtest("RELIANCE.NS")
