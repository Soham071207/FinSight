"""
output_engine.py — Signal generation, charts, and reports.

Generates per-stock:
  • Final Buy/Sell/Hold signal with confidence (0-100)
  • Entry price, stop loss, target price
  • Current regime label + sentiment label
  • Most impactful headline
  • Feature importance chart (LightGBM)
  • Equity curve plot
  • Rolling Sharpe ratio plot
  • Sentiment vs price overlay chart
"""

import warnings
warnings.filterwarnings("ignore")

import os
import numpy as np
import pandas as pd
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from config import CONFIG

logger = logging.getLogger(__name__)

# ── Premium dark theme ────────────────────────────────────────────────────────
DARK_BG  = "#0d1117"
CARD_BG  = "#161b22"
ACCENT   = "#58a6ff"
GREEN    = "#3fb950"
RED      = "#f85149"
YELLOW   = "#d29922"
PURPLE   = "#a371f7"
TEXT_CLR = "#e6edf3"
MUTED    = "#8b949e"
GRID_CLR = "#21262d"

plt.rcParams.update({
    "figure.facecolor": DARK_BG,
    "axes.facecolor":   CARD_BG,
    "axes.edgecolor":   GRID_CLR,
    "axes.labelcolor":  TEXT_CLR,
    "xtick.color":      MUTED,
    "ytick.color":      MUTED,
    "text.color":       TEXT_CLR,
    "grid.color":       GRID_CLR,
    "grid.alpha":       0.6,
    "font.family":      "monospace",
})


class OutputEngine:
    """Generates all output: signals, charts, CSV reports."""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or CONFIG["output_dir"]
        os.makedirs(self.output_dir, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════════
    #  SIGNAL COMPUTATION
    # ══════════════════════════════════════════════════════════════════════

    def compute_final_signal(self, lgbm_signal: str, confidence: float,
                             regime: int, atr_norm: float,
                             close: float) -> dict:
        """
        Compute the final output signal with entry, stop, and target prices.

        Args:
            lgbm_signal : "Strong Buy", "Buy", "Hold", or "Sell"
            confidence  : meta-learner score (0-100)
            regime      : regime id (0-3)
            atr_norm    : normalised ATR (decimal)
            close       : current close price

        Returns dict with all output fields.
        """
        atr_raw = atr_norm * close

        # Entry / stop / target
        entry_price  = close
        stop_loss    = close - (CONFIG["atr_stop_multiplier"] * atr_raw)
        target_price = close + (3.0 * atr_raw)  # 3:1 reward-risk ratio

        # Map signal to Buy/Sell/Hold
        if lgbm_signal in ("Strong Buy", "Buy"):
            final_action = "BUY"
        elif lgbm_signal == "Sell":
            final_action = "SELL"
        else:
            final_action = "HOLD"

        regime_label = CONFIG["regime_labels"].get(regime, "Unknown")

        return {
            "signal":        final_action,
            "lgbm_signal":   lgbm_signal,
            "confidence":    round(confidence, 1),
            "entry_price":   round(entry_price, 2),
            "stop_loss":     round(stop_loss, 2),
            "target_price":  round(target_price, 2),
            "regime":        regime,
            "regime_label":  regime_label,
        }

    # ══════════════════════════════════════════════════════════════════════
    #  CHARTS
    # ══════════════════════════════════════════════════════════════════════

    def plot_equity_curve(self, equity: np.ndarray, dates: list,
                          ticker: str, metrics: dict,
                          baseline_equity: np.ndarray = None,
                          return_base64: bool = False):
        """Plot equity curve with optional buy-and-hold baseline."""
        fig, ax = plt.subplots(figsize=(14, 5), facecolor=DARK_BG)

        ax.plot(dates, equity, color=ACCENT, linewidth=2, label="Strategy")
        if baseline_equity is not None and len(baseline_equity) == len(dates):
            ax.plot(dates, baseline_equity, color=MUTED, linewidth=1.5,
                    linestyle="--", label="Buy & Hold")

        # Shade profit / loss regions
        init = equity[0]
        ax.fill_between(dates, init, equity,
                        where=(equity >= init), alpha=0.12, color=GREEN)
        ax.fill_between(dates, init, equity,
                        where=(equity < init), alpha=0.12, color=RED)
        ax.axhline(init, color=MUTED, linewidth=0.8, linestyle=":")

        ax.set_title(f"{ticker} — Equity Curve", fontsize=14, pad=10)
        ax.set_ylabel("Portfolio Value")
        ax.legend(framealpha=0.2, fontsize=9)
        ax.grid(True, axis="y")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))

        # Metrics annotation
        m_text = (
            f"Return: {metrics.get('total_return', 0):+.2f}%  |  "
            f"Sharpe: {metrics.get('sharpe', 0):.3f}  |  "
            f"Max DD: {metrics.get('max_drawdown', 0):.2f}%  |  "
            f"Trades: {metrics.get('n_trades', 0)}"
        )
        ax.text(0.5, -0.12, m_text, transform=ax.transAxes,
                ha="center", fontsize=9, color=MUTED,
                bbox=dict(facecolor=CARD_BG, edgecolor=GRID_CLR,
                          boxstyle="round,pad=0.4"))

        if return_base64:
            import io, base64
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=CONFIG["chart_dpi"], bbox_inches="tight", facecolor=DARK_BG)
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")

        path = os.path.join(self.output_dir, f"{ticker}_equity_curve.png")
        fig.savefig(path, dpi=CONFIG["chart_dpi"], bbox_inches="tight",
                    facecolor=DARK_BG)
        plt.close(fig)
        logger.info(f"  📊 Equity curve → {path}")
        return path

    def plot_rolling_sharpe(self, equity: np.ndarray, dates: list,
                             ticker: str, window: int = 60,
                             return_base64: bool = False):
        """Plot rolling Sharpe ratio (60-day default)."""
        fig, ax = plt.subplots(figsize=(14, 4), facecolor=DARK_BG)

        rets = pd.Series(equity).pct_change().dropna()
        rolling_sharpe = (
            rets.rolling(window).mean() / (rets.rolling(window).std() + 1e-9)
        ) * np.sqrt(252)

        # Trim dates to match
        plot_dates = dates[1:]  # skip first (pct_change drops it)
        if len(plot_dates) > len(rolling_sharpe):
            plot_dates = plot_dates[:len(rolling_sharpe)]
        elif len(rolling_sharpe) > len(plot_dates):
            rolling_sharpe = rolling_sharpe[:len(plot_dates)]

        ax.plot(plot_dates, rolling_sharpe.values, color=PURPLE, linewidth=1.5)
        ax.axhline(0, color=MUTED, linewidth=0.8, linestyle=":")
        ax.axhline(0.8, color=GREEN, linewidth=0.8, linestyle="--",
                   alpha=0.6, label="Target Sharpe (0.8)")
        ax.fill_between(plot_dates, 0, rolling_sharpe.values,
                        where=(rolling_sharpe.values >= 0), alpha=0.1, color=GREEN)
        ax.fill_between(plot_dates, 0, rolling_sharpe.values,
                        where=(rolling_sharpe.values < 0), alpha=0.1, color=RED)

        ax.set_title(f"{ticker} — {window}-Day Rolling Sharpe Ratio",
                     fontsize=13, pad=10)
        ax.set_ylabel("Sharpe Ratio")
        ax.legend(framealpha=0.2, fontsize=9)
        ax.grid(True, axis="y")

        if return_base64:
            import io, base64
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=CONFIG["chart_dpi"], bbox_inches="tight", facecolor=DARK_BG)
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")

        path = os.path.join(self.output_dir, f"{ticker}_rolling_sharpe.png")
        fig.savefig(path, dpi=CONFIG["chart_dpi"], bbox_inches="tight",
                    facecolor=DARK_BG)
        plt.close(fig)
        logger.info(f"  📊 Rolling Sharpe → {path}")
        return path

    def plot_sentiment_overlay(self, df: pd.DataFrame, ticker: str,
                                last_n: int = 300,
                                return_base64: bool = False):
        """Price vs sentiment score overlay chart."""
        fig, ax1 = plt.subplots(figsize=(14, 5), facecolor=DARK_BG)

        subset = df.iloc[-last_n:]
        dates  = subset.index

        # Price on primary axis
        ax1.plot(dates, subset["Close"], color=ACCENT, linewidth=1.5, label="Close Price")
        ax1.set_ylabel("Price", color=ACCENT)
        ax1.tick_params(axis="y", labelcolor=ACCENT)

        # Sentiment on secondary axis
        ax2 = ax1.twinx()
        if "daily_sentiment_score" in subset.columns:
            sent = subset["daily_sentiment_score"]
            ax2.fill_between(dates, 0, sent,
                             where=(sent >= 0), alpha=0.3, color=GREEN, label="Bullish")
            ax2.fill_between(dates, 0, sent,
                             where=(sent < 0), alpha=0.3, color=RED, label="Bearish")
            ax2.plot(dates, sent, color=YELLOW, linewidth=0.8, alpha=0.7)
            ax2.set_ylabel("Sentiment Score", color=YELLOW)
            ax2.tick_params(axis="y", labelcolor=YELLOW)
            ax2.set_ylim(-1, 1)

        ax1.set_title(f"{ticker} — Sentiment vs Price", fontsize=13, pad=10)
        ax1.grid(True, axis="y")

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, framealpha=0.2,
                   fontsize=8, loc="upper left")

        if return_base64:
            import io, base64
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=CONFIG["chart_dpi"], bbox_inches="tight", facecolor=DARK_BG)
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")

        path = os.path.join(self.output_dir, f"{ticker}_sentiment_overlay.png")
        fig.savefig(path, dpi=CONFIG["chart_dpi"], bbox_inches="tight",
                    facecolor=DARK_BG)
        plt.close(fig)
        logger.info(f"  📊 Sentiment overlay → {path}")
        return path

    def plot_feature_importance(self, importance: pd.Series, ticker: str,
                                 top_n: int = 15,
                                 return_base64: bool = False):
        """Horizontal bar chart of LightGBM feature importances."""
        if importance.empty:
            return None

        fig, ax = plt.subplots(figsize=(10, 6), facecolor=DARK_BG)

        top = importance.head(top_n).sort_values()
        colors = [ACCENT if v > top.median() else MUTED for v in top.values]

        ax.barh(top.index, top.values, color=colors, height=0.6, edgecolor=GRID_CLR)
        ax.set_xlabel("Importance Score")
        ax.set_title(f"{ticker} — Feature Importance (Top {top_n})",
                     fontsize=13, pad=10)
        ax.grid(True, axis="x")

        if return_base64:
            import io, base64
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=CONFIG["chart_dpi"], bbox_inches="tight", facecolor=DARK_BG)
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")

        path = os.path.join(self.output_dir, f"{ticker}_feature_importance.png")
        fig.savefig(path, dpi=CONFIG["chart_dpi"], bbox_inches="tight",
                    facecolor=DARK_BG)
        plt.close(fig)
        logger.info(f"  📊 Feature importance → {path}")
        return path

    # ══════════════════════════════════════════════════════════════════════
    #  COMBINED DASHBOARD
    # ══════════════════════════════════════════════════════════════════════

    def generate_dashboard(self, ticker: str, df: pd.DataFrame,
                            signal_info: dict, sentiment_info: dict,
                            backtest_result: dict,
                            importance: pd.Series, currency: str = "USD"):
        """
        Generate all charts and a text summary for a single ticker.
        Returns dict of file paths.
        """
        paths = {}

        # 1. Equity curve
        bt = backtest_result
        paths["equity"] = self.plot_equity_curve(
            bt["combined_equity"], bt["combined_dates"],
            ticker, bt["combined_metrics"],
        )

        # 2. Rolling Sharpe
        paths["sharpe"] = self.plot_rolling_sharpe(
            bt["combined_equity"], bt["combined_dates"], ticker
        )

        # 3. Sentiment overlay
        if "daily_sentiment_score" in df.columns:
            paths["sentiment"] = self.plot_sentiment_overlay(df, ticker)

        # 4. Feature importance
        if importance is not None and not importance.empty:
            paths["importance"] = self.plot_feature_importance(importance, ticker)

        # 5. Text summary
        summary = self._build_summary(ticker, signal_info, sentiment_info,
                                       bt["combined_metrics"], bt["per_fold"], currency)
        summary_path = os.path.join(self.output_dir, f"{ticker}_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
        paths["summary"] = summary_path
        logger.info(f"  📝 Summary → {summary_path}")

        return paths

    def _build_summary(self, ticker: str, signal: dict, sentiment: dict,
                        metrics: dict, fold_metrics: list, currency: str = "USD") -> str:
        """Build a formatted text summary."""
        sep = "═" * 55
        sym = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$"}.get(currency, "$")

        lines = [
            sep,
            f"  STOCK PREDICTION REPORT: {ticker}",
            sep,
            "",
            "  ── SIGNAL ──────────────────────────────────────────",
            f"  Action         : {signal.get('signal', 'N/A')}",
            f"  LightGBM Class : {signal.get('lgbm_signal', 'N/A')}",
            f"  Confidence     : {signal.get('confidence', 0):.1f} / 100",
            f"  Entry Price    : {sym}{signal.get('entry_price', 0):.2f}",
            f"  Stop Loss      : {sym}{signal.get('stop_loss', 0):.2f}",
            f"  Target Price   : {sym}{signal.get('target_price', 0):.2f}",
            f"  Regime         : {signal.get('regime_label', 'N/A')}",
            "",
            "  ── SENTIMENT ───────────────────────────────────────",
            f"  Sentiment      : {sentiment.get('sentiment_label', 'N/A')}",
            f"  Score          : {sentiment.get('daily_sentiment_score', 0):+.4f}",
            f"  3-Day Rolling  : {sentiment.get('sentiment_3d_rolling', 0):+.4f}",
            f"  7-Day Rolling  : {sentiment.get('sentiment_7d_rolling', 0):+.4f}",
            f"  Momentum       : {sentiment.get('sentiment_momentum', 0):+.4f}",
            f"  News Volume    : {sentiment.get('news_volume', 0):.4f}",
            f"  Top Headline   : {sentiment.get('top_headline', 'N/A')}",
            f"  Headline Link  : {sentiment.get('top_link', 'N/A')}",
            "",
            "  ── BACKTEST METRICS (Combined) ─────────────────────",
            f"  Total Return   : {metrics.get('total_return', 0):+.2f}%",
            f"  Sharpe Ratio   : {metrics.get('sharpe', 0):.3f}",
            f"  Max Drawdown   : {metrics.get('max_drawdown', 0):.2f}%",
            f"  Win Rate       : {metrics.get('win_rate', 0):.1f}%",
            f"  Total Trades   : {metrics.get('n_trades', 0)}",
            "",
            "  ── PER-FOLD BREAKDOWN ──────────────────────────────",
        ]

        for i, fm in enumerate(fold_metrics):
            lines.append(
                f"  Fold {i+1}: Return={fm['total_return']:+.2f}% | "
                f"Sharpe={fm['sharpe']:.3f} | "
                f"MaxDD={fm['max_drawdown']:.2f}% | "
                f"WinRate={fm['win_rate']:.1f}%"
            )

        lines.extend(["", sep])
        return "\n".join(lines)

    # ── Console Output ────────────────────────────────────────────────────

    def print_signal(self, ticker: str, signal_info: dict,
                     sentiment_info: dict, currency: str = "USD"):
        """Pretty-print the final signal to console."""
        s = signal_info
        st = sentiment_info
        sym = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$"}.get(currency, "$")

        icon = "🟢" if s["signal"] == "BUY" else ("🔴" if s["signal"] == "SELL" else "🟡")
        regime_icon = "📈" if s["regime"] in (0, 1) else "📉"

        print(f"\n  {ticker}")
        print(f"    Price        : {sym}{s['entry_price']:.2f}")
        print(f"    Regime       : {regime_icon} {s['regime_label']}")
        print(f"    Sentiment    : {st.get('sentiment_label', 'N/A')} "
              f"({st.get('daily_sentiment_score', 0):+.3f})")
        print(f"    Signal       : {icon} {s['signal']} ({s['lgbm_signal']})")
        print(f"    Confidence   : {s['confidence']:.1f}%")
        print(f"    Stop Loss    : {sym}{s['stop_loss']:.2f}")
        print(f"    Target       : {sym}{s['target_price']:.2f}")
        print(f"    Top Headline : {st.get('top_headline', 'N/A')}")
        print(f"    Headline Link: {st.get('top_link', 'N/A')}")
