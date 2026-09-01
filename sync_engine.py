import pandas as pd
import requests
from datetime import datetime, timedelta
import yfinance as yf
from mftool import Mftool
import numpy as np
import warnings

warnings.filterwarnings("ignore")

def get_amfi_bulk_chunk(end_dt):
    """Fetches the AMFI bulk NAV data for a 7-day period ending on end_dt."""
    start_dt = end_dt - timedelta(days=7)
    url = f"https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt={start_dt.strftime('%d-%b-%Y')}&todt={end_dt.strftime('%d-%b-%Y')}"
    print(f"Fetching AMFI chunk for {end_dt.strftime('%Y-%m-%d')}...")
    
    try:
        res = requests.get(url, timeout=30)
        lines = res.text.split("\n")
        data = []
        for line in lines:
            parts = line.split(";")
            if len(parts) >= 8 and parts[0].isdigit():
                try:
                    nav = float(parts[4])
                    data.append({
                        "AMFI Code": parts[0].strip(),
                        "Fund Name": parts[1].strip(),
                        "nav": nav,
                        "date": parts[7].strip()
                    })
                except ValueError:
                    pass
                    
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y")
        df = df.sort_values("date")
        latest = df.groupby("AMFI Code").last().reset_index()
        return latest
    except Exception as e:
        print(f"Error fetching chunk: {e}")
        return pd.DataFrame()

def categorize(name):
    name = name.lower()
    if "liquid" in name or "debt" in name or "bond" in name or "gilt" in name or "money market" in name or "overnight" in name: 
        return "Debt"
    if "small cap" in name or "smallcap" in name: return "Small Cap"
    if "mid cap" in name or "midcap" in name or "mid" in name: return "Mid Cap"
    if "flexi" in name or "multi" in name: return "Flexi Cap"
    if "large" in name or "bluechip" in name or "nifty" in name or "sensex" in name or "top 100" in name: return "Index / Large Cap"
    if "tax" in name or "elss" in name: return "ELSS (Tax Saving)"
    return "Other Equity"

def calculate_risk_score(navs):
    rets = navs.pct_change().dropna()
    if len(rets) < 50: return 5 # Default medium risk if not enough data
    ann_std = rets.std() * np.sqrt(252)
    # Map annualized volatility to a 1-10 score. 
    # E.g., 0-35% volatility mapped to 1-10 scale.
    score = round((ann_std * 100) / 3.5)
    return max(1, min(10, int(score)))

def main():
    today = datetime.today()
    
    # 1. Fetch bulk datasets
    df_now = get_amfi_bulk_chunk(today)
    df_1y = get_amfi_bulk_chunk(today - timedelta(days=365))
    df_3y = get_amfi_bulk_chunk(today - timedelta(days=3*365))
    df_5y = get_amfi_bulk_chunk(today - timedelta(days=5*365))
    
    if df_now.empty or df_1y.empty or df_3y.empty:
        print("Failed to fetch critical AMFI data. Exiting.")
        return
        
    print(f"Total funds found today: {len(df_now)}")
    
    # 2. Merge Data
    df = df_now[["AMFI Code", "Fund Name", "nav"]].rename(columns={"nav": "nav_now"})
    df = df.merge(df_1y[["AMFI Code", "nav"]].rename(columns={"nav": "nav_1y"}), on="AMFI Code", how="left")
    df = df.merge(df_3y[["AMFI Code", "nav"]].rename(columns={"nav": "nav_3y"}), on="AMFI Code", how="left")
    df = df.merge(df_5y[["AMFI Code", "nav"]].rename(columns={"nav": "nav_5y"}), on="AMFI Code", how="left")
    
    # 3. Compute CAGR
    df["1Y CAGR (%)"] = ((df["nav_now"] / df["nav_1y"]) - 1) * 100
    df["3Y CAGR (%)"] = ((df["nav_now"] / df["nav_3y"]) ** (1/3) - 1) * 100
    df["5Y CAGR (%)"] = ((df["nav_now"] / df["nav_5y"]) ** (1/5) - 1) * 100
    
    # 4. Filter for Direct Growth Equity
    df = df[
        df["Fund Name"].str.contains("Direct", case=False, na=False) &
        df["Fund Name"].str.contains("Growth", case=False, na=False) &
        ~df["Fund Name"].str.contains("IDCW", case=False, na=False) &
        ~df["Fund Name"].str.contains("Dividend", case=False, na=False)
    ]
    
    df["Category"] = df["Fund Name"].apply(categorize)
    df = df[df["Category"] != "Debt"]
    
    df = df.dropna(subset=["3Y CAGR (%)"])
    
    # 5. Take Top 50 funds from EACH category
    print(f"Filtered down to {len(df)} Equity Direct Growth funds. Selecting Top 50 by 3Y CAGR per category...")
    top_funds_list = []
    for cat in df["Category"].unique():
        cat_df = df[df["Category"] == cat].sort_values("3Y CAGR (%)", ascending=False).head(50)
        top_funds_list.append(cat_df)
    
    top_domestic = pd.concat(top_funds_list).copy()
    print(f"Selected a balanced universe of {len(top_domestic)} domestic funds across all categories.")
    
    # 6. Deep Dive: Fetch history to calculate Risk Score
    mf = Mftool()
    risk_scores = []
    print(f"Fetching 3Y historical timeseries for {len(top_domestic)} funds to compute Risk Score...")
    for i, code in enumerate(top_domestic["AMFI Code"]):
        if i % 25 == 0:
            print(f"  ...processed {i}/{len(top_domestic)}")
        try:
            hist = mf.get_scheme_historical_nav(code, as_Dataframe=True)
            if hist is not None and not hist.empty:
                hist["nav"] = pd.to_numeric(hist["nav"], errors="coerce")
                hist.index = pd.to_datetime(hist.index, format="%d-%m-%Y", dayfirst=True)
                hist = hist.sort_index().dropna()
                score = calculate_risk_score(hist["nav"])
                risk_scores.append(score)
            else:
                risk_scores.append(5)
        except:
            risk_scores.append(5)
    
    top_domestic["Risk Score"] = risk_scores
    
    # Shorten names
    top_domestic["Fund Name"] = top_domestic["Fund Name"].apply(lambda x: x.split('-')[0].strip())
    
    # 7. Add International ETFs
    international_tickers = {
        "SPY": "SPDR S&P 500 ETF", "QQQ": "Invesco Nasdaq 100 ETF", "VT": "Vanguard Total World Stock", 
        "VXUS": "Vanguard Total Intl Stock", "EFA": "iShares MSCI EAFE ETF", "VOO": "Vanguard S&P 500 ETF", 
        "IVV": "iShares Core S&P 500 ETF", "VTI": "Vanguard Total Stock Market", "VUG": "Vanguard Growth ETF", 
        "VTV": "Vanguard Value ETF", "SCHD": "Schwab US Dividend Equity", "IWM": "iShares Russell 2000 ETF", 
        "IJH": "iShares Core S&P Mid-Cap", "VEA": "Vanguard Developed Markets", "VWO": "Vanguard Emerging Markets", 
        "IEMG": "iShares Core MSCI Emerging", "AGG": "iShares Core US Aggregate Bond", "GLD": "SPDR Gold Shares", 
        "SLV": "iShares Silver Trust", "SMH": "VanEck Semiconductor ETF", "ARKK": "ARK Innovation ETF", 
        "XLK": "Technology Select Sector SPDR", "XLV": "Health Care Select Sector SPDR", "XLF": "Financial Select Sector SPDR", 
        "XLE": "Energy Select Sector SPDR", "VNQ": "Vanguard Real Estate ETF", "INDA": "iShares MSCI India ETF", 
        "MCHI": "iShares MSCI China ETF", "EWJ": "iShares MSCI Japan ETF", "EWZ": "iShares MSCI Brazil ETF", 
        "EZU": "iShares MSCI Eurozone ETF", "VGK": "Vanguard FTSE Europe ETF", "URA": "Global X Uranium ETF", 
        "TAN": "Invesco Solar ETF", "LIT": "Global X Lithium & Battery ETF", "KWEB": "KraneShares China Internet", 
        "URTH": "iShares MSCI World ETF", "EWY": "iShares MSCI South Korea ETF", "EWT": "iShares MSCI Taiwan ETF", 
        "EWW": "iShares MSCI Mexico ETF", "EWC": "iShares MSCI Canada ETF", "EWA": "iShares MSCI Australia ETF", 
        "EWS": "iShares MSCI Singapore ETF", "EZA": "iShares MSCI South Africa ETF", "ILF": "iShares Latin America 40 ETF", 
        "IXUS": "iShares Core MSCI Total Intl", "ACWI": "iShares MSCI ACWI ETF", "CWI": "SPDR MSCI ACWI ex-US ETF", 
        "SPDW": "SPDR Portfolio Developed World", "SPEM": "SPDR Portfolio Emerging Markets", "SCHF": "Schwab Intl Equity ETF", 
        "SCHE": "Schwab Emerging Markets Equity", "VIGI": "Vanguard Intl Div Apprec", "VYMI": "Vanguard Intl High Div Yield", 
        "VIG": "Vanguard Dividend Appreciation ETF", "VYM": "Vanguard High Dividend Yield ETF", "SCHG": "Schwab US Large-Cap Growth ETF", 
        "IWD": "iShares Russell 1000 Value ETF", "IWF": "iShares Russell 1000 Growth ETF", "IWN": "iShares Russell 2000 Value ETF", 
        "IWO": "iShares Russell 2000 Growth ETF", "VBR": "Vanguard Small-Cap Value ETF", "VB": "Vanguard Small-Cap ETF", 
        "VO": "Vanguard Mid-Cap ETF", "XBI": "SPDR S&P Biotech ETF", "IBB": "iShares Biotechnology ETF", "KRE": "SPDR S&P Regional Banking ETF", 
        "XRT": "SPDR S&P Retail ETF", "ITB": "iShares U.S. Home Construction ETF", "XHB": "SPDR S&P Homebuilders ETF", 
        "IDU": "iShares U.S. Utilities ETF", "PFF": "iShares Preferred and Income Sec ETF", "EMB": "iShares J.P. Morgan USD Emerging Mkts", 
        "LQD": "iShares iBoxx USD Investment Grade", "HYG": "iShares iBoxx USD High Yield Corp Bond", "JNK": "SPDR Bloomberg High Yield Bond ETF", 
        "SHY": "iShares 1-3 Year Treasury Bond ETF", "IEF": "iShares 7-10 Year Treasury Bond ETF", "TLT": "iShares 20+ Year Treasury Bond ETF", 
        "MUB": "iShares National Muni Bond ETF", "TIP": "iShares TIPS Bond ETF", "MTUM": "iShares MSCI USA Momentum Factor ETF", 
        "USMV": "iShares MSCI USA Min Vol Factor ETF", "QUAL": "iShares MSCI USA Quality Factor ETF", "VLUE": "iShares MSCI USA Value Factor ETF", 
        "SIZE": "iShares MSCI USA Size Factor ETF", "ICLN": "iShares Global Clean Energy ETF", "PBW": "Invesco WilderHill Clean Energy ETF", 
        "FAN": "First Trust Global Wind Energy ETF", "CPER": "US Copper Index Fund", "SLX": "VanEck Steel ETF", "COPX": "Global X Copper Miners ETF"
    }
    
    print("Fetching International ETFs data...")
    cutoff = today - timedelta(days=5*365 + 30)
    int_results = []
    
    try:
        raw_yf = yf.download(list(international_tickers.keys()), start=cutoff.strftime("%Y-%m-%d"), progress=False)
        if not raw_yf.empty:
            if isinstance(raw_yf.columns, pd.MultiIndex):
                closes = raw_yf["Close"].copy()
            else:
                closes = raw_yf.copy()
            closes.index = pd.to_datetime(closes.index).tz_localize(None)
            
            for ticker, desc_name in international_tickers.items():
                if ticker in closes.columns:
                    series = closes[ticker].dropna()
                    if series.empty: continue
                    
                    def get_cagr_yf(years):
                        start_dt = series.index[-1] - timedelta(days=int(years * 365.25))
                        valid = series[series.index <= start_dt]
                        if valid.empty: return None
                        return ((series.iloc[-1] / valid.iloc[-1]) ** (1/years) - 1) * 100
                    
                    int_results.append({
                        "AMFI Code": ticker,
                        "Fund Name": desc_name,
                        "Category": "International",
                        "1Y CAGR (%)": get_cagr_yf(1),
                        "3Y CAGR (%)": get_cagr_yf(3),
                        "5Y CAGR (%)": get_cagr_yf(5),
                        "Risk Score": calculate_risk_score(series)
                    })
    except Exception as e:
        print(f"Error fetching international: {e}")
        
    df_int = pd.DataFrame(int_results)
    
    # 8. Combine and Score
    final_df = pd.concat([top_domestic, df_int], ignore_index=True)
    
    # Lower Risk Score is better. We'll give CAGR positive weight, Risk Score negative weight.
    final_df["Score"] = final_df["3Y CAGR (%)"].fillna(0) * 0.6 - (final_df["Risk Score"].fillna(5) * 2) * 0.4
    final_df = final_df.sort_values("Score", ascending=False)
    
    cols = ["AMFI Code", "Fund Name", "Category", "1Y CAGR (%)", "3Y CAGR (%)", "5Y CAGR (%)", "Risk Score", "Score"]
    final_df = final_df[cols]
    
    csv_path = "master_funds_database.csv"
    final_df.to_csv(csv_path, index=False)
    
    with open("last_sync.txt", "w") as f:
        f.write(datetime.now().strftime("%d-%b-%Y %I:%M %p") + " IST")
        
    print(f"Success! Master database saved to {csv_path} with {len(final_df)} top-tier assets.")

if __name__ == "__main__":
    main()
