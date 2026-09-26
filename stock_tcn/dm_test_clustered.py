import numpy as np
import pandas as pd
from dataclasses import dataclass
from scipy import stats

def _newey_west_variance(x: np.ndarray, h: int = 1) -> float:
    n = len(x)
    x = np.asarray(x, dtype=float)
    x_demeaned = x - x.mean()

    max_lag = max(0, h - 1)
    gamma_0 = np.sum(x_demeaned**2) / n
    var = gamma_0

    for lag in range(1, max_lag + 1):
        weight = 1.0 - lag / (max_lag + 1)
        gamma_lag = np.sum(x_demeaned[lag:] * x_demeaned[:-lag]) / n
        var += 2 * weight * gamma_lag

    return var / n

def diebold_mariano(loss_a: np.ndarray, loss_b: np.ndarray, h: int = 1) -> tuple[float, float]:
    loss_a = np.asarray(loss_a, dtype=float)
    loss_b = np.asarray(loss_b, dtype=float)
    if loss_a.shape != loss_b.shape:
        raise ValueError("loss_a and loss_b must have the same shape")

    d = loss_a - loss_b
    d_mean = d.mean()
    var_d_mean = _newey_west_variance(d, h=h)

    if var_d_mean <= 0:
        raise ValueError("Non-positive HAC variance estimate")

    dm_stat = d_mean / np.sqrt(var_d_mean)
    p_value = 2 * (1 - stats.norm.cdf(np.abs(dm_stat)))
    return dm_stat, p_value

@dataclass
class ClusteredDMResult:
    dm_stat: float
    p_value: float
    n_dates: int
    n_raw_observations: int
    mean_daily_loss_diff: float

    def __str__(self) -> str:
        return (
            f"Date-clustered DM test:\n"
            f"  DM statistic     = {self.dm_stat:.4f}\n"
            f"  p-value          = {self.p_value:.4g}\n"
            f"  effective N      = {self.n_dates} trading days "
            f"(vs. {self.n_raw_observations} raw ticker-day rows)\n"
            f"  mean daily loss diff (A-B) = {self.mean_daily_loss_diff:.6f}"
        )

def clustered_dm_test(df: pd.DataFrame, date_col: str, loss_a_col: str, loss_b_col: str, h: int = 1) -> ClusteredDMResult:
    daily = (
        df.groupby(date_col)
        .apply(lambda g: pd.Series({
            "loss_a_mean": g[loss_a_col].mean(),
            "loss_b_mean": g[loss_b_col].mean(),
        }), include_groups=False)
        .sort_index()
    )

    dm_stat, p_value = diebold_mariano(
        daily["loss_a_mean"].values, daily["loss_b_mean"].values, h=h
    )

    return ClusteredDMResult(
        dm_stat=dm_stat,
        p_value=p_value,
        n_dates=len(daily),
        n_raw_observations=len(df),
        mean_daily_loss_diff=float((daily["loss_a_mean"] - daily["loss_b_mean"]).mean()),
    )

def naive_pooled_dm_test(df: pd.DataFrame, loss_a_col: str, loss_b_col: str, h: int = 1) -> tuple[float, float]:
    return diebold_mariano(df[loss_a_col].values, df[loss_b_col].values, h=h)
