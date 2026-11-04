# Ontario arrears & house prices

A single-plot comparison of **Ontario bank mortgage arrears** and **Toronto-area
house prices**. Both series share one calendar axis and one index axis. Each
starts at 100 in the first shared month, so 120 means 20% above that series’
starting value. The tooltip shows the index alongside the original share of
mortgages 90+ days overdue or the average sale price in Canadian dollars.

## Interface

The fixed series are **monthly Ontario bank arrears including the CMHC
forecast** and **monthly Toronto-area average sale prices**. There are no series
selectors or date controls. The plot always shows their full shared history,
with the bounds calculated from the committed observations.

The current shared period is **January 2021–September 2026**. The plot and cursor
clip to those exact month boundaries. Bank observations run through
June 2026, so the displayed dashed forecast covers July–September 2026. Later
forecast months are excluded because corresponding price data are unavailable.

Hover or tap to inspect, or focus the chart and use Left/Right to step through
months (Home/End jump to the window edges). The tooltip labels the exact period of each
nearest published observation, within half the reporting interval. It never
interpolates values or carries a stale series beyond its published coverage.
Definitions and linked sources are in one collapsed section beneath the chart.
The page embeds all data, scripts and styles and works offline.

## Data and limits

- **Ontario monthly bank arrears:** observed January 2021–June 2026; CMHC Fall
  2026 forecast July 2026–June 2027, clipped to shared price coverage. Share of
  CBA-member bank mortgage accounts 90+ days overdue. Arrears and delinquency
  mean the same 90+ day measure here.
- **Toronto-area monthly prices:** January 2020–September 2026 in the source,
  clipped to the shared window. TRREB average sale prices, **not Ontario-wide
  prices** and **not a quality-adjusted HPI**. Sales mix affects price averages.

Monthly prices retain two report vintages: legacy coverage through 2023 and
expanded member-board coverage from the 2024 records used here. Separate paths
in the same price color preserve the break; a vertical dashed line marks it.
The boundary is a source-vintage break, not the exact date membership changed.
Newer overlapping report revisions take precedence. Each monthly record retains
its source URL. Annual history also has changing market coverage and conceals
monthly turning points. These data do not establish an arrears-to-price-bottom
lag or prove that prices have not bottomed.

The source JSON retains the original broader CMHC tables for provenance and
refresh validation. Quarterly bank history, annual prices, GTHA private-lender rates, other
provinces and national consumer-credit series are excluded from the plot. No
power-of-sale or inventory history is presented.

## Visual snapshots

[Desktop (1440 × 900)](tests/snapshots/desktop.jpg) ·
[Mobile (390 × 844)](tests/snapshots/mobile.jpg)

Generate review images of the actual HTML page:

```sh
make snapshot-browser  # explicit headless Chromium setup; repeat after Playwright upgrades
make snapshots         # rebuild from committed data, then capture both views
```

Capture uses a temporary loopback server and fresh light-mode contexts. Mobile
uses touch emulation. All plots, the inspection readout, fonts and responsive
geometry must finish rendering before capture; page errors, external requests
and horizontal overflow fail the command. Both captures must succeed before
existing review images are replaced. These JPEGs show the initial viewport;
longer pages continue below the image. They are visual review references, not
automated pixel comparisons.

The chart pages are self-contained, so capture works offline once the locked
Python dependencies and browser are installed. Browser downloads happen only
through `make snapshot-browser`. Ordinary builds, tests and data refreshes do
not install browsers or capture images. Recapture after visual changes and
commit the reviewed images. On Linux, install Chromium's
[manual system prerequisites](https://playwright.dev/python/docs/browsers#install-system-dependencies)
if needed; the targets do not install OS packages.

Optional browser fixtures check incomplete rendering, moving paths, page errors,
overflow and blocked external resources without live data or network assets:

```sh
make browser-test # shared offline browser fixtures; browser setup is explicit
```

## Build, test and refresh

```sh
make system-deps # explicit macOS/Homebrew installation of uv
make deps        # install complete locked environment when missing/stale
make             # offline build from committed data
make test        # offline Python tests
make open        # open the generated HTML
make data        # explicit network refresh, then rebuild
make clean       # remove generated HTML
make clean-deps  # remove environment/stamp; clean-venv is an alias
node tests/test_timeline.cjs # optional checks, Node 18+, no npm dependencies
```

Build within this checkout: the Makefile includes `../python-project.mk`.
Homebrew must already be installed for `system-deps`; other platforms need uv
installed manually. uv manages Python >=3.11. No credentials are needed.
Environments are reused without repair. Use `make clean-deps && make deps` for
an incomplete environment. Missing/stale locks fail without being rewritten.

Fetching uses requests, BeautifulSoup for CMHC accessible chart tables, and
pypdf layout extraction for TRREB PDFs. All required inputs must validate before
one `data/series.json` is replaced atomically. Missing periods, duplicates,
implausible values, truncated tables and missing report links fail the refresh.
The latest monthly price table must cover the full previous year and January
through the report month discovered from its PDF filename. Combined history
must also reach that month; surviving extracted rows cannot shorten the endpoint.
Unchanged normalized records preserve bytes, timestamps and mtime. Raw PDFs are
not retained. Network access is confined to `make data` and dependency setup;
installed builds/tests stay offline. Failed refreshes retain previous data/output.

The rolling CMHC URL must still contain the **Fall 2026** edition; a new edition
requires reviewing definitions and forecast vintage before updating the parser.
TRREB archive reports may need extending when a new year creates a history gap.

Sources live in `src/`; `timeline.js` holds the date/selection model and `app.js`
renders the one SVG plot. `tests/` contains parser fixtures and model checks.
The committed artifact is `output/canada-mortgage-stress.html`.

## Data sources

- [CMHC Residential Mortgage Industry Report, Fall 2026](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-research/research-reports/housing-finance/residential-mortgage-industry-report):
  accessible tables, Ontario observations from Figures 1 and 13. Underlying
  sources include the Canadian Bankers Association and Statistics Canada.
- [TRREB Historic Statistics](https://public.trreb.ca/wp-content/files/market-stats/market-watch/historic.pdf):
  annual sale prices and the changing-market-area caveat.
- [TRREB Market Watch](https://public.trreb.ca/market-data/market-watch/): latest
  report discovery and the notice about expanded coverage and revised history.
- [December 2021](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2112.pdf),
  [December 2023](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2312.pdf),
  [December 2025](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2512.pdf),
  and [September 2026](https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw2609.pdf)
  Market Watch reports: monthly sale-price tables. Copyright Toronto Regional
  Real Estate Board. Exact report URLs are also in the HTML and JSON.

Shared build-time components and the single Python environment are documented
in the [repo README](../README.md). Project `make clean-deps` removes that shared
environment, not a private environment. Add dependencies at the repository root;
`site.toml` holds listing metadata and `pytest.ini` configures this project’s tests.
The generated HTML remains standalone and embeds its application assets/data.
