"""Shared mechanics; callers explicitly choose monthly/quarterly anchor policy."""
from datetime import date
from pathlib import Path


def period_end(anchor, frequency):
    import pandas as pd
    return pd.Timestamp(anchor).normalize().to_period(frequency).to_timestamp(how="end").normalize()


def baseline_level(series, anchor, *, frequency):
    end = period_end(anchor, frequency)
    series = series.dropna().sort_index()
    if series.empty:
        raise ValueError("Series is empty after dropping NaNs.")
    head = series.loc[:end]
    if head.empty:
        raise ValueError(f"No observations on or before {end:%Y-%m-%d}.")
    return float(head.iloc[-1])


def rebase(series, anchor, *, frequency):
    base = baseline_level(series, anchor, frequency=frequency)
    if base == 0:
        raise ValueError("Baseline level is zero; cannot rebase.")
    return 100.0 * series / base


def load_series(path):
    import pandas as pd
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"{path} is missing - run `make data` to fetch it.")
    return pd.read_csv(path, parse_dates=["date"], index_col="date").sort_index()


def data_pulled_date(stamp, data):
    if stamp.exists():
        value = stamp.read_text(encoding="utf-8").strip()
        if value:
            return value[:10]
    if data.exists():
        return date.fromtimestamp(data.stat().st_mtime).isoformat()
    return ""
