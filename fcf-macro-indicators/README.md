# fcf-macro-indicators

Free cash flow vs. the macro backdrop.

Takes the quarterly **free cash flow** and **cash & cash-equivalents balance** of
a basket of large public companies (Apple, Microsoft, Alphabet, Amazon, Meta by
default), sums each into one basket-aggregate series, and plots them against the
macro variables they are usually discussed alongside — **M2 money supply**, the
**S&P 500**, and the Treasury yield curve at four terms (**3-month, 2-year,
10-year, 30-year**).

The chart is **two panels sharing one x-axis**:

- **Top — levels rebased to 100** at a common anchor quarter (aggregate FCF,
  aggregate cash, M2, S&P 500), so it shows how corporate cash generation and cash
  on hand have moved *relative to* liquidity and equity prices. The basket members
  behind the aggregate lines are named in the subtitle.
- **Bottom — the Treasury curve as raw yields (%)**, not rebased: yields already
  share a natural scale, and rebasing them to a near-zero-rate anchor (the 3-month
  bill was ~0.03% in 2014) would blow that line up into the thousands. Periods when
  the curve is **inverted** (10Y &lt; 2Y — the 2s10s recession signal) are shaded
  as a band across both panels.

![free cash flow vs. M2, the S&P 500, and the Treasury curve](output/fcf-macro-indicators.png)

## Usage

Render both charts from the committed `data/series.csv` (offline):

```sh
make          # build output/fcf-macro-indicators.{html,png} from the committed data/
make open     # build, then open the zoomable chart in a browser
make test     # run the tests
make data     # refetch SEC EDGAR + FRED into data/series.csv (requires internet), then rebuild
```

`uv` creates this project's `.venv` on first run. Targets follow the repo
standard — see the [repo README](../README.md).

`make data` pulls company fundamentals from SEC EDGAR, which requires every
caller to identify itself. **`SEC_USER_AGENT` is mandatory** — `make data` fails
immediately if it is unset (SEC returns a 403 to unidentified requests):

```sh
SEC_USER_AGENT="fcf-macro-indicators you@example.com" make data
```

The scripts can also be driven directly — pick the anchor quarter, or a different
basket via `make data`:

```sh
.venv/bin/python src/plot_fcf_macro.py -o output/chart.html --rebase-date 2015-03-31
SEC_USER_AGENT="fcf-macro-indicators you@example.com" \
  .venv/bin/python src/fetch_data.py --tickers AAPL,MSFT,NVDA,GOOGL
```

## Zoomable chart

`make` writes a self-contained page (plotly from CDN). Open it in a browser and:

- **drag** a region to zoom, **scroll** to zoom, **double-click** to reset
- use the **range slider** under the axis, or the **3y / 5y / 10y / All** buttons
- **click anywhere on the chart** to re-anchor the top panel: the click snaps to
  the nearest quarter, a dotted marker line moves to it, and the level series
  re-rebase to 100 there — live, client-side, no rebuild. `--rebase-date` sets the
  initial anchor
- toggle **Levels: Linear / Log** on the top panel's y-axis (log helps when a
  decade of M2/S&P growth compresses the recent range)
- click legend entries to hide or isolate a series; hover for aligned values

## Layout

| Path | What it is |
| --- | --- |
| `src/fetch_data.py` | Network step (`make data`): pulls FCF + macro series into `data/series.csv` |
| `src/plot_fcf_macro.py` | Offline build: renders `output/fcf-macro-indicators.{html,png}` from the CSV |
| `data/series.csv` | Committed quarterly grid: `m2`, `sp500`, `dgs3mo/2/10/30`, and `fcf_<TICKER>` + `cash_<TICKER>` columns per basket member |
| `data/fcf_source.txt` | Provenance marker (`label\|url`) recording where the committed FCF came from; drives the chart's source footer |
| `output/fcf-macro-indicators.html` | Zoomable chart (committed so it works without a build) |
| `output/fcf-macro-indicators.png` | Static chart |

## Data sources

- **Free cash flow** — reconstructed from each company's
  [SEC EDGAR XBRL filings](https://www.sec.gov/edgar/sec-api-documentation) as
  quarterly **Operating Cash Flow − Capital Expenditure**
  (`NetCashProvidedByUsedInOperatingActivities` −
  `PaymentsToAcquirePropertyPlantAndEquipment`), back to the ~2009 start of the
  XBRL mandate. Each concept's candidate tags are **merged across the full
  history**, because filers rename tags over time (Amazon's capex moved from
  `PaymentsToAcquirePropertyPlantAndEquipment` to `PaymentsToAcquireProductiveAssets`
  in 2017; Apple the reverse) — using only the first tag would truncate the series
  to one era. Keyless; SEC only asks for a `User-Agent` with contact info.
- **Cash & cash equivalents** — the quarter-end balance from the same SEC filings
  (`CashAndCashEquivalentsAtCarryingValue`, falling back to the
  restricted-cash-inclusive line). A balance-sheet *instant*, taken as-reported.
- **M2 money supply** — [FRED `M2SL`](https://fred.stlouisfed.org/series/M2SL),
  via `pandas-datareader` (keyless).
- **Treasury yields** — FRED constant-maturity series
  [`DGS3MO`](https://fred.stlouisfed.org/series/DGS3MO),
  [`DGS2`](https://fred.stlouisfed.org/series/DGS2),
  [`DGS10`](https://fred.stlouisfed.org/series/DGS10),
  [`DGS30`](https://fred.stlouisfed.org/series/DGS30), via `pandas-datareader`.
- **S&P 500** — level via [Yahoo Finance `^GSPC`](https://finance.yahoo.com/quote/%5EGSPC)
  (`yfinance`); keyless with deep history.

`make data` writes all of them into `data/series.csv`, which is committed so
`make` renders offline and reproducibly.

## Caveats

- **Quarterly reconstruction (FCF only).** SEC cash-flow statements are usually
  filed year-to-date (Q2 = 6 months, Q3 = 9 months, and Q4 is never filed on its
  own), so discrete quarters are recovered by differencing consecutive legs that
  share a fiscal-year start (Q2 = H1 − Q1, … , Q4 = FY − 9M). Where a filer instead
  reports a native three-month leg (Amazon does), it is taken directly. Legs are
  matched by the period they actually cover, not by SEC's `fy`/`fp` labels — those
  describe the *filing*, so prior-year comparatives are mislabelled. A fiscal year
  missing a leg omits the quarters that depend on it.
- **Cash is a level, FCF is a flow.** Cash & equivalents is a balance-sheet
  *instant* — the amount on hand at the quarter-end date, taken as-reported with
  no differencing — whereas FCF is generated *during* the quarter. Both are among
  the top-panel level series rebased to 100, so the chart compares their growth,
  not their magnitudes.
- **Restatements → latest-filed.** When a period is restated across filings the
  most recently filed value is used, so the series reflects restated figures, not
  as-first-reported. It is not a strict point-in-time (as-filed) dataset.
- **US filers only, known tags.** EDGAR XBRL covers US-domestic filers (10-K/10-Q)
  from ~2009; the fetcher merges a short list of GAAP tags per concept, so a
  company reporting capex/OCF under a tag outside that list would be missed.
- **Yields shown raw; inversion is quarter-sampled.** The Treasury series are
  plotted as raw percentages in their own panel (not rebased), so the curve reads
  in points of yield. Inversion shading is evaluated at quarter-ends, so a brief
  inversion that opens and closes between two quarter-ends (e.g. the short August
  2019 2s10s dip) can fall through the sampling.
- **Aggregate composition.** Each aggregate (FCF and cash) is summed only over
  quarters where *every* basket member reports, so a line never jumps because a
  company entered or left the sample. Fiscal-quarter report dates are snapped to the
  nearest calendar-quarter-end to share one grid; companies with off-calendar
  fiscal quarters (e.g. Microsoft) are aligned to calendar quarters, not their
  own fiscal ones.
- **FCF is lumpy and seasonal.** A single quarter's FCF swings with working
  capital, buyback-driven capex timing, and seasonality; it is not deseasonalised.
- Not investment advice.
