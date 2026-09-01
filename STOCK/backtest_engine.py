"""
backtest_engine.py — Walk-forward validation + position sizing + risk management.

Features:
  • TimeSeriesSplit (3 folds minimum, NO random shuffle)
  • Per-fold metrics: Sharpe Ratio, Max Drawdown, Win Rate
  • ATR-based stop loss: entry ± 2 × ATR(14)
  • Inverse-volatility position sizing
  • Max position size: 10 % of portfolio per stock
  • Debounce logic: 2 consecutive same signals before acting
  • Transaction costs applied on entry/exit
"""

import numpy as np
import pandas as pd
import logging
from sklearn.model_selection import TimeSeriesSplit

from config import CONFIG

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Walk-forward backtester with risk management.

    Usage:
        engine = BacktestEngine()
        results = engine.run(df, signals_series, confidence_series)
    """

    def __init__(self):
        self.initial_capital = CONFIG["initial_capital"]
        self.atr_mult        = CONFIG["atr_stop_multiplier"]
        self.max_pos_pct     = CONFIG["max_position_pct"]
        self.tx_cost         = CONFIG["transaction_cost"]
        self.debounce_days   = CONFIG["debounce_days"]
        self.n_splits        = CONFIG["n_splits"]

    # ── Walk-Forward Splits ───────────────────────────────────────────────

    def get_splits(self, df: pd.DataFrame) -> list:
        """
        Generate TimeSeriesSplit indices.
        Returns list of (train_index, test_index) tuples.
        """
        test_size = CONFIG["test_size_days"]
        n = len(df)
        splits = []

        tscv = TimeSeriesSplit(n_splits=self.n_splits, test_size=test_size)
        for train_idx, test_idx in tscv.split(df):
            splits.append((train_idx, test_idx))

        return splits

    # ── Debounce Logic ────────────────────────────────────────────────────

    def _debounce_signals(self, raw_signals: pd.Series) -> pd.Series:
        """
        Require `debounce_days` consecutive same signals before acting.
        Prevents whipsaw from noisy single-day flips.
        """
        debounced = raw_signals.copy()
        streak = 1
        prev   = raw_signals.iloc[0]

        for i in range(1, len(raw_signals)):
            curr = raw_signals.iloc[i]
            if curr == prev:
                streak += 1
            else:
                streak = 1
                prev   = curr

            # Only allow signal change if streak >= debounce threshold
            if streak < self.debounce_days:
                debounced.iloc[i] = debounced.iloc[i - 1]  # keep previous

        return debounced

    # ── Position Sizing ───────────────────────────────────────────────────

    def _compute_position_size(self, atr_norm: float, confidence: float,
                               capital: float) -> float:
        """
        Inverse-volatility position sizing capped at max_position_pct.

        Higher ATR → smaller position.
        Higher confidence → larger position.
        """
        if atr_norm <= 0:
            atr_norm = 0.01

        # Base size: inverse of normalised ATR
        inv_vol_size = 1.0 / (atr_norm * 50)  # scale factor

        # Adjust by confidence (0-100 → 0.3-1.0 multiplier)
        conf_mult = 0.3 + 0.7 * (confidence / 100.0)

        # Raw position as fraction of capital
        raw_pct = inv_vol_size * conf_mult

        # Cap at max position %
        capped = min(raw_pct, self.max_pos_pct)

        return capped * capital

    # ── Single-Fold Backtest ──────────────────────────────────────────────

    def run_single(self, df: pd.DataFrame, signals: pd.Series,
                   confidences: pd.Series) -> dict:
        """
        Run backtest on a single period.

        Args:
            df          : DataFrame with Close, atr_14 columns
            signals     : Series of signal strings ("Strong Buy","Buy","Hold","Sell")
            confidences : Series of confidence scores (0-100)

        Returns dict with:
            equity_curve, dates, metrics, trade_log
        """
        # Debounce signals
        # Convert to numeric: Strong Buy/Buy → 1, Hold → 0, Sell → -1
        sig_numeric = signals.map({
            "Strong Buy": 1, "Buy": 1, "Hold": 0, "Sell": -1
        }).fillna(0).astype(int)
        sig_debounced = self._debounce_signals(sig_numeric)

        capital      = float(self.initial_capital)
        equity       = [capital]
        dates_list   = [df.index[0]]
        trade_log    = []
        position     = 0        # 0 = flat, 1 = long
        entry_price  = None
        stop_loss    = None
        pos_size     = 0.0      # dollar amount in position

        for i in range(1, len(df)):
            date  = df.index[i]
            close = float(df["Close"].iloc[i])
            atr   = float(df["atr_14"].iloc[i]) if "atr_14" in df.columns else 0.02
            sig   = int(sig_debounced.iloc[i])
            conf  = float(confidences.iloc[i]) if i < len(confidences) else 50.0

            prev_close = float(df["Close"].iloc[i - 1])
            daily_ret  = (close / prev_close) - 1 if prev_close > 0 else 0

            # ── Check stop loss ───────────────────────────────────────
            if position == 1 and stop_loss is not None and close <= stop_loss:
                # Stop loss triggered
                pnl = pos_size * ((close / entry_price) - 1)
                capital += pos_size + pnl - (pos_size * self.tx_cost)
                trade_log.append({
                    "date": date, "action": "STOP-LOSS",
                    "price": close, "pnl": pnl,
                })
                position    = 0
                entry_price = None
                stop_loss   = None
                pos_size    = 0

            # ── Entry logic ───────────────────────────────────────────
            elif position == 0 and sig == 1:
                pos_size    = self._compute_position_size(atr, conf, capital)
                entry_price = close
                # ATR-based stop loss: entry - 2 × ATR (raw, not normalised)
                atr_raw     = atr * close
                stop_loss   = entry_price - (self.atr_mult * atr_raw)
                capital    -= pos_size + (pos_size * self.tx_cost)
                position    = 1
                trade_log.append({
                    "date": date, "action": "BUY",
                    "price": close, "stop": stop_loss,
                })

            # ── Exit logic ────────────────────────────────────────────
            elif position == 1 and sig <= 0:
                pnl = pos_size * ((close / entry_price) - 1)
                capital += pos_size + pnl - (pos_size * self.tx_cost)
                trade_log.append({
                    "date": date, "action": "SELL",
                    "price": close, "pnl": pnl,
                })
                position    = 0
                entry_price = None
                stop_loss   = None
                pos_size    = 0

            # ── Update trailing stop ──────────────────────────────────
            elif position == 1:
                # Mark-to-market
                atr_raw   = atr * close
                new_stop  = close - (self.atr_mult * atr_raw)
                if new_stop > stop_loss:
                    stop_loss = new_stop

            # Track equity (mark-to-market)
            if position == 1:
                mtm = pos_size * ((close / entry_price) - 1)
                equity.append(capital + pos_size + mtm)
            else:
                equity.append(capital)
            dates_list.append(date)

        # Close any open position at end
        if position == 1:
            final_close = float(df["Close"].iloc[-1])
            pnl = pos_size * ((final_close / entry_price) - 1)
            capital += pos_size + pnl
            trade_log.append({
                "date": df.index[-1], "action": "CLOSE-EOD",
                "price": final_close, "pnl": pnl,
            })

        equity = np.array(equity)
        metrics = self._compute_metrics(equity)
        metrics["n_trades"] = len(trade_log)

        return {
            "equity_curve": equity,
            "dates":        dates_list,
            "metrics":      metrics,
            "trade_log":    trade_log,
        }

    # ── Metrics Computation ───────────────────────────────────────────────

    def _compute_metrics(self, equity: np.ndarray) -> dict:
        """Compute Sharpe, Max Drawdown, Win Rate from equity curve."""
        if len(equity) < 2:
            return {"sharpe": 0, "max_drawdown": 0, "win_rate": 0, "total_return": 0}

        rets = pd.Series(equity).pct_change().dropna()

        # Annualised Sharpe Ratio
        sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(252)

        # Max Drawdown
        rolling_max = np.maximum.accumulate(equity)
        drawdown    = (equity / rolling_max - 1) * 100
        max_dd      = float(drawdown.min())

        # Win Rate (daily)
        win_rate = float((rets > 0).sum() / (len(rets) + 1e-9) * 100)

        # Total Return
        total_ret = float((equity[-1] / equity[0] - 1) * 100)

        return {
            "sharpe":       round(sharpe, 3),
            "max_drawdown": round(max_dd, 2),
            "win_rate":     round(win_rate, 1),
            "total_return": round(total_ret, 2),
        }

    # ── Full Walk-Forward Backtest ────────────────────────────────────────

    def walk_forward(self, df: pd.DataFrame, signals: pd.Series,
                     confidences: pd.Series) -> dict:
        """
        Run walk-forward validation across all folds.

        Returns:
            dict with per_fold_metrics, combined_equity, combined_dates
        """
        splits = self.get_splits(df)
        all_fold_results = []

        for fold_i, (train_idx, test_idx) in enumerate(splits):
            df_test   = df.iloc[test_idx].copy()
            sig_test  = signals.iloc[test_idx].copy()
            conf_test = confidences.iloc[test_idx].copy()

            result = self.run_single(df_test, sig_test, conf_test)
            result["fold"] = fold_i + 1
            all_fold_results.append(result)

            m = result["metrics"]
            logger.info(
                f"  Fold {fold_i+1}: Return={m['total_return']:+.2f}% | "
                f"Sharpe={m['sharpe']:.3f} | MaxDD={m['max_drawdown']:.2f}% | "
                f"WinRate={m['win_rate']:.1f}%"
            )

        # Combine equity curves across folds
        combined_equity = np.array([self.initial_capital])
        combined_dates  = []
        for i, r in enumerate(all_fold_results):
            # Chain: scale next fold's equity to start where previous ended
            scale = combined_equity[-1] / r["equity_curve"][0]
            if i == 0:
                # Include the starting date for the first fold
                combined_dates.append(r["dates"][0])
            combined_equity = np.concatenate([
                combined_equity, r["equity_curve"][1:] * scale
            ])
            combined_dates.extend(r["dates"][1:])

        combined_metrics = self._compute_metrics(combined_equity)
        combined_metrics["n_trades"] = sum(r["metrics"]["n_trades"] for r in all_fold_results)

        return {
            "per_fold":         [r["metrics"] for r in all_fold_results],
            "combined_equity":  combined_equity,
            "combined_dates":   combined_dates,
            "combined_metrics": combined_metrics,
            "fold_results":     all_fold_results,
        }
