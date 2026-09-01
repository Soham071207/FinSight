"""
mutual_2_api.py  —  REST API wrapper for the Pro Mutual Fund Analysis engine.
Run this locally with:  python mutual_2_api.py
Then the Flutter app connects to http://localhost:5050

Endpoints:
  GET  /health                   → { "status": "ok" }
  POST /analyze                  → run backtest + future projection
  POST /search                   → search AMFI by keyword
"""

import warnings
warnings.filterwarnings("ignore")

import sys, io
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pandas as pd
import joblib
import os
import logging
import threading
from datetime import datetime, timedelta

# ── Background Sync Scheduler (REMOVED) ───────────────────────────────────────
# The auto-sync is now handled professionally via GitHub Actions CI/CD Pipeline
# (.github/workflows/data_sync.yml) to prevent Render ephemeral disk issues.
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ── Reuse the core engine from mutual_2.py ────────────────────────────────────
# (copy-paste the three key functions so this file is standalone)

def xirr(cashflows):
    from scipy.optimize import newton
    cashflows = sorted(cashflows, key=lambda x: x[0])
    if len(cashflows) < 2:
        return 0.0
    t0 = cashflows[0][0]

    def npv(rate):
        if rate <= -1.0:
            return float("inf")
        return sum(amt / ((1.0 + rate) ** ((d - t0).days / 365.25))
                   for d, amt in cashflows)

    for guess in (0.1, 0.0, 0.5, -0.5):
        try:
            return newton(npv, guess) * 100
        except (RuntimeError, OverflowError, ZeroDivisionError):
            continue

    total_inv = sum(-c[1] for c in cashflows[:-1])
    final_val = cashflows[-1][1]
    years = (cashflows[-1][0] - t0).days / 365.25
    if total_inv <= 0 or years <= 0:
        return 0.0
    return ((final_val / total_inv) ** (1 / years) - 1) * 100


def compute_metrics(val_hist, inv_hist, dates, bench_rets=None, rf=0.065):
    v   = np.asarray(val_hist, dtype=np.float64)
    inv = np.asarray(inv_hist, dtype=np.float64)
    n   = len(v)
    out = dict(max_dd=0.0, volatility=0.0, riskScore=5, sortino=0.0,
               beta=0.0, alpha=0.0, abs_return=0.0, cagr=0.0)
    if n < 2 or inv[-1] <= 0:
        return out
    prev = v[:-1]; curr = v[1:]; inj = np.diff(inv)
    safe = prev > 0
    safe_prev = np.where(prev == 0, 1, prev)
    rets = np.where(safe, (curr - inj) / safe_prev - 1, 0.0)
    out["abs_return"] = ((v[-1] - inv[-1]) / inv[-1]) * 100
    years = (dates[-1] - dates[0]).days / 365.25
    if years > 0 and inv[-1] > 0:
        out["cagr"] = ((v[-1] / inv[-1]) ** (1 / years) - 1) * 100
    std = np.std(rets, ddof=1)
    out["volatility"] = std * np.sqrt(252) * 100 if std > 0 else 0.0
    peak = np.maximum.accumulate(v)
    safe_peak = np.where(peak == 0, 1, peak)
    dd   = np.where(peak > 0, (v / safe_peak) - 1, 0.0)
    out["max_dd"] = dd.min() * 100
    ann_ret = (1 + np.mean(rets)) ** 252 - 1
    excess  = ann_ret - rf
    ann_std = std * np.sqrt(252) if std > 0 else 0.0
    score = round((ann_std * 100) / 3.5)
    out["riskScore"] = max(1, min(10, int(score)))
    down = rets[rets < 0]
    down_std = np.std(down, ddof=1) if len(down) > 1 else 0.0
    ann_down = down_std * np.sqrt(252) if down_std > 0 else 0.0
    out["sortino"] = excess / ann_down if ann_down > 0 else 0.0
    if bench_rets is not None:
        br = bench_rets[:len(rets)]
        if len(br) == len(rets) and np.var(br) > 0:
            cov = np.cov(rets, br)
            out["beta"] = cov[0, 1] / cov[1, 1]
            bench_ann = (1 + np.mean(br)) ** 252 - 1
            out["alpha"] = ((ann_ret - rf) - out["beta"] * (bench_ann - rf)) * 100
    return out


def fetch_mftool(scheme_code: str, years: float):
    from mftool import Mftool
    mf  = Mftool()
    meta = mf.get_scheme_details(scheme_code)
    if not meta or "scheme_name" not in meta:
        return None, None
    raw = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
    if raw is None or raw.empty:
        return None, None
    df = raw.copy()
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df.index  = pd.to_datetime(df.index, format="%d-%m-%Y", dayfirst=True)
    df = df.sort_index().dropna(subset=["nav"])
    df = df[~df.index.duplicated(keep="first")]
    cutoff = df.index.max() - timedelta(days=int(years * 365.25) + 60)
    df = df[df.index >= cutoff]
    return df[["nav"]].rename(columns={"nav": "Close"}), meta


def fetch_yfinance(ticker: str, years: float):
    import yfinance as yf
    start = (datetime.today() - timedelta(days=int(years * 365.25) + 365)).strftime("%Y-%m-%d")
    raw = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if raw.empty:
        return None, None
    raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
    if "Close" not in raw.columns:
        return None, None
    info = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        pass
    meta = {
        "scheme_name":     info.get("longName", ticker),
        "fund_house":      info.get("fundFamily", "N/A"),
        "scheme_category": info.get("category", info.get("quoteType", "N/A")),
        "expense_ratio":   info.get("annualReportExpenseRatio", None),
    }
    df = raw[["Close"]].copy().dropna()
    df = df[~df.index.duplicated(keep="first")]
    return df, meta


def search_schemes(keyword: str):
    from mftool import Mftool
    mf = Mftool()
    matches = mf.get_available_schemes(keyword)
    if not matches:
        return {}
    return dict(list(matches.items())[:20])


def is_scheme_code(text: str) -> bool:
    return text.strip().isdigit() and len(text.strip()) >= 5


# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

# --- CIBIL Model Loading ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

model    = joblib.load(os.path.join(BASE_DIR, "cibil_model.pkl"))
medians  = joblib.load(os.path.join(BASE_DIR, "cibil_medians.pkl"))
features = joblib.load(os.path.join(BASE_DIR, "cibil_features.pkl"))   # list of 42 feature names
encoders = joblib.load(os.path.join(BASE_DIR, "cibil_encoders.pkl"))   # LabelEncoders for cat cols
cat_cols = joblib.load(os.path.join(BASE_DIR, "cibil_cat_cols.pkl"))   # list of categorical col names

print("✅ CIBIL model loaded successfully")   # Allow Flutter web/desktop to call this API


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route("/sync-status")
def sync_status():
    """Check the status of the last sync run. Now handled by GitHub actions."""
    return jsonify({"status": "handled_by_github_actions"})


@app.route("/search", methods=["POST"])
def search():
    """
    Body: { "keyword": "HDFC flexi cap" }
    Returns: [ { "code": "119597", "name": "HDFC Flexi Cap Fund - Direct Plan..." }, ... ]
    """
    body    = request.get_json(force=True) or {}
    keyword = body.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "keyword is required"}), 400
    try:
        matches = search_schemes(keyword)
        results = [{"code": code, "name": name} for code, name in matches.items()]
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Body:
    {
      "assets":       ["119597", "120503"],   // AMFI codes or yfinance tickers
      "inv_mode":     1,                      // 1=SIP, 2=Lumpsum, 3=Both
      "base_sip":     10000,
      "step_up_pct":  10,
      "lumpsum_amt":  0,
      "target_years": 5,
      "future_years": 10
    }
    """
    body = request.get_json(force=True) or {}

    asset_keys   = body.get("assets", [])
    inv_mode     = int(body.get("inv_mode", 1))
    base_sip     = float(body.get("base_sip", 10000))
    step_up_pct  = float(body.get("step_up_pct", 10))
    lumpsum_amt  = float(body.get("lumpsum_amt", 0))
    target_years = float(body.get("target_years", 5))
    future_years = float(body.get("future_years", 10))

    if not asset_keys:
        return jsonify({"error": "assets list is required"}), 400

    # ── Fetch data ────────────────────────────────────────────────────────────
    nav_data  = {}
    meta_data = {}
    labels    = {}

    for key in asset_keys:
        key = key.strip()
        if is_scheme_code(key):
            df, meta = fetch_mftool(key, target_years)
        else:
            key = key.upper()
            df, meta = fetch_yfinance(key, target_years)

        if df is None or df.empty or len(df) < 60:
            continue

        nav_data[key]  = df
        meta_data[key] = meta or {}
        name           = (meta or {}).get("scheme_name", key)
        labels[key]    = (name[:50] + "…") if len(name) > 50 else name

    asset_keys = list(nav_data.keys())
    if not asset_keys:
        return jsonify({"error": "No valid data returned for any of the requested assets"}), 422

    # ── Align date range ──────────────────────────────────────────────────────
    common_idx = nav_data[asset_keys[0]].index
    for k in asset_keys[1:]:
        common_idx = common_idx.intersection(nav_data[k].index)

    for k in asset_keys:
        nav_data[k] = nav_data[k].loc[common_idx]

    TARGET_DAYS  = int(target_years * 252)
    TEST_SIZE    = min(TARGET_DAYS, len(common_idx))
    ACTUAL_YEARS = TEST_SIZE / 252

    start_date = common_idx[-TEST_SIZE]
    end_date   = common_idx[-1]

    # ── Run simulations ───────────────────────────────────────────────────────
    SIP_INTERVAL = 21
    results      = {}

    bench_key    = asset_keys[0]
    bench_prices = nav_data[bench_key]["Close"].iloc[-TEST_SIZE:].values.astype(float)
    bench_rets   = np.diff(bench_prices) / bench_prices[:-1]

    for key in asset_keys:
        prices = nav_data[key]["Close"].iloc[-TEST_SIZE:].values.astype(float)
        dates  = nav_data[key].index[-TEST_SIZE:].tolist()

        units = invested = 0.0
        cashflows = []
        val_hist, inv_hist = [], []
        days_since_sip = months = 0
        sip_amt = base_sip

        for i in range(len(prices)):
            price = prices[i]
            dt    = dates[i]
            if i == 0 and lumpsum_amt > 0:
                units    += lumpsum_amt / price
                invested += lumpsum_amt
                cashflows.append((dt, -lumpsum_amt))
            if base_sip > 0:
                days_since_sip += 1
                if days_since_sip >= SIP_INTERVAL:
                    days_since_sip = 0
                    months += 1
                    if months > 0 and months % 12 == 0:
                        sip_amt *= (1 + step_up_pct / 100)
                    units    += sip_amt / price
                    invested += sip_amt
                    cashflows.append((dt, -sip_amt))
            val_hist.append(units * price)
            inv_hist.append(invested)

        final_val = val_hist[-1]
        cashflows.append((dates[-1], final_val))

        xirr_val = xirr(cashflows)
        m        = compute_metrics(val_hist, inv_hist, dates, bench_rets)
        er       = meta_data.get(key, {}).get("expense_ratio", None)
        er_str   = f"{er*100:.2f}%" if er else "N/A"

        # Future projection
        cagr_pct      = m["cagr"]
        future_months = int(future_years * 12)
        monthly_rate  = (1 + cagr_pct / 100) ** (1 / 12) - 1 if cagr_pct > 0 else 0

        f_val = lumpsum_amt if lumpsum_amt > 0 else 0.0
        f_inv = f_val
        f_sip = base_sip
        future_val_hist = [f_val]

        for fm in range(1, future_months + 1):
            f_val = f_val * (1 + monthly_rate)
            if base_sip > 0:
                if fm > 1 and (fm - 1) % 12 == 0:
                    f_sip *= (1 + step_up_pct / 100)
                f_val += f_sip
                f_inv += f_sip
            future_val_hist.append(f_val)

        # NAV history for sparkline (sample every 10th point for size)
        sampled_nav = prices[::10].tolist()
        sampled_dates = [d.strftime("%Y-%m-%d") for d in dates[::10]]

        # Helper: replace NaN/Inf with 0 to prevent JSON serialization crash
        def _sf(val, decimals=2):
            """Safe float: round and replace NaN/Inf with 0."""
            import math
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return 0.0
            return round(f, decimals)

        results[key] = {
            "key":            key,
            "name":           labels.get(key, key),
            "fundHouse":      meta_data.get(key, {}).get("fund_house", "N/A"),
            "category":       meta_data.get(key, {}).get("scheme_category", "N/A"),
            "expenseRatio":   er_str,
            "startDate":      start_date.strftime("%d-%b-%Y"),
            "endDate":        end_date.strftime("%d-%b-%Y"),
            "durationYears":  round(ACTUAL_YEARS, 1),
            "invested":       _sf(invested),
            "finalValue":     _sf(final_val),
            "wealthGain":     _sf(final_val - invested),
            "absReturn":      _sf(m["abs_return"]),
            "cagr":           _sf(m["cagr"]),
            "xirr":           _sf(xirr_val),
            "maxDrawdown":    _sf(m["max_dd"]),
            "volatility":     _sf(m["volatility"]),
            "riskScore":      int(m["riskScore"]) if not np.isnan(m["riskScore"]) else 5,
            "sortino":        _sf(m["sortino"]),
            "beta":           _sf(m["beta"]),
            "alpha":          _sf(m["alpha"]),
            "futureInvested": _sf(f_inv),
            "futureValue":    _sf(f_val),
            "futureWealthGain": _sf(f_val - f_inv),
            "navDates":       sampled_dates,
            "navValues":      [_sf(v) for v in sampled_nav],
            "valHistSampled": [_sf(v) for v in val_hist[::10]],
        }

    # ── Rank assets ───────────────────────────────────────────────────────────
    df_res = pd.DataFrame(results.values())
    for col, asc in [("xirr", False), ("riskScore", True),
                     ("sortino", False), ("maxDrawdown", False)]:
        df_res[f"_r_{col}"] = df_res[col].rank(ascending=asc)
    df_res["score"] = (df_res["_r_xirr"]       * 0.4 +
                       df_res["_r_riskScore"]      * 0.3 +
                       df_res["_r_sortino"]     * 0.2 +
                       df_res["_r_maxDrawdown"] * 0.1)
    df_res = df_res.sort_values("score").reset_index(drop=True)

    ranked = []
    for idx, row in df_res.iterrows():
        entry = results[row["key"]]
        entry["rank"]  = idx + 1
        entry["score"] = round(row["score"], 3)
        ranked.append(entry)

    return jsonify({
        "mode":         inv_mode,
        "actualYears":  round(ACTUAL_YEARS, 1),
        "futureYears":  future_years,
        "benchmarkKey": bench_key,
        "results":      ranked,
    })


@app.route("/live-funds", methods=["GET"])
def live_funds():
    """
    Returns the master_funds_database.csv as JSON for the Flutter Live Dashboard.
    Response:
    {
      "lastSync": "25-May-2026 10:30 AM IST",
      "funds": [
        { "amfiCode": "...", "fundName": "...", "category": "...",
          "cagr1Y": 12.3, "cagr3Y": 15.6, "cagr5Y": 14.2,
          "sharpeRatio": 1.23, "score": 9.87 }
      ]
    }
    """
    import os

    csv_path = os.path.join(os.path.dirname(__file__), "master_funds_database.csv")
    txt_path = os.path.join(os.path.dirname(__file__), "last_sync.txt")

    if not os.path.exists(csv_path):
        return jsonify({"error": "Database not found. Run sync_engine.py first."}), 404

    try:
        df = pd.read_csv(csv_path)
        df = df.fillna(0)

        funds = []
        for _, row in df.iterrows():
            funds.append({
                "amfiCode":    str(row.get("AMFI Code", "")),
                "fundName":    str(row.get("Fund Name", "")),
                "category":    str(row.get("Category", "")),
                "cagr1Y":      round(float(row.get("1Y CAGR (%)", 0)), 2),
                "cagr3Y":      round(float(row.get("3Y CAGR (%)", 0)), 2),
                "cagr5Y":      round(float(row.get("5Y CAGR (%)", 0)), 2),
                "riskScore":   int(row.get("Risk Score", 5)),
                "score":       round(float(row.get("Score", 0)), 3),
            })

        last_sync = "Never"
        try:
            with open(txt_path, "r") as f:
                last_sync = f.read().strip()
        except Exception:
            pass

        return jsonify({"lastSync": last_sync, "funds": funds})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- CIBIL Routes ---
def get_score_band(score: int) -> dict:
    if score >= 750:
        return {"band": "Excellent", "color": "#4CAF50", "message": "You qualify for the best loan rates!"}
    elif score >= 700:
        return {"band": "Good", "color": "#8BC34A", "message": "Good credit. You'll get competitive rates."}
    elif score >= 650:
        return {"band": "Fair", "color": "#FF9800", "message": "Fair credit. Consider improving before applying."}
    elif score >= 600:
        return {"band": "Poor", "color": "#FF5722", "message": "Poor credit. Focus on paying bills on time."}
    else:
        return {"band": "Very Poor", "color": "#F44336", "message": "Very poor credit. Avoid new credit applications."}

# ─────────────────────────────────────────────
# PREDICT CIBIL SCORE ENDPOINT
# POST /predict-cibil
#
# Flutter sends the 10 key questions answered by user.
# All other 32 features default to dataset medians.
#
# Request JSON:
# {
#   "age_oldest_tl": 72,          ← months (oldest credit account age)
#   "age_newest_tl": 18,          ← months (newest credit account age)
#   "time_since_recent_enq": 10,  ← months since last credit enquiry
#   "time_since_recent_payment": 30, ← days since last payment
#   "max_recent_level_of_deliq": 0,  ← 0=none, higher=worse
#   "recent_level_of_deliq": 0,      ← 0=none, higher=worse
#   "time_with_curr_empr": 24,    ← months with current employer
#   "num_std_12mts": 5,           ← active accounts in good standing
#   "enq_l3m": 1,                 ← credit enquiries in last 3 months
#   "netmonthlyincome": 50000     ← in INR
# }
#
# Response JSON:
# {
#   "cibil_score": 712,
#   "band": "Good",
#   "color": "#8BC34A",
#   "message": "Good credit. You'll get competitive rates.",
#   "improvement_tips": [...]
# }
# ─────────────────────────────────────────────
@app.route("/predict-cibil", methods=["POST"])
def predict_cibil():
    try:
        data = request.get_json(force=True)

        # Start with median defaults for all 42 features
        input_row = {feat: medians.get(feat, 0) for feat in features}

        # Map the 10 user-answered fields to their exact feature names
        user_field_map = {
            "age_oldest_tl":              "Age_Oldest_TL",
            "age_newest_tl":              "Age_Newest_TL",
            "time_since_recent_enq":      "time_since_recent_enq",
            "time_since_recent_payment":  "time_since_recent_payment",
            "max_recent_level_of_deliq":  "max_recent_level_of_deliq",
            "recent_level_of_deliq":      "recent_level_of_deliq",
            "time_with_curr_empr":        "Time_With_Curr_Empr",
            "num_std_12mts":              "num_std_12mts",
            "enq_l3m":                    "enq_L3m",
            "netmonthlyincome":           "NETMONTHLYINCOME",
        }

        # Override defaults with user-provided values
        for user_key, feature_name in user_field_map.items():
            if user_key in data and feature_name in input_row:
                input_row[feature_name] = float(data[user_key])

        # Handle categoricals (default to most common value via encoder)
        for col in cat_cols:
            le = encoders[col]
            input_row[col] = 0  # encoded default (first class)

        # Build feature vector in correct order
        feature_vector = np.array([[input_row[f] for f in features]])

        # Predict and clamp to valid CIBIL range
        raw_score = model.predict(feature_vector)[0]
        score = int(np.clip(raw_score, 300, 900))

        # Get improvement tips based on user inputs
        tips = []
        if data.get("enq_l3m", 0) > 2:
            tips.append("Reduce credit applications — too many enquiries lower your score.")
        if data.get("max_recent_level_of_deliq", 0) > 0:
            tips.append("Clear any overdue payments immediately.")
        if data.get("recent_level_of_deliq", 0) > 0:
            tips.append("Bring all active accounts to current status.")
        if data.get("netmonthlyincome", 0) < 20000:
            tips.append("A higher income-to-debt ratio improves your score.")
        if data.get("num_std_12mts", 0) < 3:
            tips.append("Maintain at least 3–4 accounts in good standing.")
        if not tips:
            tips.append("Keep maintaining on-time payments to sustain your score.")

        band_info = get_score_band(score)

        return jsonify({
            "cibil_score": score,
            "band": band_info["band"],
            "color": band_info["color"],
            "message": band_info["message"],
            "improvement_tips": tips
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# Background scheduler removed (Handled by CI/CD)
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# RUN (only if running this file standalone for testing)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 56)
    print("  FinSight Pro Analysis API")
    print("  Running on http://localhost:5050")
    print("  Auto-sync enabled: 6 AM & 6 PM IST")
    print("  Keep this window open while using the app!")
    print("=" * 56)
    app.run(host="0.0.0.0", port=5050, debug=False)
