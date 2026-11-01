# Canada Mortgage Stress

A self-contained time-series dashboard for CMHC mortgage arrears, lender risk,
and Toronto-area house prices. Choose a metric, date range and reported/indexed
view; toggle series, inspect observations and export all records as CSV. An
optional second chart shows prices on the same date axis, with a separate scale.
The HTML runs offline without a server, CDN or external JavaScript.

## Available data

- **Provincial mortgage arrears:** quarterly, 1995 Q1–2026 Q2; Quebec, Ontario,
  Alberta and British Columbia. CBA-member bank mortgages, 90+ days overdue.
- **Arrears by lender type:** quarterly, 2020 Q1–2026 Q2; national chartered banks,
  credit unions, other non-bank lenders and mortgage investment entities (MIEs).
- **GTHA MIE arrears:** quarterly, 2023 Q3–2026 Q1; GTHA versus rest of Canada.
  These are **balance-weighted** rates, not the percentage of loans in arrears.
- **Non-mortgage credit delinquencies:** quarterly, 2014 Q1–2026 Q2; national
  HELOC, credit card, auto loan and line-of-credit rates across consumers.
- **Monthly arrears and outlook:** observed January 2021–June 2026, followed by
  the CMHC Fall 2026 forecast through June 2027; Canada and selected provinces.
  Forecasts are dashed and can be hidden. This monthly series is kept separate
  from quarterly provincial figures.
- **Toronto-area prices:** monthly January 2020–September 2026, and annual
  averages 1980–2025. These are nominal TRREB average sale prices, **not HPI**.
  Monthly records are split between legacy report coverage (2020–2023) and
  expanded board coverage (2024 onward). The boundary marks a source-vintage
  break, not the exact date membership changed. Overlapping newer monthly
  revisions take precedence; every monthly observation retains its source URL.

These are the ranges in the committed snapshot, not promises of live coverage.
CMHC's geographic Equifax workbook is another potential extension (e.g. Toronto
CMA history), but is not merged into the CBA provincial series in this version.

## Data gaps and interpretation

**We have enough data for a descriptive dashboard, but not for every claim in
the motivating discussion.** Power-of-sale listings have no verified consistent
public historical series in this project. Active inventory is available in
individual TRREB reports but has not been assembled into a comparable historical
series. Neither the unverified 600+ power-of-sale figure nor a single inventory
snapshot is plotted as a historical series.

Ontario, Toronto CMA, TRREB market area and GTHA are different geographies.
National lender rates and GTHA balance-weighted MIE rates have different coverage
and denominators. Do not equate 11.14% of balances with one in nine loans.

Price averages are sensitive to sales mix, geography changes and revisions.
Older TRREB PDFs use a narrower market coverage; the dashboard does not connect
the monthly lines across that break. The annual series also has changing market
coverage, as TRREB warns. Indexed mode rebases each line independently to its
first visible value; it does not resolve these comparability limits.

Straight chart segments connect published observations; no intervening records
are invented. Quarterly and annual data are not forward-filled or interpolated.
Annual averages conceal monthly troughs, so the long-run series cannot establish
whether house prices bottom before or after peak arrears. Rising arrears alone
are not proof of a future price bottom. A consistently revised resale benchmark
series is still needed for a stronger cycle-timing study.

## Usage

```sh
make system-deps # explicit macOS/Homebrew installation of uv
make deps        # complete locked environment
make             # offline build from committed data
make test        # offline parser, validation and publication tests
make open        # open the HTML
make data        # explicit refresh of every source, then rebuild
make clean       # remove generated HTML
make clean-deps  # remove only environment/stamp; clean-venv is an alias
```

Build within the repository checkout; the Makefile includes
[`../python-project.mk`](../python-project.mk). Homebrew must already be installed
for `system-deps`. On other platforms install uv manually. Python >=3.11 is
managed by uv. No credentials are needed. Existing dependency environments are
reused; incomplete environments fail and require explicit
`make clean-deps && make deps`. Missing or stale lockfiles fail without repair.

## Refresh behavior

`src/fetch_data.py` fetches CMHC's accessible HTML chart tables and TRREB's annual
PDF, latest report page, December 2021/2023/2025 reports and latest report PDF.
`pypdf` layout extraction prevents column reversal in older PDF layouts.
The project reads public reports rather than requiring an MLS login.

All required sources must succeed before one validated `data/series.json` is
replaced atomically. Missing periods, duplicate observations, implausible values,
truncated tables and absent report links fail the refresh. Unchanged normalized
records preserve the file's bytes, retrieval timestamp and mtime. Raw upstream
PDFs are not retained; normalized records and their source URLs are committed.
`make data` also restores a missing HTML output. Tests never hit live sources.

The CMHC parser deliberately requires the **Fall 2026** edition. When that
rolling URL changes editions, refresh fails until definitions, captions and
forecast vintage have been reviewed in the code. TRREB monthly coverage is
validated continuously from January 2020; additional archive reports may be
needed when a new year is no longer covered by the configured reports.
Required-source failures preserve the previous complete dataset and output.

## Layout

- `src/fetch_data.py`: network refresh, parsers and validation.
- `src/build_site.py`: deterministic offline HTML build.
- `src/page.html`, `src/style.css`, `src/app.js`: locally embedded dashboard.
- `data/series.json`: committed observations, definitions and provenance.
- `tests/fixtures/`: short text extracts from the public monthly PDF tables.
- `output/canada-mortgage-stress.html`: generated standalone page, committed.

## Data sources

- [CMHC Residential Mortgage Industry Report, Fall 2026](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-research/research-reports/housing-finance/residential-mortgage-industry-report):
  accessible tables for Figures 1, 3, 7, 8 and 13. Underlying sources include CBA,
  Equifax, regulatory reporting and Statistics Canada's Survey of Non-Bank
  Mortgage Lenders. Source attribution is preserved on the page.
- [TRREB Historic Statistics](https://public.trreb.ca/wp-content/files/market-stats/market-watch/historic.pdf):
  annual average sale prices, with TRREB's changing-market-area caveat.
- [TRREB Market Watch](https://public.trreb.ca/market-data/market-watch/):
  latest report discovery and the notice about expanded PropTx/member-board
  coverage and revised history.
- [December 2021 report](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2112.pdf),
  [December 2023 report](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2312.pdf),
  [December 2025 report](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2512.pdf),
  and [September 2026 report](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2609.pdf):
  monthly average sale-price tables. Copyright Toronto Regional Real Estate Board;
  prices are attributed to TRREB, not presented as CMHC data. The current
  snapshot's exact report URLs are listed in the HTML and JSON.
