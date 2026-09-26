"""
feature_engine.py — Technical indicator computation using the `ta` library.

All features use only past/present data — labels are shifted separately
in the model modules to prevent data leakage.

Categories:
  • Momentum  : RSI(14), MACD, Stochastic Oscillator
  • Volatility: ATR(14), Bollinger Bands
  • Trend     : EMA(9,21,50), ADX
  • Volume    : OBV, VWAP approximation
  • Derived   : Price ROC, Rolling Returns (5d, 10d, 20d)
  • Macro     : USD/INR exchange rate (for Indian stocks)
"""

import pandas as pd
import numpy as np
import ta
import logging

from config import CONFIG, TECHNICAL_FEATURES

logger = logging.getLogger(__name__)


class FeatureEngine:
    """Computes all technical features for a given OHLCV DataFrame."""

    def __init__(self):
        self.feature_names = TECHNICAL_FEATURES.copy()

    # ── Momentum ──────────────────────────────────────────────────────────

    def _momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """RSI(14), MACD(12,26,9), Stochastic Oscillator(14)."""
        c, h, l = df["Close"], df["High"], df["Low"]

        # RSI
        df["rsi_14"] = ta.momentum.RSIIndicator(
            close=c, window=CONFIG["rsi_period"]
        ).rsi()

        # MACD
        macd = ta.trend.MACD(
            close=c,
            window_slow=CONFIG["macd_slow"],
            window_fast=CONFIG["macd_fast"],
            window_sign=CONFIG["macd_signal"],
        )
        df["macd"]             = macd.macd()
        df["macd_signal_line"] = macd.macd_signal()
        df["macd_diff"]        = macd.macd_diff()

        # Stochastic Oscillator
        stoch = ta.momentum.StochasticOscillator(
            high=h, low=l, close=c,
            window=CONFIG["stochastic_period"],
        )
        df["stoch_k"] = stoch.stoch()
        df["stoch_d"] = stoch.stoch_signal()

        return df

    # ── Volatility ────────────────────────────────────────────────────────

    def _volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """ATR(14) normalised, Bollinger Bands (20, 2σ)."""
        c, h, l = df["Close"], df["High"], df["Low"]

        # ATR — normalised by close for cross-stock comparability
        atr = ta.volatility.AverageTrueRange(
            high=h, low=l, close=c, window=CONFIG["atr_period"]
        )
        df["atr_14"] = atr.average_true_range() / c

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            close=c,
            window=CONFIG["bollinger_period"],
            window_dev=CONFIG["bollinger_std"],
        )
        df["bb_high"]  = (bb.bollinger_hband() / c) - 1   # relative
        df["bb_low"]   = (bb.bollinger_lband() / c) - 1
        df["bb_width"] = bb.bollinger_wband()
        df["bb_pband"] = bb.bollinger_pband()

        return df

    # ── Trend ─────────────────────────────────────────────────────────────

    def _trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """EMA(9,21,50) as ratio to close; ADX(14)."""
        c, h, l = df["Close"], df["High"], df["Low"]

        for period in CONFIG["ema_periods"]:
            ema = ta.trend.EMAIndicator(close=c, window=period)
            # Store as relative distance from close (dimensionless)
            df[f"ema_{period}"] = ema.ema_indicator() / c - 1

        # ADX
        adx = ta.trend.ADXIndicator(
            high=h, low=l, close=c, window=CONFIG["adx_period"]
        )
        df["adx"] = adx.adx()

        return df

    # ── Volume ────────────────────────────────────────────────────────────

    def _volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """OBV (normalised rate-of-change), VWAP ratio."""
        c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]

        # On-Balance Volume — 10-day diff normalised by rolling mean
        obv_raw = ta.volume.OnBalanceVolumeIndicator(close=c, volume=v).on_balance_volume()
        df["obv"] = obv_raw.diff(10) / (obv_raw.rolling(20).mean().abs() + 1e-9)

        # VWAP approximation — typical price × volume cumulative ratio
        typical = (h + l + c) / 3
        cum_tp_vol = (typical * v).rolling(20).sum()
        cum_vol    = v.rolling(20).sum()
        vwap_approx = cum_tp_vol / (cum_vol + 1e-9)
        df["vwap_ratio"] = c / vwap_approx - 1

        return df

    # ── Derived ───────────────────────────────────────────────────────────

    def _derived(self, df: pd.DataFrame) -> pd.DataFrame:
        """Price rate-of-change, rolling returns (5d, 10d, 20d)."""
        c = df["Close"]

        # 10-day price rate-of-change (%)
        df["price_roc"] = c.pct_change(10)

        # Rolling returns
        for w in CONFIG["rolling_return_windows"]:
            df[f"rolling_ret_{w}"] = c.pct_change(w)

        return df

    # ── Macro Feature (Forex) ─────────────────────────────────────────────

    def add_forex_feature(self, df: pd.DataFrame, forex_series: pd.Series) -> pd.DataFrame:
        """
        Merge USD/INR (or other forex) rate as a feature for Indian stocks.
        The forex series is reindexed to match the stock's dates.
        """
        if forex_series.empty:
            df["forex_rate"] = 0.0
            return df

        # Reindex forex to stock dates, forward-fill weekends/holidays
        fx = forex_series.reindex(df.index, method="ffill")
        df["forex_rate"] = fx.pct_change(5)  # 5-day % change in forex
        df["forex_rate"].fillna(0.0, inplace=True)
        return df

    # ── Regime Classification ─────────────────────────────────────────────

    def classify_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        4-regime classifier using ADX + EMA crossovers:
          0 = Bull Trending   (price > EMA50 & ADX > 25)
          1 = Bull Ranging    (price > EMA50 & ADX ≤ 25)
          2 = Bear Trending   (price ≤ EMA50 & ADX > 25)
          3 = Bear Ranging    (price ≤ EMA50 & ADX ≤ 25)
        """
        c = df["Close"]
        ema50_abs = ta.trend.EMAIndicator(close=c, window=50).ema_indicator()
        adx_abs   = df["adx"].copy()

        bull   = c > ema50_abs
        strong = adx_abs > 25

        df["regime"] = 3                                   # default: Bear Ranging
        df.loc[bull & strong,   "regime"] = 0              # Bull Trending
        df.loc[bull & ~strong,  "regime"] = 1              # Bull Ranging
        df.loc[~bull & strong,  "regime"] = 2              # Bear Trending
        # ~bull & ~strong stays 3                          # Bear Ranging

        return df

    # ── Master Builder ────────────────────────────────────────────────────

    def compute_all(self, df: pd.DataFrame,
                    forex_series: pd.Series = None,
                    is_indian: bool = False) -> pd.DataFrame:
        """
        Run full feature pipeline on an OHLCV DataFrame.
        Adds technical features, derived features, optional forex, and regime.
        Does NOT drop NaN — caller decides when to truncate.
        """
        df = self._momentum(df)
        df = self._volatility(df)
        df = self._trend(df)
        df = self._volume(df)
        df = self._derived(df)

        # Add forex macro feature for Indian stocks
        if is_indian and forex_series is not None:
            df = self.add_forex_feature(df, forex_series)
            if "forex_rate" not in self.feature_names:
                self.feature_names.append("forex_rate")

        # Classify market regime
        df = self.classify_regime(df)

        logger.info(f"  Features computed: {len(self.feature_names)} columns")
        return df
