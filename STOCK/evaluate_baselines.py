import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from config import ALL_FEATURES
from data_pipeline import DataPipeline
from feature_engine import FeatureEngine
from sentiment_engine import SentimentEngine
from garch_model import GARCHModel

def make_5day_labels(df):
    """Create 5-day horizon binary labels (1=bullish >0, 0=bearish <=0)."""
    return (df["Close"].pct_change(5).shift(-5) > 0).astype(int)

def evaluate_baselines(ticker="RELIANCE.NS"):
    print(f"\n{'='*68}")
    print(f"  Evaluating Baselines: {ticker}")
    print(f"{'='*68}\n")

    dp = DataPipeline()
    fe = FeatureEngine()
    se = SentimentEngine()
    garch = GARCHModel()
    
    train_tickers = [ticker, "TCS.NS", "INFY.NS"] if ticker.endswith(".NS") else [ticker]
    all_train_dfs = []
    target_test_df = None
    target_available = []

    try:
        _, market, _ = dp.process(ticker)
    except Exception as e:
        print(f"  ✗ Failed initial fetch: {e}")
        return
        
    is_indian = market in ["NSE", "BSE"]
    forex = dp.fetch_forex_rate("USD", "INR") if is_indian else pd.Series(dtype=float)
    nifty = dp.fetch_index_data("^NSEI") if is_indian else pd.Series(dtype=float)
    vix = dp.fetch_index_data("^INDIAVIX") if is_indian else pd.Series(dtype=float)

    test_size = 252

    for t in train_tickers:
        try:
            df_t, _, _ = dp.process(t)
            df_t = fe.compute_all(df_t, forex_series=forex, nifty_series=nifty, vix_series=vix, is_indian=is_indian)
            df_t = se.get_historical_features(df_t, {})
            df_t = garch.fit_transform(df_t)

            available = [c for c in ALL_FEATURES if c in df_t.columns]
            df_t["label_5d"] = make_5day_labels(df_t)
            df_t.dropna(subset=available + ["label_5d"], inplace=True)
            df_t["label_5d"] = df_t["label_5d"].astype(int)

            if t == ticker:
                target_available = available
                train_df_t = df_t.iloc[:-test_size].copy()
                target_test_df = df_t.iloc[-test_size:].copy()
                all_train_dfs.append(train_df_t)
            else:
                all_train_dfs.append(df_t)
        except Exception as e:
            print(f"  ✗ Failed for {t}: {e}")

    train_df = pd.concat(all_train_dfs).reset_index(drop=True)
    test_df = target_test_df.reset_index(drop=True)
    
    # We use only the technical and sentiment features (no LSTM probs)
    features = target_available
    X_train = train_df[features].fillna(0)
    y_train = train_df["label_5d"].values
    
    X_test = test_df[features].fillna(0)
    y_test = test_df["label_5d"].values
    
    print(f"  Train Data: {len(X_train)} rows | Test Data: {len(X_test)} rows")
    print("\n  [1/2] Training Random Forest Baseline...")
    rf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)
    
    print("  [2/2] Training Logistic Regression Baseline...")
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    lr_preds = lr.predict(X_test)

    # Calculate metrics
    def calc_metrics(name, y_true, y_pred):
        acc = accuracy_score(y_true, y_pred) * 100
        pre = precision_score(y_true, y_pred, zero_division=0) * 100
        rec = recall_score(y_true, y_pred, zero_division=0) * 100
        f1  = f1_score(y_true, y_pred, zero_division=0) * 100
        return f"| {name:<28} | {acc:>5.1f} | {pre:>5.1f} | {rec:>5.1f} | {f1:>5.1f} |"

    print("\n" + "="*72)
    print("  Table I: Baseline Model Performance (5-Day Horizon)")
    print("="*72)
    print("| Model                        | Acc % | Pre % | Rec % |  F1 % |")
    print("-" * 72)
    print(calc_metrics("Logistic Regression", y_test, lr_preds))
    print(calc_metrics("Random Forest", y_test, rf_preds))
    print("="*72 + "\n")

if __name__ == "__main__":
    evaluate_baselines("RELIANCE.NS")
