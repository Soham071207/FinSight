import numpy as np
import pandas as pd
from typing import Iterator, Tuple

def _as_datetime_index(dates: np.ndarray) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(dates))

def purged_walk_forward_splits(
    dates: np.ndarray,
    n_splits: int = 3,
    test_size: int = 252,
    label_horizon: int = 5,
    embargo_pct: float = 0.01,
    min_train_size: int = 252,
) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
    dt_index = _as_datetime_index(dates)
    order = np.argsort(dt_index.values)
    sorted_dates = dt_index.values[order]
    n = len(sorted_dates)

    embargo_days = max(1, int(round(test_size * embargo_pct)))
    test_starts = [n - (n_splits - i) * test_size for i in range(n_splits)]

    for fold, test_start in enumerate(test_starts):
        test_end = test_start + test_size
        if test_start < 0 or test_end > n:
            raise ValueError(
                f"Not enough data for {n_splits} folds of size {test_size}. "
                f"Have {n} rows, need at least {n_splits * test_size}."
            )

        test_pos = np.arange(test_start, test_end)
        purge_start = max(0, test_start - label_horizon)
        train_pos = np.arange(0, purge_start)
        embargo_end = min(n, test_end + embargo_days)
        train_pos = train_pos[~((train_pos >= test_end) & (train_pos < embargo_end))]

        if len(train_pos) < min_train_size:
            print(f"[purged_walk_forward_splits] Fold {fold}: skipped, only {len(train_pos)} usable training rows.")
            continue

        train_idx = order[train_pos]
        test_idx = order[test_pos]
        yield train_idx, test_idx

def purged_walk_forward_splits_panel(
    df: pd.DataFrame,
    date_col: str = "date",
    ticker_col: str = "ticker",
    n_splits: int = 3,
    test_size: int = 252,
    label_horizon: int = 5,
    embargo_pct: float = 0.01,
    min_train_size: int = 252,
) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
    unique_dates = np.sort(df[date_col].unique())

    for train_date_pos, test_date_pos in purged_walk_forward_splits(
        dates=unique_dates,
        n_splits=n_splits,
        test_size=test_size,
        label_horizon=label_horizon,
        embargo_pct=embargo_pct,
        min_train_size=min_train_size,
    ):
        train_dates = set(unique_dates[train_date_pos])
        test_dates = set(unique_dates[test_date_pos])

        train_mask = df[date_col].isin(train_dates).values
        test_mask = df[date_col].isin(test_dates).values

        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]
        yield train_idx, test_idx
