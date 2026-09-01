"""
PRO MUTUAL FUND ANALYSIS & COMPARISON SYSTEM
─────────────────────────────────────────────
Data Sources:
  • mftool  – Indian mutual funds via AMFI scheme codes
  • yfinance – ETFs / global tickers (e.g. SPY, QQQ, ^NSEI)

Features:
  SIP · Lumpsum · SIP + Lumpsum
  Step-Up SIP · XIRR · CAGR · Absolute Return
  Sharpe · Sortino · Max Drawdown · Volatility
  Alpha · Beta · Expense-Ratio · Fund Category
"""

import warnings, sys, textwrap, io
warnings.filterwarnings("ignore")

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════════
# FINANCIAL METRICS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def xirr(cashflows):
    """Compute annualised IRR (%) for irregular cashflows using Newton–Raphson."""
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

    # Fallback: simple geometric approximation
    total_inv = sum(-c[1] for c in cashflows[:-1])
    final_val = cashflows[-1][1]
    years = (cashflows[-1][0] - t0).days / 365.25
    if total_inv <= 0 or years <= 0:
        return 0.0
    return ((final_val / total_inv) ** (1 / years) - 1) * 100


def compute_metrics(val_hist, inv_hist, dates, bench_rets=None, rf=0.065):
    """
    Compute a full dict of risk/return metrics.

    Parameters
    ----------
    val_hist   : list[float]  – daily portfolio value
    inv_hist   : list[float]  – cumulative invested amount each day
    dates      : list[datetime] – date for each observation
    bench_rets : np.array     – daily benchmark returns (optional)
    rf         : float        – annualised risk-free rate (RBI repo ≈ 6.5 %)

    Returns
    -------
    dict with keys: max_dd, volatility, sharpe, sortino, beta, alpha,
                    abs_return, cagr
    """
    v = np.asarray(val_hist, dtype=np.float64)
    inv = np.asarray(inv_hist, dtype=np.float64)
    n = len(v)

    out = dict(max_dd=0.0, volatility=0.0, sharpe=0.0, sortino=0.0,
               beta=0.0, alpha=0.0, abs_return=0.0, cagr=0.0)

    if n < 2 or inv[-1] <= 0:
        return out

    # --- Daily portfolio returns (adjusted for injections) ---
    prev = v[:-1]
    curr = v[1:]
    inj = np.diff(inv)
    safe = prev > 0
    safe_prev = np.where(prev == 0, 1, prev)
    rets = np.where(safe, (curr - inj) / safe_prev - 1, 0.0)

    # --- Absolute Return ---
    out["abs_return"] = ((v[-1] - inv[-1]) / inv[-1]) * 100

    # --- CAGR ---
    years = (dates[-1] - dates[0]).days / 365.25
    if years > 0 and inv[-1] > 0:
        out["cagr"] = ((v[-1] / inv[-1]) ** (1 / years) - 1) * 100

    # --- Volatility (annualised) ---
    std = np.std(rets, ddof=1)
    out["volatility"] = std * np.sqrt(252) * 100 if std > 0 else 0.0

    # --- Max Drawdown ---
    peak = np.maximum.accumulate(v)
    safe_peak = np.where(peak == 0, 1, peak)
    dd = np.where(peak > 0, (v / safe_peak) - 1, 0.0)
    out["max_dd"] = dd.min() * 100

    # --- Sharpe ---
    ann_ret = (1 + np.mean(rets)) ** 252 - 1
    excess = ann_ret - rf
    ann_std = std * np.sqrt(252) if std > 0 else 0.0
    out["sharpe"] = excess / ann_std if ann_std > 0 else 0.0

    # --- Sortino ---
    down = rets[rets < 0]
    down_std = np.std(down, ddof=1) if len(down) > 1 else 0.0
    ann_down = down_std * np.sqrt(252) if down_std > 0 else 0.0
    out["sortino"] = excess / ann_down if ann_down > 0 else 0.0

    # --- Alpha & Beta ---
    if bench_rets is not None:
        br = bench_rets[:len(rets)]
        if len(br) == len(rets) and np.var(br) > 0:
            cov = np.cov(rets, br)
            out["beta"] = cov[0, 1] / cov[1, 1]
            bench_ann = (1 + np.mean(br)) ** 252 - 1
            out["alpha"] = ((ann_ret - rf) - out["beta"] * (bench_ann - rf)) * 100

    return out


# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHERS
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_mftool(scheme_code: str, years: float):
    """Return (nav_df, meta_dict) using mftool for an AMFI scheme code."""
    from mftool import Mftool
    mf = Mftool()

    meta = mf.get_scheme_details(scheme_code)
    if not meta or "scheme_name" not in meta:
        return None, None

    raw = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
    if raw is None or raw.empty:
        return None, None

    df = raw.copy()
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df.index = pd.to_datetime(df.index, format="%d-%m-%Y", dayfirst=True)
    df = df.sort_index()
    df = df.dropna(subset=["nav"])
    df = df[~df.index.duplicated(keep="first")]

    # Trim to requested horizon + buffer
    cutoff = df.index.max() - timedelta(days=int(years * 365.25) + 60)
    df = df[df.index >= cutoff]

    return df[["nav"]].rename(columns={"nav": "Close"}), meta


def fetch_yfinance(ticker: str, years: float):
    """Return (price_df, meta_dict) using yfinance."""
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
        tk = yf.Ticker(ticker)
        info = tk.info or {}
    except Exception:
        pass

    meta = {
        "scheme_name": info.get("longName", ticker),
        "fund_house": info.get("fundFamily", "N/A"),
        "scheme_category": info.get("category", info.get("quoteType", "N/A")),
        "expense_ratio": info.get("annualReportExpenseRatio", None),
    }

    df = raw[["Close"]].copy().dropna()
    df = df[~df.index.duplicated(keep="first")]
    return df, meta


def search_schemes(keyword: str):
    """Search AMFI scheme database by keyword and return top results."""
    from mftool import Mftool
    mf = Mftool()
    matches = mf.get_available_schemes(keyword)
    if not matches:
        return {}
    return dict(list(matches.items())[:15])


def is_scheme_code(text: str) -> bool:
    """Check if the input looks like an AMFI numeric scheme code."""
    return text.strip().isdigit() and len(text.strip()) >= 5


# ═══════════════════════════════════════════════════════════════════════════════
# USER INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

SEP = "═" * 64

def banner(text):
    print(f"\n{SEP}")
    print(f"  {text}")
    print(SEP)


banner("PRO MUTUAL FUND ANALYSIS & COMPARISON SYSTEM")
print("  Data Sources : mftool (Indian MFs) + yfinance (ETFs / Global)")
print("  You can enter:")
print("    - Fund names       → e.g. 'HDFC flexi cap', 'SBI bluechip', 'quant small cap'")
print("    - AMFI codes       → e.g. 119597, 120503")
print("    - yfinance tickers → e.g. SPY, QQQ, ^NSEI")
print("    - 'search <keyword>' → e.g. 'search HDFC' to browse all matching funds\n")


def _do_search(keyword):
    """Search AMFI and display results. Returns list of scheme codes user selects."""
    print(f"\n  🔍 Searching AMFI for '{keyword}' …")
    matches = search_schemes(keyword)
    if not matches:
        print("  ⚠ No schemes found for that keyword.\n")
        return []
    items = list(matches.items())
    print(f"\n  {'#':<4} {'Code':<10} {'Scheme Name'}")
    print(f"  {'-'*60}")
    for i, (code, name) in enumerate(items, 1):
        print(f"  {i:<4} {code:<10} {name}")
    print()
    pick = input("  Enter the # numbers to select (e.g. 1,3,5) or press Enter to skip: ").strip()
    if not pick:
        return []
    selected = []
    for p in pick.split(","):
        p = p.strip()
        if p.isdigit():
            idx = int(p) - 1
            if 0 <= idx < len(items):
                selected.append(items[idx][0])  # scheme code
    return selected


def _is_fund_name(text):
    """Detect if input looks like a fund name (has letters, not a valid ticker pattern)."""
    t = text.strip()
    # Numeric = scheme code
    if t.isdigit():
        return False
    # Short uppercase with optional dots/^ = likely a yfinance ticker (e.g. SPY, ^NSEI, RELIANCE.NS)
    if len(t) <= 12 and t.replace(".", "").replace("^", "").replace("-", "").isalnum() and t == t.upper():
        return False
    # Everything else with spaces or mixed case = likely a fund name
    return True


# ── Collect assets ────────────────────────────────────────────────────────────
assets_input = input("1. Enter fund names, scheme codes, or tickers\n   (e.g. 'HDFC flexi cap, SBI bluechip' or '119597, 120503' or 'SPY, QQQ'): ").strip()

ASSET_KEYS = []

# Handle explicit 'search <keyword>' command
if assets_input.lower().startswith("search"):
    kw = assets_input[6:].strip()
    if kw:
        codes = _do_search(kw)
        ASSET_KEYS.extend(codes)
    # Allow user to enter more after search
    more = input("\n   Enter more fund names, codes, or tickers (or press Enter to continue): ").strip()
    if more:
        for entry in [s.strip() for s in more.split(",") if s.strip()]:
            if _is_fund_name(entry):
                codes = _do_search(entry)
                ASSET_KEYS.extend(codes)
            else:
                ASSET_KEYS.append(entry.strip())
else:
    # Split by comma and process each entry
    raw_entries = [s.strip() for s in assets_input.split(",") if s.strip()]

    if not raw_entries:
        ASSET_KEYS = ["119597", "120503"]
        print(f"  [!] No input. Using defaults: {ASSET_KEYS}")
    else:
        for entry in raw_entries:
            if _is_fund_name(entry):
                # Auto-search for this fund name
                codes = _do_search(entry)
                ASSET_KEYS.extend(codes)
            else:
                ASSET_KEYS.append(entry.strip())

if not ASSET_KEYS:
    ASSET_KEYS = ["119597", "120503"]
    print(f"  [!] No valid selections made. Using defaults: {ASSET_KEYS}")

# ── Investment mode ───────────────────────────────────────────────────────────
print("\n  Investment Modes:")
print("    1 → SIP        (invest a fixed amount every month)")
print("    2 → Lumpsum    (invest everything at once upfront)")
print("    3 → SIP + Lumpsum (combine both strategies)")
inv_mode = input("2. Choose your investment mode (e.g. 1 or 2 or 3) [default: 1]: ").strip() or "1"
inv_mode = int(inv_mode) if inv_mode in ("1", "2", "3") else 1

base_sip, step_up_pct, lumpsum_amt = 0.0, 0.0, 0.0

if inv_mode in (1, 3):
    try:
        base_sip = float(input("3. Monthly SIP amount in Rupees (e.g. 5000 or 10000) [default: 10000]: ").strip() or "10000")
    except ValueError:
        base_sip = 10000.0
    try:
        step_up_pct = float(input("4. Annual step-up percentage (e.g. 10 means SIP increases 10% every year) [default: 10]: ").strip() or "10")
    except ValueError:
        step_up_pct = 10.0

if inv_mode in (2, 3):
    try:
        lumpsum_amt = float(input("5. One-time lumpsum amount in Rupees (e.g. 100000 or 500000) [default: 100000]: ").strip() or "100000")
    except ValueError:
        lumpsum_amt = 100000.0

try:
    TARGET_YEARS = float(input("6. How many years to backtest? (e.g. 3 or 5 or 10) [default: 5]: ").strip() or "5")
except ValueError:
    TARGET_YEARS = 5.0

try:
    FUTURE_YEARS = float(input("7. How many years into the future do you want to project? (e.g. 5, 10, 15) [default: 10]: ").strip() or "10")
except ValueError:
    FUTURE_YEARS = 10.0

MODE_LABEL = {1: "SIP", 2: "Lumpsum", 3: "SIP + Lumpsum"}[inv_mode]

banner("CONFIGURATION SUMMARY")
print(f"  Assets     : {', '.join(ASSET_KEYS)}")
print(f"  Mode       : {MODE_LABEL}")
if inv_mode in (1, 3):
    print(f"  SIP        : ₹{base_sip:,.0f}/month  (step-up {step_up_pct}% every year)")
if inv_mode in (2, 3):
    print(f"  Lumpsum    : ₹{lumpsum_amt:,.0f} (one-time)")
print(f"  Horizon    : {TARGET_YEARS} years")
print(f"  Future Proj: {FUTURE_YEARS} years")
print(f"  Risk-Free  : 6.50% (RBI Repo Rate benchmark)")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════

banner("DOWNLOADING DATA")

nav_data = {}      # key → DataFrame with 'Close' column, DatetimeIndex
meta_data = {}     # key → dict with scheme_name, fund_house, etc.
labels = {}        # key → short display name

for key in ASSET_KEYS:
    if is_scheme_code(key):
        print(f"  📡 [{key}] Fetching from mftool (AMFI) …", end=" ")
        df, meta = fetch_mftool(key, TARGET_YEARS)
        source = "mftool"
    else:
        key_upper = key.upper()
        print(f"  📡 [{key_upper}] Fetching from yfinance …", end=" ")
        df, meta = fetch_yfinance(key_upper, TARGET_YEARS)
        key = key_upper
        source = "yfinance"

    if df is None or df.empty or len(df) < 60:
        print(f"⚠ FAILED / insufficient data. Skipping.")
        continue

    nav_data[key] = df
    meta_data[key] = meta or {}

    name = (meta or {}).get("scheme_name", key)
    # Truncate long MF names for display
    labels[key] = (name[:45] + "…") if len(name) > 45 else name

    print(f"✓ {len(df)} days | {labels[key]}")

ASSET_KEYS = list(nav_data.keys())
if not ASSET_KEYS:
    print("\n❌ No valid data. Exiting.")
    sys.exit(1)

# Align to common date range
common_idx = nav_data[ASSET_KEYS[0]].index
for k in ASSET_KEYS[1:]:
    common_idx = common_idx.intersection(nav_data[k].index)

for k in ASSET_KEYS:
    nav_data[k] = nav_data[k].loc[common_idx]

TARGET_DAYS = int(TARGET_YEARS * 252)
TEST_SIZE = min(TARGET_DAYS, len(common_idx))
ACTUAL_YEARS = TEST_SIZE / 252

start_date = common_idx[-TEST_SIZE]
end_date = common_idx[-1]

print(f"\n  📅 Common trading days : {TEST_SIZE} (~{ACTUAL_YEARS:.1f} years)")
print(f"  📅 Backtest period     : {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')}")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTEST SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

banner("RUNNING SIMULATIONS")

SIP_INTERVAL = 21  # ~monthly in trading days
results = {}
all_dates = None

# Benchmark: first asset's raw returns for Alpha/Beta
bench_key = ASSET_KEYS[0]
bench_prices = nav_data[bench_key]["Close"].iloc[-TEST_SIZE:].values.astype(float)
bench_rets = np.diff(bench_prices) / bench_prices[:-1]

for key in ASSET_KEYS:
    prices = nav_data[key]["Close"].iloc[-TEST_SIZE:].values.astype(float)
    dates = nav_data[key].index[-TEST_SIZE:].tolist()
    all_dates = dates  # save for plotting

    n = len(prices)
    units = 0.0
    invested = 0.0
    cashflows = []
    val_hist, inv_hist = [], []
    days_since_sip = 0
    months = 0
    sip_amt = base_sip

    for i in range(n):
        price = prices[i]
        dt = dates[i]

        # Lumpsum on Day 0
        if i == 0 and lumpsum_amt > 0:
            units += lumpsum_amt / price
            invested += lumpsum_amt
            cashflows.append((dt, -lumpsum_amt))

        # SIP
        if base_sip > 0:
            days_since_sip += 1
            if days_since_sip >= SIP_INTERVAL:
                days_since_sip = 0
                months += 1
                if months > 0 and months % 12 == 0:
                    sip_amt *= (1 + step_up_pct / 100)
                units += sip_amt / price
                invested += sip_amt
                cashflows.append((dt, -sip_amt))

        val_hist.append(units * price)
        inv_hist.append(invested)

    final_val = val_hist[-1]
    cashflows.append((dates[-1], final_val))

    xirr_val = xirr(cashflows)
    m = compute_metrics(val_hist, inv_hist, dates, bench_rets)

    # Expense ratio from meta
    er = meta_data.get(key, {}).get("expense_ratio", None)
    er_str = f"{er*100:.2f}%" if er else "N/A"

    category = meta_data.get(key, {}).get("scheme_category", "N/A")
    fund_house = meta_data.get(key, {}).get("fund_house", "N/A")

    # ── Future Projection Simulation ──
    cagr_pct = m["cagr"]
    future_months = int(FUTURE_YEARS * 12)
    monthly_rate = (1 + cagr_pct/100)**(1/12) - 1 if cagr_pct > 0 else 0
    
    f_val = lumpsum_amt if lumpsum_amt > 0 else 0.0
    f_inv = f_val
    f_sip_amt = base_sip
    
    future_val_hist = [f_val]
    
    for fm in range(1, future_months + 1):
        f_val = f_val * (1 + monthly_rate)
        if base_sip > 0:
            if fm > 1 and (fm - 1) % 12 == 0:
                f_sip_amt *= (1 + step_up_pct / 100)
            f_val += f_sip_amt
            f_inv += f_sip_amt
        future_val_hist.append(f_val)

    results[key] = {
        "Key": key,
        "Name": labels.get(key, key),
        "Fund House": fund_house,
        "Category": category,
        "Expense Ratio": er_str,
        "Start Date": start_date.strftime("%d-%b-%Y"),
        "End Date": end_date.strftime("%d-%b-%Y"),
        "Duration": f"{ACTUAL_YEARS:.1f} years",
        "Invested": invested,
        "Final Value": final_val,
        "Wealth Gain": final_val - invested,
        "Absolute Return (%)": round(m["abs_return"], 2),
        "CAGR (%)": round(m["cagr"], 2),
        "XIRR (%)": round(xirr_val, 2),
        "Max Drawdown (%)": round(m["max_dd"], 2),
        "Volatility (%)": round(m["volatility"], 2),
        "Sharpe Ratio": round(m["sharpe"], 2),
        "Sortino Ratio": round(m["sortino"], 2),
        "Beta": round(m["beta"], 2),
        "Alpha (%)": round(m["alpha"], 2),
        "val_hist": val_hist,
        "Future Invested": f_inv,
        "Future Value": f_val,
        "Future Wealth Gain": f_val - f_inv,
        "future_val_hist": future_val_hist,
    }

    print(f"  ✓ {labels.get(key, key)}")


# ═══════════════════════════════════════════════════════════════════════════════
# RANKING & OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

banner("RESULTS & RANKING")

df_res = pd.DataFrame(results.values())

# Composite rank: 40% XIRR + 30% Sharpe + 20% Sortino + 10% Max DD (less negative = better)
for col, asc in [("XIRR (%)", False), ("Sharpe Ratio", False),
                 ("Sortino Ratio", False), ("Max Drawdown (%)", False)]:
    df_res[f"_r_{col}"] = df_res[col].rank(ascending=asc)

df_res["_score"] = (df_res["_r_XIRR (%)"] * 0.4 +
                    df_res["_r_Sharpe Ratio"] * 0.3 +
                    df_res["_r_Sortino Ratio"] * 0.2 +
                    df_res["_r_Max Drawdown (%)"] * 0.1)

df_res = df_res.sort_values("_score").reset_index(drop=True)

# Print detailed cards
for idx, row in df_res.iterrows():
    rank = idx + 1
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")

    print(f"\n  {medal}  {row['Name']}")
    print(f"  {'─'*58}")
    print(f"  Fund House       : {row['Fund House']}")
    print(f"  Category         : {row['Category']}")
    print(f"  Expense Ratio    : {row['Expense Ratio']}")
    print(f"  Period           : {row['Start Date']} to {row['End Date']} ({row['Duration']})")
    print(f"  ────────────────────────────────────────────────────────")
    print(f"  Total Invested   : ₹{row['Invested']:>14,.2f}")
    print(f"  Current Value    : ₹{row['Final Value']:>14,.2f}")
    print(f"  Wealth Gained    : ₹{row['Wealth Gain']:>14,.2f}")
    print(f"  ────────────────────────────────────────────────────────")
    print(f"  Absolute Return  : {row['Absolute Return (%)']:>8.2f} %")
    if inv_mode in (2, 3):
        print(f"  CAGR             : {row['CAGR (%)']:>8.2f} %")
    print(f"  XIRR             : {row['XIRR (%)']:>8.2f} %")
    print(f"  ────────────────────────────────────────────────────────")
    print(f"  Max Drawdown     : {row['Max Drawdown (%)']:>8.2f} %")
    print(f"  Volatility (Ann.): {row['Volatility (%)']:>8.2f} %")
    print(f"  Sharpe Ratio     : {row['Sharpe Ratio']:>8.2f}")
    print(f"  Sortino Ratio    : {row['Sortino Ratio']:>8.2f}")
    print(f"  Beta             : {row['Beta']:>8.2f}  (vs {labels.get(bench_key, bench_key)})")
    print(f"  Alpha            : {row['Alpha (%)']:>8.2f} %")
    print(f"  ────────────────────────────────────────────────────────")
    print(f"  🔮 FUTURE PREDICTION (in {FUTURE_YEARS} years)")
    print(f"  Expected CAGR    : {row['CAGR (%)']:>8.2f} % (Based on past)")
    print(f"  Future Invested  : ₹{row['Future Invested']:>14,.2f}")
    print(f"  Future Value     : ₹{row['Future Value']:>14,.2f}")
    print(f"  Future Wealth    : ₹{row['Future Wealth Gain']:>14,.2f}")

# Summary table
print(f"\n{'─'*64}")
print(f"  {'Rank':<5} {'XIRR':>7} {'Sharpe':>7} {'Sortino':>8} {'Max DD':>8}  Name")
print(f"  {'─'*58}")
for idx, row in df_res.iterrows():
    print(f"  {idx+1:<5} {row['XIRR (%)']:>6.1f}% {row['Sharpe Ratio']:>7.2f} {row['Sortino Ratio']:>8.2f} {row['Max Drawdown (%)']:>7.1f}%  {row['Name'][:30]}")

best = df_res.iloc[0]
print(f"\n  🏆 BEST PICK → {best['Name']}")
print(f"     XIRR {best['XIRR (%)']}% | Sharpe {best['Sharpe Ratio']} | Max DD {best['Max Drawdown (%)']}%")


# ═══════════════════════════════════════════════════════════════════════════════
# PLOTTING
# ═══════════════════════════════════════════════════════════════════════════════

DARK_BG  = "#0d1117"
CARD_BG  = "#161b22"
MUTED    = "#8b949e"
GRID_CLR = "#21262d"
TEXT_CLR = "#e6edf3"
PALETTE  = ["#58a6ff", "#f78166", "#3fb950", "#d2a8ff",
            "#ff7b72", "#79c0ff", "#ffa657", "#7ee787"]

plt.rcParams.update({
    "figure.facecolor": DARK_BG, "axes.facecolor": CARD_BG,
    "axes.edgecolor": GRID_CLR, "axes.labelcolor": TEXT_CLR,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": TEXT_CLR, "grid.color": GRID_CLR,
    "grid.alpha": 0.5, "font.family": "monospace",
})

fig, axes = plt.subplots(3, 1, figsize=(18, 18), facecolor=DARK_BG,
                         gridspec_kw={"height_ratios": [3, 1, 3], "hspace": 0.3})

def format_currency(x, _):
    if x >= 10000000:
        return f"₹{x/10000000:,.2f}Cr"
    elif x >= 100000:
        return f"₹{x/100000:,.1f}L"
    else:
        return f"₹{x:,.0f}"

# ── Panel 1: Portfolio Value ──────────────────────────────────────────────────
ax1 = axes[0]
for i, key in enumerate(df_res["Key"]):
    vals = results[key]["val_hist"]
    color = PALETTE[i % len(PALETTE)]
    is_best = (key == best["Key"])
    lbl = f"{'★ ' if is_best else ''}{labels.get(key, key)} (XIRR {results[key]['XIRR (%)']:.1f}%)"
    ax1.plot(all_dates, vals, linewidth=3 if is_best else 1.5,
             alpha=1.0 if is_best else 0.7, color=color, label=lbl)

# Investment line
inv_line = [results[df_res.iloc[0]["Key"]]["val_hist"][0]]  # approx
inv_hist_plot = results[df_res.iloc[0]["Key"]]
# Use first asset's invested history for reference
first_key = df_res.iloc[0]["Key"]
ax1.fill_between(all_dates,
                 [0]*len(all_dates),
                 [results[first_key]["val_hist"][j] for j in range(len(all_dates))],
                 alpha=0.03, color=PALETTE[0])

ax1.set_title(f"Portfolio Value Growth  |  {MODE_LABEL}  |  ~{ACTUAL_YEARS:.1f} Years",
              color=TEXT_CLR, fontsize=15, fontweight="bold", pad=12)
ax1.set_ylabel("Portfolio Value (₹)", fontsize=11)
ax1.legend(framealpha=0.15, loc="upper left", fontsize=9, ncol=1)
ax1.grid(True, axis="both")
ax1.yaxis.set_major_formatter(plt.FuncFormatter(format_currency))

# ── Panel 2: Drawdown ────────────────────────────────────────────────────────
ax2 = axes[1]
for i, key in enumerate(df_res["Key"]):
    vals = np.asarray(results[key]["val_hist"])
    peak = np.maximum.accumulate(vals)
    dd = ((vals / peak) - 1) * 100
    color = PALETTE[i % len(PALETTE)]
    ax2.fill_between(all_dates, dd, 0, alpha=0.25, color=color)
    ax2.plot(all_dates, dd, linewidth=1, alpha=0.8, color=color,
             label=labels.get(key, key))

ax2.set_title("Drawdown from Peak (%)", color=TEXT_CLR, fontsize=12, pad=8)
ax2.set_ylabel("Drawdown %", fontsize=10)
ax2.legend(framealpha=0.15, loc="lower left", fontsize=8, ncol=2)
ax2.grid(True, axis="both")

# ── Panel 3: Future Wealth Prediction ────────────────────────────────────────
ax3 = axes[2]
future_months = int(FUTURE_YEARS * 12)
future_dates = [datetime.today() + timedelta(days=30.436875 * i) for i in range(future_months + 1)]

for i, key in enumerate(df_res["Key"]):
    f_vals = results[key]["future_val_hist"]
    color = PALETTE[i % len(PALETTE)]
    is_best = (key == best["Key"])
    lbl = f"{'★ ' if is_best else ''}{labels.get(key, key)} (CAGR {results[key]['CAGR (%)']:.1f}%)"
    ax3.plot(future_dates, f_vals, linewidth=3 if is_best else 1.5,
             alpha=1.0 if is_best else 0.7, color=color, label=lbl)

ax3.set_title(f"🔮 Future Wealth Prediction  |  Next {FUTURE_YEARS} Years",
              color=TEXT_CLR, fontsize=15, fontweight="bold", pad=12)
ax3.set_ylabel("Predicted Value (₹)", fontsize=11)
ax3.legend(framealpha=0.15, loc="upper left", fontsize=9, ncol=1)
ax3.grid(True, axis="both")
ax3.yaxis.set_major_formatter(plt.FuncFormatter(format_currency))

outpath = "mf_comparison.png"
plt.savefig(outpath, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
plt.close()

print(f"\n  ✅ Dashboard saved → {outpath}")
print(SEP)
