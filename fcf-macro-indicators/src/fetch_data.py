#!/usr/bin/env python3
"""Network step (`make data`): download every source series and write data/series.csv.

Sources:
  - Free cash flow, per company   -- SEC EDGAR XBRL company facts (OCF - CapEx)
  - Money supply (M2)             -- FRED M2SL           (monthly)
  - Treasury yields, by term      -- FRED DGS3MO/2/10/30 (daily)
  - S&P 500 index level           -- yfinance (^GSPC)    (daily)

Everything is aligned onto one **calendar-quarter-end** grid, because free cash
flow is only reported quarterly -- it is the coarsest series and sets the grid.

FCF is reconstructed from each company's SEC XBRL filings as quarterly operating
cash flow minus capital expenditure, back to the ~2009 start of the XBRL mandate
-- far deeper than the ~5 quarters yfinance exposes. Cash-flow statements are
filed year-to-date (Q2 = 6 months, Q3 = 9 months, and Q4 is never filed alone),
so discrete quarters are recovered by differencing within each fiscal year.

The result is committed to the repo so that `make` (plot_fcf_macro.py) renders
offline and reproducibly. Re-run with `make data` for fresher numbers.

SEC asks every automated caller to identify itself in the User-Agent (requests
without one get 403). Set SEC_USER_AGENT to e.g. "my-app you@example.com".
"""

from __future__ import annotations

import argparse
import io
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SERIES_CSV = DATA_DIR / "series.csv"
PULLED_STAMP = DATA_DIR / "generated_at.txt"
# Records where the committed FCF numbers came from, so the chart footer can
# attribute them accurately (read back by plot_fcf_macro.py). Written here.
FCF_SOURCE_FILE = DATA_DIR / "fcf_source.txt"
FCF_SOURCE = ("Company free cash flow (OCF - CapEx) from SEC EDGAR XBRL"
              "|https://www.sec.gov/edgar/sec-api-documentation")

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

# XBRL data begins ~2009 (the SEC mandate phased in 2009-2011); the macro series
# on FRED/Yahoo go back decades, so this start is set by FCF availability.
START = pd.Timestamp("2009-01-01")
END = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)

# --- SEC EDGAR ---------------------------------------------------------------
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"
# SEC requires a descriptive User-Agent with contact info; a library default gets
# a 403. It is mandatory and kept OUT of the committed repo -- supply it at run
# time via this env var (see _require_sec_user_agent).
SEC_USER_AGENT_ENV = "SEC_USER_AGENT"
# Operating-cash-flow XBRL tags, tried in order (filers differ / rename tags).
OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]
# Capital-expenditure tags, reported as a positive outflow -> subtract from OCF.
CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
]
# Cumulative year-to-date length (months) of each fiscal period on a cash-flow
# statement: Q1 = 3, Q2 = 6 (H1), Q3 = 9 (9M), FY = 12. Q4 is never filed alone.
_FP_MONTHS = {"Q1": 3, "Q2": 6, "Q3": 9, "FY": 12}
# Ordered (period, previous-period) pairs used to difference YTD into discrete
# quarters: Q1 as-is, Q2 = H1 - Q1, Q3 = 9M - H1, Q4 = FY - 9M.
_FP_PREV = [("Q1", None), ("Q2", "Q1"), ("Q3", "Q2"), ("FY", "Q3")]


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


def _require_sec_user_agent() -> str:
    """SEC contact string from the environment, or a hard failure. Required: SEC
    rejects callers that don't identify themselves (403), so refuse to proceed
    rather than send a placeholder."""
    ua = os.environ.get(SEC_USER_AGENT_ENV, "").strip()
    if not ua:
        raise SystemExit(
            f"{SEC_USER_AGENT_ENV} is not set. SEC EDGAR requires every automated "
            "caller to identify itself with contact info (unidentified requests get "
            "a 403), so this fetch will not run without it.\n"
            "Set it and re-run, e.g.:\n"
            f'    {SEC_USER_AGENT_ENV}="fcf-macro-indicators you@example.com" make data'
        )
    return ua


def _sec_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _require_sec_user_agent(),
                      "Accept-Encoding": "gzip, deflate"})
    return s


def _load_ticker_cik_map(session: requests.Session) -> dict[str, int]:
    """Ticker -> CIK from SEC's published ticker directory."""
    r = session.get(SEC_TICKERS_URL, timeout=120)
    r.raise_for_status()
    return {str(row["ticker"]).upper(): int(row["cik_str"]) for row in r.json().values()}


def _discrete_quarterly(facts: list[dict]) -> pd.Series:
    """Cumulative YTD cash-flow facts -> discrete per-quarter values indexed by
    calendar-quarter-end.

    Cash-flow-statement concepts are only ever reported year-to-date, so within
    each fiscal year we difference the cumulative legs (Q2 = H1 - Q1, and so on).
    A fiscal year missing a leg simply omits the quarters that depend on it. When
    the same period is restated across filings, the latest-filed value wins.
    """
    rows = []
    for f in facts or []:
        if f.get("val") is None or "start" not in f or "end" not in f:
            continue
        fp = f.get("fp")
        if fp not in _FP_MONTHS:
            continue
        start, end = pd.Timestamp(f["start"]), pd.Timestamp(f["end"])
        months = (end - start).days / 30.4
        if abs(months - _FP_MONTHS[fp]) > 1.2:
            continue  # duration doesn't match the claimed fiscal period -- skip
        rows.append({"fy": f.get("fy"), "fp": fp, "end": end,
                     "filed": f.get("filed", ""), "val": float(f["val"])})
    if not rows:
        return pd.Series(dtype=float)

    df = pd.DataFrame(rows).sort_values("filed").drop_duplicates(["fy", "fp"], keep="last")
    out: dict[pd.Timestamp, float] = {}
    for _fy, g in df.groupby("fy"):
        cum = {r.fp: (r.val, r.end) for r in g.itertuples()}
        for fp, prev in _FP_PREV:
            if fp not in cum:
                continue
            val, end = cum[fp]
            if prev is not None:
                if prev not in cum:
                    continue  # can't difference without the earlier cumulative leg
                val = val - cum[prev][0]
            out[end.to_period("Q").to_timestamp(how="end").normalize()] = val
    return pd.Series(out).sort_index()


def _pick_concept(session: requests.Session, cik: int, tags: list[str]) -> pd.Series:
    """First tag (in preference order) that yields discrete quarterly values."""
    for tag in tags:
        url = SEC_CONCEPT_URL.format(cik=cik, tag=tag)
        r = session.get(url, timeout=120)
        time.sleep(0.15)  # SEC fair-use: stay well under 10 requests/second
        if r.status_code == 404:
            continue  # this filer never reported this tag
        r.raise_for_status()
        series = _discrete_quarterly(r.json().get("units", {}).get("USD", []))
        if not series.empty:
            return series
    return pd.Series(dtype=float)


def _fetch_company_fcf(session: requests.Session, ticker: str, cik_map: dict[str, int]) -> pd.Series:
    """Quarterly free cash flow (OCF - CapEx) for one ticker from SEC XBRL."""
    cik = cik_map.get(ticker.upper())
    if cik is None:
        raise RuntimeError(f"{ticker}: no CIK in SEC ticker directory (US filer only?).")
    ocf = _pick_concept(session, cik, OCF_TAGS)
    capex = _pick_concept(session, cik, CAPEX_TAGS)
    if ocf.empty or capex.empty:
        raise RuntimeError(f"{ticker}: missing operating-cash-flow or CapEx XBRL facts.")
    fcf = (ocf - capex).dropna()  # aligned on shared calendar-quarter-ends
    fcf = fcf.loc[(fcf.index >= START) & (fcf.index <= END)]
    if fcf.empty:
        raise RuntimeError(f"{ticker}: no overlapping OCF and CapEx quarters.")
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

    # Fail fast if the SEC identifier is missing, before spending any time on the
    # macro fetches -- the FCF pull can't succeed without it.
    _require_sec_user_agent()

    print(f"Fetching M2, the {'/'.join(YIELD_SERIES)} yield curve, S&P 500, "
          f"and SEC EDGAR FCF for {', '.join(tickers)}...")

    columns: dict[str, pd.Series] = {"m2": _fetch_fred_quarterly("M2SL")}
    for fred_id, col in YIELD_SERIES.items():
        columns[col] = _fetch_fred_quarterly(fred_id)
    columns["sp500"] = _fetch_sp500_quarterly()

    session = _sec_session()
    cik_map = _load_ticker_cik_map(session)
    for ticker in tickers:
        try:
            columns[f"fcf_{ticker}"] = _fetch_company_fcf(session, ticker, cik_map)
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
    FCF_SOURCE_FILE.write_text(FCF_SOURCE + "\n", encoding="utf-8")

    fcf_cols = [c for c in frame.columns if c.startswith("fcf_")]
    print(f"Wrote {SERIES_CSV} with {len(frame)} quarterly rows "
          f"({frame.index.min():%Y-%m} to {frame.index.max():%Y-%m}) "
          f"and {len(fcf_cols)} FCF series.")
    print("Done. Now run `make` to re-render the charts.")


if __name__ == "__main__":
    main()
