# US & Canada government bond yield curves

Compare nominal US Treasury and Government of Canada bill and bond yields at 1, 2, 3 and 6 months,
then 1, 2, 3, 5, 7 and 10 years and the long end. Latest always uses each country's most recent available trading observation.
The newest date appears above the chart; exact observation dates for all plotted
curves and overnight references are listed in the source disclosure.

The US and Canada have separate plots, side by side on desktop and stacked on
mobile. They share the maturity and yield scales and the historical-offset
controls. Hover tooltips show only the country being inspected, and keyboard
inspection works independently in either plot.

The horizontal axis uses a labelled logarithmic maturity scale to keep the
short-term points readable. The vertical axis shows annual yield in percent
on one shared scale, starting at 0%. Hover or tap for exact yields and
a dot highlighting the nearest series. Arrow keys step through maturities,
Home/End jump to the edges, and Escape dismisses the tooltip. Values are also announced through a screen reader status region.
Dashed horizontal lines show only the latest available US SOFR and Canadian
CORRA. Their names and values appear in the tooltip. The cards below show each
country's latest 10Y minus 2Y slope in basis points.

Latest curves are always shown. Toggle multiple historical overlays using
relative offsets: −1m, −3m, −6m, −1y, −2y, −5y and −10y. The initial view shows
Latest, −1y and −5y. Every yield curve uses the same solid line style. Progressively
lighter shades distinguish older dates within each country's color family.
Tooltips and controls use relative labels; exact observation dates are listed
in the source disclosure.

Offsets are measured from the newest country curve date. Each country uses its
latest available observation on or before the target day. Calendar-month
subtraction clamps to month end, and weekends and holidays resolve backward.
Missing countries and tenors are labelled unavailable. Only the latest overnight
rate for each country is shown, independently of the selected curve offsets.
The embedded official history supports the controls offline. Run make data to
reconstruct the snapshot from current official history.

## Definitions and limits

US rates are fitted par yields at constant maturities. Canadian rates are
mid-market closing yields on selected benchmark bonds. Their actual maturities
can differ from the stated terms. Canada's long-term benchmark is positioned at
30 years and marked with an asterisk; the US point is a 30-year par yield.
SOFR and CORRA are overnight secured funding rates. Their horizontal reference
lines are separate from the maturity curve and use each rate’s latest available effective date.

These series have different construction and currency conventions, so the
difference between them also reflects those conventions.

The chart includes daily Canadian treasury bill yields from the Bank of Canada
money-market feed and US par yields at the same tenors. Inflation-linked bonds
are excluded. Lines connect observations; inspection
snaps to published tenor points. One basis point is 0.01 percentage points.

## Commands

```sh
make           # offline build from data/curves.json
make test      # offline parser, alignment, validation and publication tests
make data      # rebuild official history from 1990 onward, then rebuild the page
make open      # open output/us-canada-yield-curves.html
make snapshots # capture desktop and mobile review images with an installed browser
```

`make deps` uses the repository's shared locked environment. Browser setup is
explicit through `make snapshot-browser`. The project uses requests through the
shared HTTP helper and standard-library XML parsing; no new dependencies.

Each explicit refresh downloads the official history from 1990 onward and
atomically replaces data/curves.json after all four required datasets validate.
The local snapshot supports offline builds. Source corrections, missing values
and removed observations are reflected directly on refresh. Failed requests or
validation retain the previous complete snapshot, and identical normalized
content preserves bytes, retrieval timestamp and mtime.

A refresh requires a complete common curve date no more than 14 days old
before publication. The interactive plot uses the latest observation available
for each country, preserving gaps in any partial curve. Historical partial curves are retained with null for unavailable
maturities. Overnight history is stored separately by effective observation
date. The page embeds the official history for offline date selection.

All chart styles, scripts and data are embedded in the output HTML. The yield
curve's maturity scale is a local adapter; page styles, tooltips, point
highlights, JSON embedding, atomic publication and snapshot capture are shared.

## Historical coverage

Run make data to reconstruct the snapshot. For a shorter history, invoke
src/fetch_data.py with --start-date YYYY-MM-DD. US annual feeds are requested
with at most three requests in flight. The requested range replaces the local
snapshot in full.

US maturities have different start dates and gaps. In particular, the 2-month
series begins in October 2018, and the 30-year series has a gap during
2002–2006. The currently used Canadian daily series begin in 2001; the import
retains whatever each requested series actually returns. SOFR begins in April
2018, while CORRA has a longer history and a methodology change in June 2020.
The stored backfill currently contains US curves from January 2, 1990,
Canadian curves from January 2, 2001, SOFR from April 2, 2018, and CORRA from
August 12, 1997.
The snapshot’s coverage object records first/last dates and observation counts
for every country/maturity and overnight rate. A missing maturity is never
interpolated or filled from another trading date.

## Sources

- [New York Fed SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr/)
- [Bank of Canada CORRA](https://www.bankofcanada.ca/rates/interest-rates/corra/)

- [Bank of Canada daily money-market yields](https://www.bankofcanada.ca/rates/interest-rates/money-market-yields/)

- [US Treasury daily par yield curve rates](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve)
- [US Treasury XML feeds](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/interest-rate-xml-files)
- [Bank of Canada selected bond yields](https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/)
- [Bank of Canada Valet API](https://www.bankofcanada.ca/valet/docs)

Canadian series identifiers and US XML field names are listed in
`src/fetch_data.py`. The initial snapshot and retrieval date are recorded in
`data/curves.json`. Review images live under `tests/snapshots/`.
