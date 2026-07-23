#!/usr/bin/env python3
"""Network step (`make data`): download every source series and write data/series.csv.

Sources:
  - Free cash flow, per company   -- SEC EDGAR XBRL company facts (OCF - CapEx)
  - Money supply (M2)             -- FRED M2SL           (monthly, via pandas-datareader)
  - Treasury yields, by term      -- FRED DGS3MO/2/10/30 (daily,   via pandas-datareader)
  - S&P 500 index level           -- yfinance (^GSPC)    (daily)

Everything is aligned onto one **calendar-quarter-end** grid, because free cash
flow is only reported quarterly -- it is the coarsest series and sets the grid.

FCF is reconstructed from each company's SEC XBRL filings as quarterly operating
cash flow minus capital expenditure, back to the ~2009 start of the XBRL mandate
-- far deeper than the ~5 quarters a scraped-quote source exposes. Cash-flow statements are
filed year-to-date (Q2 = 6 months, Q3 = 9 months, and Q4 is never filed alone),
so discrete quarters are recovered by differencing within each fiscal year.

The result is committed to the repo so that `make` (plot_fcf_macro.py) renders
offline and reproducibly. Re-run with `make data` for fresher numbers.

SEC asks every automated caller to identify itself in the User-Agent (requests
without one get 403). Set SEC_USER_AGENT to e.g. "my-app you@example.com".
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_datareader.data as web
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

# FRED series id -> our column name. M2 money supply plus the Treasury term
# structure (constant-maturity nominal yields, short end -> long end).
FRED_SERIES = {
    "M2SL": "m2",
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
# Cash & cash-equivalents tags -- a balance-sheet *instant* (point-in-time)
# value, not a flow, so it is taken as-reported at each period end (no YTD
# differencing). Plain cash & equivalents first, then the variant that folds in
# restricted cash, as a fallback for filers that only report the combined line.
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]
# A discrete quarter is ~3 months; allow a wide tolerance so a 52/53-week fiscal
# quarter (~2.9-3.2 months) still counts, while a half-year leg (~6 months) never
# does. Used both to spot a natively-reported quarter and to confirm two YTD legs
# are exactly one quarter apart before differencing them.
_ONE_Q_LOW, _ONE_Q_HIGH = 2.0, 4.0


def _to_quarter_end(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Snap timestamps to their *containing* calendar quarter-end. Used to bucket
    dense daily series (FRED/Yahoo) into quarters -- a May observation belongs to
    Q2, so the containing quarter is what's wanted here."""
    return idx.to_period("Q").to_timestamp(how="end").normalize()


def _nearest_quarter_end(idx) -> pd.DatetimeIndex:
    """Snap reported-period end dates to the *nearest* calendar quarter-end. Nearest
    (not containing) so a 52/53-week fiscal calendar whose quarter boundary drifts a
    few days across a calendar-quarter line -- e.g. Apple's fiscal Q2 ending
    2017-04-01 -- lands on the quarter it economically represents (2017-03-31)
    instead of jumping a quarter forward and leaving the real quarter empty."""
    idx = pd.DatetimeIndex(idx)
    this_qe = idx.to_period("Q").to_timestamp(how="end").normalize()
    prev_qe = (idx.to_period("Q") - 1).to_timestamp(how="end").normalize()
    nearer_prev = np.abs((idx - prev_qe).values) < np.abs((this_qe - idx).values)
    return pd.DatetimeIndex(np.where(nearer_prev, prev_qe.values, this_qe.values))


def _snap_quarter_end(ts: pd.Timestamp) -> pd.Timestamp:
    """`_nearest_quarter_end` for a single timestamp."""
    return _nearest_quarter_end([ts])[0]


def _quarter_last(frame: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Last available observation in each calendar quarter. Forward-fills first so
    a quarter-end falling on a weekend/holiday (NaN on FRED daily series) still
    carries the prior business day's value."""
    obj = frame.sort_index().ffill()
    idx = pd.DatetimeIndex(obj.index)
    return obj.groupby(_to_quarter_end(idx)).last()


def _fetch_fred_quarterly() -> pd.DataFrame:
    """M2 and the Treasury curve from FRED (keyless), one column per series,
    reduced to quarter-end values."""
    raw = web.DataReader(list(FRED_SERIES), "fred", START, END)
    raw = raw.rename(columns=FRED_SERIES)
    return _quarter_last(raw).astype(float)


def _fetch_sp500_quarterly() -> pd.Series:
    """S&P 500 quarter-end close from Yahoo Finance (^GSPC) via yfinance -- the
    keyless, deep-history source that reliably serves the index level."""
    hist = yf.Ticker("^GSPC").history(start=START, end=END, auto_adjust=False, actions=False)
    if hist.empty:
        raise RuntimeError("No S&P 500 data returned from Yahoo Finance (^GSPC).")
    px = hist["Close"].sort_index()
    if isinstance(px.index, pd.DatetimeIndex) and px.index.tz is not None:
        px.index = pd.to_datetime(px.index.date)
    return _quarter_last(px).astype(float)


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
    """Cash-flow-statement facts -> discrete per-quarter values indexed by
    calendar-quarter-end.

    Two kinds of facts become discrete quarters:
      * a fact whose own duration is ~one quarter (some filers, e.g. Amazon, report
        a native three-month leg) is a discrete quarter as reported; and
      * cumulative year-to-date legs that share a fiscal-year start are differenced
        pairwise (H1 - Q1, 9M - H1, FY - 9M), each difference landing on the later
        leg's quarter-end -- but only when the two legs are exactly one quarter
        apart, so a missing leg never fabricates a value.

    Periods are grouped by what they actually cover (`start`/`end`), NOT by SEC's
    `fy`/`fp` labels: those describe the *filing*, so a prior-year comparative
    carried into a later filing is mislabelled and would collide with the real
    period. On identical periods the latest-filed value wins (then the preferred
    tag), which also absorbs restatements and cross-tag overlaps.
    """
    rows = []
    for f in facts or []:
        if f.get("val") is None or "start" not in f or "end" not in f:
            continue
        start, end = pd.Timestamp(f["start"]), pd.Timestamp(f["end"])
        months = (end - start).days / 30.4
        if months < 1:
            continue
        rows.append({"start": start, "end": end, "months": months,
                     "filed": f.get("filed", ""), "prio": f.get("_prio", 0),
                     "val": float(f["val"])})
    if not rows:
        return pd.Series(dtype=float)

    # keep='last' after this sort keeps the latest-filed fact for each period, and
    # among equally-filed facts the preferred (lowest-index) tag.
    df = (pd.DataFrame(rows)
          .sort_values(["filed", "prio"], ascending=[True, False])
          .drop_duplicates(["start", "end"], keep="last"))

    out: dict[pd.Timestamp, float] = {}
    # Natively-reported one-quarter legs are discrete quarters as-is.
    for r in df.itertuples():
        if _ONE_Q_LOW <= r.months <= _ONE_Q_HIGH:
            out[_snap_quarter_end(r.end)] = r.val
    # Difference consecutive YTD legs sharing a fiscal-year start; fill only the
    # quarters a native leg didn't already cover.
    for _start, g in df.sort_values("end").groupby("start"):
        prev = None
        for r in g.itertuples():
            if prev is not None and _ONE_Q_LOW <= (r.end - prev.end).days / 30.4 <= _ONE_Q_HIGH:
                out.setdefault(_snap_quarter_end(r.end), r.val - prev.val)
            prev = r
    return pd.Series(out).sort_index()


def _instant_quarterly(facts: list[dict]) -> pd.Series:
    """Balance-sheet *instant* facts (e.g. cash) -> the reported balance at each
    calendar-quarter-end. No differencing: each fact is a point-in-time value at
    its `end` date. Restatements/comparatives dedupe to the latest-filed value,
    and if two report dates land in one calendar quarter the later one wins."""
    rows = []
    for f in facts or []:
        if f.get("val") is None or "end" not in f:
            continue
        rows.append({"end": pd.Timestamp(f["end"]), "filed": f.get("filed", ""),
                     "prio": f.get("_prio", 0), "val": float(f["val"])})
    if not rows:
        return pd.Series(dtype=float)
    df = (pd.DataFrame(rows)
          .sort_values(["filed", "prio"], ascending=[True, False])
          .drop_duplicates("end", keep="last"))
    df["qe"] = _nearest_quarter_end(pd.DatetimeIndex(df["end"]))
    df = df.sort_values("end").drop_duplicates("qe", keep="last")
    return df.set_index("qe")["val"].sort_index().astype(float)


def _concept_facts(session: requests.Session, cik: int, tags: list[str]) -> list[dict]:
    """Raw USD facts for a concept, MERGED across all its candidate tags. Filers
    rename XBRL tags mid-history (Apple's capex ran under PaymentsToAcquire-
    ProductiveAssets, then ...PropertyPlantAndEquipment; Amazon the reverse), so no
    single tag spans the full timeline -- picking the first non-empty tag silently
    truncates the series. Unioning every tag's facts and letting the downstream
    per-period dedup keep the latest-filed value recovers the whole history. Each
    fact is stamped with `_prio` (its tag's preference rank, 0 = most preferred),
    used only to break dedup ties on an identical period."""
    facts: list[dict] = []
    for prio, tag in enumerate(tags):
        url = SEC_CONCEPT_URL.format(cik=cik, tag=tag)
        r = session.get(url, timeout=120)
        time.sleep(0.15)  # SEC fair-use: stay well under 10 requests/second
        if r.status_code == 404:
            continue  # this filer never reported under this tag
        r.raise_for_status()
        for f in r.json().get("units", {}).get("USD", []):
            facts.append({**f, "_prio": prio})
    return facts


def _fetch_company_fcf(session: requests.Session, ticker: str, cik_map: dict[str, int]) -> pd.Series:
    """Quarterly free cash flow (OCF - CapEx) for one ticker from SEC XBRL."""
    cik = cik_map.get(ticker.upper())
    if cik is None:
        raise RuntimeError(f"{ticker}: no CIK in SEC ticker directory (US filer only?).")
    ocf = _discrete_quarterly(_concept_facts(session, cik, OCF_TAGS))
    capex = _discrete_quarterly(_concept_facts(session, cik, CAPEX_TAGS))
    if ocf.empty or capex.empty:
        raise RuntimeError(f"{ticker}: missing operating-cash-flow or CapEx XBRL facts.")
    fcf = (ocf - capex).dropna()  # aligned on shared calendar-quarter-ends
    fcf = fcf.loc[(fcf.index >= START) & (fcf.index <= END)]
    if fcf.empty:
        raise RuntimeError(f"{ticker}: no overlapping OCF and CapEx quarters.")
    return fcf.astype(float)


def _fetch_company_cash(session: requests.Session, ticker: str, cik_map: dict[str, int]) -> pd.Series:
    """Quarter-end cash & cash equivalents balance for one ticker from SEC XBRL."""
    cik = cik_map.get(ticker.upper())
    if cik is None:
        raise RuntimeError(f"{ticker}: no CIK in SEC ticker directory (US filer only?).")
    cash = _instant_quarterly(_concept_facts(session, cik, CASH_TAGS))
    cash = cash.loc[(cash.index >= START) & (cash.index <= END)]
    if cash.empty:
        raise RuntimeError(f"{ticker}: no cash & equivalents XBRL facts.")
    return cash.astype(float)


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

    print("Fetching M2 + the Treasury curve (FRED), the S&P 500 (Yahoo), and SEC "
          f"EDGAR free cash flow + cash balances for {', '.join(tickers)}...")

    columns: dict[str, pd.Series] = dict(_fetch_fred_quarterly().items())
    columns["sp500"] = _fetch_sp500_quarterly()

    session = _sec_session()
    cik_map = _load_ticker_cik_map(session)
    for ticker in tickers:
        try:
            columns[f"fcf_{ticker}"] = _fetch_company_fcf(session, ticker, cik_map)
        except Exception as exc:  # one bad ticker shouldn't sink the whole pull
            print(f"  WARNING: skipping {ticker} FCF: {exc}")
        try:
            columns[f"cash_{ticker}"] = _fetch_company_cash(session, ticker, cik_map)
        except Exception as exc:
            print(f"  WARNING: skipping {ticker} cash: {exc}")

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
    cash_cols = [c for c in frame.columns if c.startswith("cash_")]
    print(f"Wrote {SERIES_CSV} with {len(frame)} quarterly rows "
          f"({frame.index.min():%Y-%m} to {frame.index.max():%Y-%m}), "
          f"{len(fcf_cols)} FCF and {len(cash_cols)} cash series.")
    print("Done. Now run `make` to re-render the charts.")


if __name__ == "__main__":
    main()
