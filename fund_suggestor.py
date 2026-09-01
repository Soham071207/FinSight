import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

# Streamlit Page Config
st.set_page_config(
    page_title="Live Mutual Fund Suggestor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark aesthetic
st.markdown("""
<style>
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #58a6ff;
    }
    .fund-name {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 Live Mutual Fund Suggestor")
st.markdown("""
This dashboard automatically analyzes the absolute best funds out of **10,000+** available in India, plus top global ETFs. 
**Data is synced daily via the background engine.** 
Find the best funds here, note their **AMFI Code**, and use `mutual_2.py` for long-term wealth prediction!
""")

import os

@st.cache_data(ttl=300)
def load_data():
    csv_path = "master_funds_database.csv"
    txt_path = "last_sync.txt"
    
    if not os.path.exists(csv_path):
        return pd.DataFrame(), "Never"
        
    df = pd.read_csv(csv_path)
    
    try:
        with open(txt_path, "r") as f:
            last_sync = f.read().strip()
    except:
        last_sync = "Unknown"
        
    return df, last_sync

# ── Application UI ──

with st.spinner("Loading master funds database..."):
    df_funds, last_refreshed = load_data()

st.sidebar.markdown(f"🕒 **Last Sync:** `{last_refreshed}`")
st.sidebar.write("---")

if df_funds.empty:
    st.error("Database not found! Please run `python sync_engine.py` in your terminal to download the bulk historical data.")
    st.stop()

# Sidebar Filters
st.sidebar.header("Filters")
categories = ["All"] + list(df_funds["Category"].unique())
selected_cat = st.sidebar.selectbox("Filter by Category", categories)

sort_options = [
    "3Y CAGR (High to Low)", 
    "5Y CAGR (High to Low)", 
    "Risk Score (Low to High) - Safest First", 
    "Risk Score (High to Low) - Most Aggressive"
]
sort_by = st.sidebar.selectbox("Sort By", sort_options)

if selected_cat != "All":
    df_display = df_funds[df_funds["Category"] == selected_cat].copy()
else:
    df_display = df_funds.copy()

if sort_by == "3Y CAGR (High to Low)":
    df_display = df_display.sort_values("3Y CAGR (%)", ascending=False)
elif sort_by == "5Y CAGR (High to Low)":
    df_display = df_display.sort_values("5Y CAGR (%)", ascending=False)
elif sort_by == "Risk Score (Low to High) - Safest First":
    df_display = df_display.sort_values("Risk Score", ascending=True)
elif sort_by == "Risk Score (High to Low) - Most Aggressive":
    df_display = df_display.sort_values("Risk Score", ascending=False)

# ── Top Picks Section ──
st.subheader("Top Recommended Domestic Funds")
st.markdown("Sorted by your selected preference above. Use the **AMFI Code** in `mutual_2.py` for long-term prediction.")

top_funds = df_display[df_display["Category"] != "International"].head(4)
cols = st.columns(4)

for i, (_, row) in enumerate(top_funds.iterrows()):
    with cols[i]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="fund-name">{row['Fund Name']}</div>
            <div style="font-size: 12px; color: #8b949e; margin-bottom: 10px;">Code: {row['AMFI Code']} | {row['Category']}</div>
            <div class="metric-value">{row['3Y CAGR (%)']:.1f}%</div>
            <div style="font-size: 12px; color: #8b949e;">3-Year CAGR</div>
            <div style="margin-top: 10px; font-size: 14px;">Risk Score: <b>{int(row.get('Risk Score', 5))}/10</b></div>
        </div>
        """, unsafe_allow_html=True)

st.write("---")

top_int = df_display[df_display["Category"] == "International"].head(4)
if not top_int.empty:
    st.subheader("🌍 Top Recommended International ETFs")
    cols_int = st.columns(min(len(top_int), 4))
    for i, (_, row) in enumerate(top_int.iterrows()):
        if i >= 4: break
        with cols_int[i]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="fund-name">{row['Fund Name']}</div>
                <div style="font-size: 12px; color: #8b949e; margin-bottom: 10px;">Ticker: {row['AMFI Code']} | {row['Category']}</div>
                <div class="metric-value">{row['3Y CAGR (%)']:.1f}%</div>
                <div style="font-size: 12px; color: #8b949e;">3-Year CAGR</div>
                <div style="margin-top: 10px; font-size: 14px;">Risk Score: <b>{int(row.get('Risk Score', 5))}/10</b></div>
            </div>
            """, unsafe_allow_html=True)
    st.write("---")

# Separate Domestic and International
df_domestic = df_display[df_display["Category"] != "International"]
df_international = df_display[df_display["Category"] == "International"]

# ── Detailed Data Table ──
st.subheader("📊 Domestic Fund Analysis")
st.markdown("Click on any column header to sort. Use the **AMFI Code** in `mutual_2.py` for backtesting and future projection.")

# Format columns for display
if not df_domestic.empty:
    df_dom_format = df_domestic.copy()
    for col in ["1Y CAGR (%)", "3Y CAGR (%)", "5Y CAGR (%)"]:
        df_dom_format[col] = df_dom_format[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A")
    
    if "Risk Score" in df_dom_format.columns:
        df_dom_format["Risk Score"] = df_dom_format["Risk Score"].apply(lambda x: f"{int(x)}/10" if pd.notnull(x) else "N/A")
    elif "Sharpe Ratio" in df_dom_format.columns:
        df_dom_format = df_dom_format.rename(columns={"Sharpe Ratio": "Risk Score (Pending Sync)"})

    st.dataframe(
        df_dom_format.set_index("AMFI Code"),
        width="stretch",
        height=400
    )
else:
    st.info("No domestic funds matched the current filter.")

st.write("---")

# ── International Funds Section ──
st.subheader("🌍 International Mutual Funds")
st.markdown("Diversify your portfolio by investing globally. These funds invest in US markets and other international assets.")

if not df_international.empty:
    df_int_format = df_international.copy()
    for col in ["1Y CAGR (%)", "3Y CAGR (%)", "5Y CAGR (%)"]:
        df_int_format[col] = df_int_format[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A")
    
    if "Risk Score" in df_int_format.columns:
        df_int_format["Risk Score"] = df_int_format["Risk Score"].apply(lambda x: f"{int(x)}/10" if pd.notnull(x) else "N/A")
    elif "Sharpe Ratio" in df_int_format.columns:
        df_int_format = df_int_format.rename(columns={"Sharpe Ratio": "Risk Score (Pending Sync)"})

    st.dataframe(
        df_int_format.set_index("AMFI Code"),
        width="stretch",
        height=250
    )
else:
    st.info("No international funds matched the current filter.")

st.sidebar.write("---")
st.sidebar.info("💡 **How to use this?**\n\n1. Sort to find a fund with high CAGR and a Risk Score that matches your profile.\n2. Copy its **AMFI Code**.\n3. Run `python mutual_2.py` in your terminal and paste the code to predict your future wealth!")
