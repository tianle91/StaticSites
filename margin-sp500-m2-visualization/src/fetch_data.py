#!/usr/bin/env python3
"""Network step: download every source series and write data/series.csv.

Sources:
  - FINRA margin statistics (debit balances)  -- margin-statistics.xlsx
  - FRED M2 / CPI / PPI                       -- fredgraph.csv
  - S&P 500 month-end levels                  -- yfinance (^GSPC)

The result is a monthly grid indexed by month-end, committed to the repo so that
`make` (plot_macro_series.py) renders offline and reproducibly. Re-run with
`make data` whenever you want fresher numbers.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SERIES_CSV = DATA_DIR / "series.csv"
PULLED_STAMP = DATA_DIR / "generated_at.txt"

FINRA_MARGIN_XLSX = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

START = pd.Timestamp("2000-01-01")
END = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)


def _fetch_fred_monthly(series_id: str) -> pd.Series:
    r = requests.get(FRED_CSV.format(series=series_id), timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content), parse_dates=["observation_date"])
    if series_id not in df.columns:
        raise KeyError(f"Column {series_id} missing from FRED CSV response.")
    s = df.set_index("observation_date")[series_id].sort_index()
    s = s.loc[(s.index >= START) & (s.index <= END)]
    # FRED uses month-beginning stamps; treat as month period end for alignment.
    s.index = s.index.to_period("M").to_timestamp(how="end").normalize()
    return s.astype(float)


def _fetch_margin_debit() -> pd.Series:
    r = requests.get(FINRA_MARGIN_XLSX, timeout=120)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), engine="openpyxl")
    ym = df.columns[0]
    debit_col = [c for c in df.columns if "Debit" in str(c)][0]
    raw = df[[ym, debit_col]].dropna()
    ts = pd.to_datetime(raw[ym].astype(str) + "-01", errors="coerce")
    s = pd.Series(raw[debit_col].astype(float).values, index=ts)
    s = s.groupby(s.index).last().sort_index()
    s.index = s.index.to_period("M").to_timestamp(how="end").normalize()
    return s.loc[(s.index >= START) & (s.index <= END)]


def _fetch_sp500_monthly() -> pd.Series:
    tkr = yf.Ticker("^GSPC")
    hist = tkr.history(start=START, end=END, auto_adjust=False, actions=False)
    if hist.empty:
        raise RuntimeError("No S&P 500 data returned from Yahoo Finance (^GSPC).")
    px = hist["Close"].sort_index()
    if isinstance(px.index, pd.DatetimeIndex) and px.index.tz is not None:
        px.index = pd.to_datetime(px.index.date)
    monthly = px.resample("ME").last()
    monthly.index = monthly.index.normalize()
    return monthly.astype(float)


def main() -> None:
    print("Fetching FRED M2 / CPI / PPI, FINRA margin debit, and S&P 500 levels...")
    frame = pd.DataFrame(
        {
            "m2": _fetch_fred_monthly("M2SL"),
            "cpi": _fetch_fred_monthly("CPIAUCSL"),
            "ppi": _fetch_fred_monthly("PPIACO"),
            "margin_debit": _fetch_margin_debit(),
            "sp500": _fetch_sp500_monthly(),
        }
    ).sort_index()
    frame = frame.loc[(frame.index >= START) & (frame.index <= END)].dropna(how="all")
    if frame.empty:
        raise RuntimeError("No observations fetched; refusing to overwrite data/series.csv.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame.index.name = "date"
    frame.to_csv(SERIES_CSV)
    PULLED_STAMP.write_text(date.today().isoformat() + "\n", encoding="utf-8")
    print(f"Wrote {SERIES_CSV} with {len(frame)} monthly rows "
          f"({frame.index.min():%Y-%m} to {frame.index.max():%Y-%m}).")
    print("Done. Now run `make` to re-render the charts.")


if __name__ == "__main__":
    main()
