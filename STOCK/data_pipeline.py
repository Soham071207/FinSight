"""
data_pipeline.py — Data fetching, cleaning, market detection, forex, and calendar alignment.

Responsibilities:
  • Auto-detect market from ticker suffix (.NS → NSE, .BO → BSE, etc.)
  • Fetch ≥ 5 years OHLCV via yfinance (auto_adjust=True)
  • Clean: forward-fill small gaps, drop bad rows, remove outlier returns
  • Detect currency from yfinance metadata
  • Fetch forex rate series (e.g. USD/INR) for macro features
  • Align data to valid trading days via pandas_market_calendars
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging

# Optional: market calendars
try:
    import pandas_market_calendars as mcal
    HAS_MARKET_CAL = True
except ImportError:
    HAS_MARKET_CAL = False

from config import CONFIG

logger = logging.getLogger(__name__)


class DataPipeline:
    """Handles all data fetching, cleaning, and market-specific operations."""

    def __init__(self):
        self.market_calendars = {}   # cache loaded calendars
        self._forex_cache = {}       # cache downloaded forex series

    # ── Market Detection ──────────────────────────────────────────────────

    def detect_market(self, ticker: str) -> str:
        """
        Auto-detect market from ticker suffix.
        .NS → NSE, .BO → BSE, .L → LSE, else → NYSE (US default).
        """
        upper = ticker.upper()
        for suffix, market in CONFIG["market_suffixes"].items():
            if upper.endswith(suffix):
                return market
        return CONFIG["default_market"]

    # ── Currency Detection ────────────────────────────────────────────────

    def get_currency(self, ticker: str) -> str:
        """Detect currency from yfinance metadata; fall back to market map."""
        try:
            info = yf.Ticker(ticker).info
            cur = info.get("currency", None)
            if cur:
                return cur.upper()
        except Exception:
            pass

        # Fallback map
        currency_map = {
            "NSE": "INR", "BSE": "INR",
            "LSE": "GBP", "EURONEXT": "EUR", "XETRA": "EUR",
            "NYSE": "USD", "NASDAQ": "USD", "TSX": "CAD",
        }
        return currency_map.get(self.detect_market(ticker), "USD")

    # ── Forex Rate Fetch ──────────────────────────────────────────────────

    def fetch_forex_rate(self, base: str = "USD", quote: str = "INR") -> pd.Series:
        """
        Fetch daily forex rate series (e.g. USD/INR) via yfinance.
        Returns a pd.Series indexed by date.  Cached per session.
        """
        cache_key = f"{base}{quote}"
        if cache_key in self._forex_cache:
            return self._forex_cache[cache_key]

        pair = f"{base}{quote}=X"
        years = CONFIG["history_years"]
        start = (datetime.now() - timedelta(days=years * 365 + 60)).strftime("%Y-%m-%d")

        try:
            fx = yf.download(pair, start=start, auto_adjust=True, progress=False)
            if fx.empty:
                raise ValueError("empty")
            if isinstance(fx.columns, pd.MultiIndex):
                fx.columns = [c[0] for c in fx.columns]
            rate = fx["Close"].squeeze()
            rate.name = cache_key
            self._forex_cache[cache_key] = rate
            logger.info(f"Fetched forex {pair}: {len(rate)} rows")
            return rate
        except Exception as e:
            logger.warning(f"Could not fetch forex {pair}: {e}")
            return pd.Series(dtype=float, name=cache_key)

    # ── OHLCV Download ────────────────────────────────────────────────────

    def fetch_data(self, ticker: str) -> pd.DataFrame:
        """
        Download OHLCV from yfinance with >= 5 years history.
        auto_adjust=True handles splits/dividends automatically.
        """
        years = CONFIG["history_years"]
        start = (datetime.now() - timedelta(days=years * 365 + 90)).strftime("%Y-%m-%d")

        logger.info(f"Downloading {ticker} from {start} …")
        df = yf.download(ticker, start=start, auto_adjust=True, progress=False)

        if df.empty:
            raise ValueError(f"No data returned for {ticker}")

        # Flatten multi-level columns yfinance sometimes returns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        # Ensure required columns exist
        df.columns = [str(c) for c in df.columns]
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(set(df.columns)):
            raise ValueError(f"{ticker}: missing columns. Got {list(df.columns)}")

        return df[["Open", "High", "Low", "Close", "Volume"]].copy()

    # ── Data Cleaning ─────────────────────────────────────────────────────

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean OHLCV data:
          1. Forward-fill gaps ≤ 5 consecutive days
          2. Drop remaining NaN in Close
          3. Remove zero-volume rows (non-trading artefacts)
          4. Remove outlier returns (> 50 % in one day — likely data errors)
        """
        df = df.ffill(limit=5)
        df.dropna(subset=["Close"], inplace=True)

        # Remove zero-volume days
        df = df[df["Volume"] > 0].copy()

        # Remove extreme single-day return outliers
        daily_ret = df["Close"].pct_change()
        mask = daily_ret.abs() < 0.50
        mask.iloc[0] = True          # always keep the first row
        df = df[mask].copy()

        return df

    # ── Market Calendar ───────────────────────────────────────────────────

    def get_market_calendar(self, market: str):
        """Return pandas_market_calendars calendar object (cached)."""
        if not HAS_MARKET_CAL:
            return None

        if market in self.market_calendars:
            return self.market_calendars[market]

        cal_map = {
            "NSE": "NSE", "BSE": "BSE",
            "NYSE": "NYSE", "NASDAQ": "NASDAQ",
            "LSE": "LSE", "EURONEXT": "EURONEXT",
            "XETRA": "XETR", "TSX": "TSX",
        }
        try:
            cal = mcal.get_calendar(cal_map.get(market, "NYSE"))
            self.market_calendars[market] = cal
            return cal
        except Exception as e:
            logger.warning(f"Calendar not found for {market}: {e}")
            return None

    def align_to_trading_days(self, df: pd.DataFrame, market: str) -> pd.DataFrame:
        """Filter DataFrame to only valid trading days per market calendar."""
        cal = self.get_market_calendar(market)
        if cal is None:
            return df

        start = df.index.min().strftime("%Y-%m-%d")
        end   = df.index.max().strftime("%Y-%m-%d")
        try:
            schedule   = cal.schedule(start_date=start, end_date=end)
            valid_days = schedule.index.normalize()
            aligned    = df[df.index.normalize().isin(valid_days)]
            return aligned if len(aligned) > 0 else df
        except Exception:
            return df

    # ── Full Pipeline ─────────────────────────────────────────────────────

    def process(self, ticker: str) -> tuple:
        """
        End-to-end: fetch → clean → align → validate.
        Returns (DataFrame, market_str, currency_str).
        """
        market   = self.detect_market(ticker)
        currency = self.get_currency(ticker)

        df = self.fetch_data(ticker)
        df = self.clean_data(df)
        df = self.align_to_trading_days(df, market)

        if len(df) < CONFIG["min_rows"]:
            raise ValueError(
                f"{ticker}: only {len(df)} rows after cleaning (need {CONFIG['min_rows']})"
            )

        logger.info(f"✓ {ticker}: {len(df)} rows | {market} | {currency}")
        return df, market, currency
