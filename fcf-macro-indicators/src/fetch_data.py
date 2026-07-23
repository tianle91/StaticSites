#!/usr/bin/env python3
"""Network step (`make data`): download every source series and write data/series.csv.

Sources:
  - Free cash flow, per company   -- yfinance quarterly cash-flow statements
  - Money supply (M2)             -- FRED M2SL           (monthly)
  - Treasury yields, by term      -- FRED DGS3MO/2/10/30 (daily)
  - S&P 500 index level           -- yfinance (^GSPC)    (daily)

Everything is aligned onto one **calendar-quarter-end** grid, because free cash
flow is only reported quarterly -- it is the coarsest series and sets the grid.
The result is committed to the repo so that `make` (plot_fcf_macro.py) renders
offline and reproducibly. Re-run with `make data` for fresher numbers.

The window is deliberately short: yfinance only returns roughly the last five
quarters of cash-flow statements per ticker, so there is no point pulling decades
of macro history that the FCF series can never line up against. See README.md.
"""

from __future__ import annotations

import argparse
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
# Present when the committed CSV is the labeled sample (see data/README.md); a
# real fetch here removes it so the render stops being watermarked.
SAMPLE_SENTINEL = DATA_DIR / "SAMPLE_DATA.txt"

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

# The Treasury term structure we chart, FRED id -> column name. Constant-maturity
# nominal yields at the short end, belly, and long end of the curve.
YIELD_SERIES = {
    "DGS3MO": "dgs3mo",
    "DGS2": "dgs2",
    "DGS10": "dgs10",
    "DGS30": "dgs30",
}

# Default basket: a handful of large, cash-generative US companies. Their summed
# quarterly FCF is the "aggregate FCF" line the chart rebases. Override with
# --tickers on the command line.
DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

# Macro history only needs to cover the (short) FCF window plus a little context;
# quarterly resampling keeps the committed CSV tiny regardless.
START = pd.Timestamp("2015-01-01")
END = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)


def _to_quarter_end(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Snap any timestamps to their calendar-quarter-end, so fiscal-quarter report
    dates (e.g. 2024-06-29) and month-ends align on one grid (2024-06-30)."""
    return idx.to_period("Q").to_timestamp(how="end").normalize()


def _fetch_fred_quarterly(series_id: str) -> pd.Series:
    """Download a FRED series and take its last observation in each quarter."""
    r = requests.get(FRED_CSV.format(series=series_id), timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content), parse_dates=["observation_date"])
    if series_id not in df.columns:
        raise KeyError(f"Column {series_id} missing from FRED CSV response.")
    s = df.set_index("observation_date")[series_id]
    # FRED marks missing daily values (weekends/holidays) with ".", read as NaN.
    s = pd.to_numeric(s, errors="coerce").dropna().sort_index()
    s = s.loc[(s.index >= START) & (s.index <= END)]
    q = s.groupby(_to_quarter_end(pd.DatetimeIndex(s.index))).last()
    return q.astype(float)


def _fetch_sp500_quarterly() -> pd.Series:
    tkr = yf.Ticker("^GSPC")
    hist = tkr.history(start=START, end=END, auto_adjust=False, actions=False)
    if hist.empty:
        raise RuntimeError("No S&P 500 data returned from Yahoo Finance (^GSPC).")
    px = hist["Close"].sort_index()
    if isinstance(px.index, pd.DatetimeIndex) and px.index.tz is not None:
        px.index = pd.to_datetime(px.index.date)
    q = px.groupby(_to_quarter_end(pd.DatetimeIndex(px.index))).last()
    return q.astype(float)


def _fetch_company_fcf(ticker: str) -> pd.Series:
    """Quarterly free cash flow for one ticker, indexed by calendar-quarter-end.

    yfinance exposes a 'Free Cash Flow' row directly in recent versions; when it
    is absent we reconstruct it as Operating Cash Flow + Capital Expenditure
    (CapEx is reported negative, so the sum is OCF minus capital spending)."""
    cf = yf.Ticker(ticker).quarterly_cashflow
    if cf is None or cf.empty:
        raise RuntimeError(f"No quarterly cash-flow statement returned for {ticker}.")

    def _row(name: str) -> pd.Series | None:
        return cf.loc[name] if name in cf.index else None

    fcf = _row("Free Cash Flow")
    if fcf is None:
        ocf = _row("Operating Cash Flow") or _row("Total Cash From Operating Activities")
        capex = _row("Capital Expenditure") or _row("Capital Expenditures")
        if ocf is None or capex is None:
            raise RuntimeError(f"Cannot derive FCF for {ticker}: rows are {list(cf.index)}")
        fcf = ocf.add(capex, fill_value=0.0)

    fcf = pd.to_numeric(fcf, errors="coerce").dropna().sort_index()
    fcf.index = _to_quarter_end(pd.DatetimeIndex(fcf.index))
    fcf = fcf.groupby(fcf.index).last()
    return fcf.astype(float)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch FCF + macro series into data/series.csv.")
    parser.add_argument(
        "--tickers",
        default=",".join(DEFAULT_TICKERS),
        help="Comma-separated tickers whose quarterly FCF is summed (default: %(default)s).",
    )
    args = parser.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    print(f"Fetching M2, the {'/'.join(YIELD_SERIES)} yield curve, S&P 500, "
          f"and quarterly FCF for {', '.join(tickers)}...")

    columns: dict[str, pd.Series] = {"m2": _fetch_fred_quarterly("M2SL")}
    for fred_id, col in YIELD_SERIES.items():
        columns[col] = _fetch_fred_quarterly(fred_id)
    columns["sp500"] = _fetch_sp500_quarterly()

    for ticker in tickers:
        try:
            columns[f"fcf_{ticker}"] = _fetch_company_fcf(ticker)
        except Exception as exc:  # one bad ticker shouldn't sink the whole pull
            print(f"  WARNING: skipping {ticker}: {exc}")

    if not any(c.startswith("fcf_") for c in columns):
        raise RuntimeError("No FCF series fetched; refusing to overwrite data/series.csv.")

    frame = pd.DataFrame(columns).sort_index()
    frame = frame.loc[(frame.index >= START) & (frame.index <= END)].dropna(how="all")
    if frame.empty:
        raise RuntimeError("No observations fetched; refusing to overwrite data/series.csv.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame.index.name = "date"
    frame.to_csv(SERIES_CSV)
    PULLED_STAMP.write_text(date.today().isoformat() + "\n", encoding="utf-8")
    # This is a real upstream pull, so drop the sample-data watermark sentinel.
    SAMPLE_SENTINEL.unlink(missing_ok=True)

    fcf_cols = [c for c in frame.columns if c.startswith("fcf_")]
    print(f"Wrote {SERIES_CSV} with {len(frame)} quarterly rows "
          f"({frame.index.min():%Y-%m} to {frame.index.max():%Y-%m}) "
          f"and {len(fcf_cols)} FCF series.")
    print("Done. Now run `make` to re-render the charts.")


if __name__ == "__main__":
    main()
