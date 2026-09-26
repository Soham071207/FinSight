"""
garch_model.py — GARCH(1,1) conditional volatility extraction.

Uses the `arch` library to fit a GARCH(1,1) model on daily log-returns.
Extracts the conditional volatility series as a feature column for
downstream models (LightGBM, meta-learner).

Walk-forward aware: fits on training window only, forecasts for test window.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import logging

from config import CONFIG

logger = logging.getLogger(__name__)

# Lazy import to avoid crash if arch is not installed
try:
    from arch import arch_model
    HAS_ARCH = True
except ImportError:
    HAS_ARCH = False
    logger.warning("arch library not installed. GARCH features will be zeros.")


class GARCHModel:
    """
    Fits GARCH(1,1) on daily returns and extracts conditional volatility.

    Usage:
        gm = GARCHModel()
        df = gm.fit_transform(df)           # adds 'garch_vol' column
        df = gm.fit_walk_forward(df, split)  # walk-forward version
    """

    def __init__(self):
        self.p = CONFIG["garch_p"]   # GARCH p parameter
        self.q = CONFIG["garch_q"]   # GARCH q parameter
        self.last_result = None      # store last fit result

    def _compute_returns(self, close: pd.Series) -> pd.Series:
        """Compute daily log-returns scaled to percentage (× 100)."""
        log_ret = np.log(close / close.shift(1)) * 100
        return log_ret.dropna()

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fit GARCH(1,1) on the entire close series and add 'garch_vol' column.
        Used for full-sample feature computation.
        """
        if not HAS_ARCH:
            df["garch_vol"] = 0.0
            return df

        returns = self._compute_returns(df["Close"])

        try:
            # Specify GARCH model: constant mean, GARCH variance, normal dist
            am = arch_model(
                returns,
                vol="Garch",
                p=self.p,
                q=self.q,
                mean="Constant",
                dist="normal",
            )
            result = am.fit(disp="off", show_warning=False)
            self.last_result = result

            # Conditional volatility (aligned to returns index)
            cond_vol = result.conditional_volatility
            # Normalise: divide by mean to get relative volatility
            cond_vol_norm = cond_vol / (cond_vol.mean() + 1e-9)

            df["garch_vol"] = cond_vol_norm.reindex(df.index).bfill().fillna(1.0)

            logger.info(f"  GARCH(1,1) fitted: AIC={result.aic:.1f}")

        except Exception as e:
            logger.warning(f"  GARCH fitting failed: {e}. Using fallback.")
            # Fallback: rolling std as volatility proxy
            df["garch_vol"] = (
                df["Close"].pct_change().rolling(20).std()
                / (df["Close"].pct_change().rolling(100).std() + 1e-9)
            ).fillna(1.0)

        return df

    def fit_walk_forward(self, df: pd.DataFrame, train_end_idx: int) -> pd.DataFrame:
        """
        Walk-forward GARCH: fit on data[:train_end_idx], forecast for the rest.
        Prevents data leakage in validation.

        Args:
            df: full DataFrame with Close prices
            train_end_idx: integer index splitting train/test

        Returns:
            df with 'garch_vol' column (fitted on train, forecast on test)
        """
        if not HAS_ARCH:
            df["garch_vol"] = 0.0
            return df

        returns = self._compute_returns(df["Close"])

        # Split returns into train/test
        train_returns = returns.iloc[:train_end_idx]

        try:
            am = arch_model(
                train_returns,
                vol="Garch",
                p=self.p,
                q=self.q,
                mean="Constant",
                dist="normal",
            )
            result = am.fit(disp="off", show_warning=False)
            self.last_result = result

            # In-sample conditional volatility
            in_sample_vol = result.conditional_volatility

            # Out-of-sample: use last fitted params to forecast
            # We forecast one step at a time using the full returns series
            test_len = len(returns) - train_end_idx
            if test_len > 0:
                forecast = result.forecast(horizon=1, start=train_returns.index[-1],
                                           reindex=False)
                # For simplicity, use the last in-sample vol for all OOS points
                # (true rolling GARCH would refit, but that's very slow)
                last_vol = float(in_sample_vol.iloc[-1])
                oos_vol = pd.Series(
                    [last_vol] * test_len,
                    index=returns.index[train_end_idx:],
                )
                full_vol = pd.concat([in_sample_vol, oos_vol])
            else:
                full_vol = in_sample_vol

            # Normalise
            full_vol_norm = full_vol / (full_vol.mean() + 1e-9)
            df["garch_vol"] = full_vol_norm.reindex(df.index).bfill().fillna(1.0)

        except Exception as e:
            logger.warning(f"  GARCH walk-forward failed: {e}. Using fallback.")
            df["garch_vol"] = (
                df["Close"].pct_change().rolling(20).std()
                / (df["Close"].pct_change().rolling(100).std() + 1e-9)
            ).fillna(1.0)

        return df

    def get_summary(self) -> str:
        """Return a human-readable summary of the last GARCH fit."""
        if self.last_result is None:
            return "GARCH not fitted yet."
        r = self.last_result
        return (
            f"GARCH({self.p},{self.q}) | "
            f"omega={r.params.get('omega', 0):.6f}, "
            f"alpha={r.params.get('alpha[1]', 0):.4f}, "
            f"beta={r.params.get('beta[1]', 0):.4f} | "
            f"AIC={r.aic:.1f}"
        )
