# StaticSites

Standalone static maps and plots built from committed datasets. Projects share
build-time Python and UI components, while retaining their own sources, data,
tests and outputs. Each generated HTML embeds its application code, styles and
data: publishing it requires no Python, package server or checkout. Existing
map CDN/tile dependencies remain documented; chart pages work offline.

| Project | What it is |
| --- | --- |
| [us-canada-yield-curves/](us-canada-yield-curves/) | US Treasury and Canadian government bond yields across maturities, on the latest shared trading date. |
| [canada-mortgage-stress/](canada-mortgage-stress/) | Monthly Ontario bank mortgage arrears including CMHC forecasts and Toronto-area sale prices in one plot, limited to their shared available period. |
| [fcf-macro-indicators/](fcf-macro-indicators/) | Quarterly free cash flow and cash balances of a basket of large public companies vs. M2, the S&P 500, and the 3M / 2Y / 10Y / 30Y Treasury curve, rebased to a chosen anchor quarter. Renders a static PNG and an interactive HTML chart. |
| [margin-sp500-m2-visualization/](margin-sp500-m2-visualization/) | FINRA margin debt vs. S&P 500, M2, CPI, and PPI, rebased to a configurable anchor date. Renders a static PNG and an interactive HTML chart. |
| [ontario-physiotherapy-clinics-map/](ontario-physiotherapy-clinics-map/) | The 255 publicly-funded (OHIP-covered) physiotherapy clinics and hospitals listed by the province, searchable by name / city / postal code. |
| [toronto-building-permits-map/](toronto-building-permits-map/) | Toronto’s complete active building permit register, searchable by address with status, type and application-year filters. |
| [toronto-crime-map/](toronto-crime-map/) | Toronto Police reports from 2025 onward, merged by incident ID with seven type layers, text search and approximate intersection locations. |
| [toronto-dinesafe-map/](toronto-dinesafe-map/) | Toronto's DineSafe food-safety inspection results, one pin per establishment coloured by its latest outcome (Pass / Conditional Pass / Closed), searchable by name / type / address. |
| [toronto-vulnerable-services-map/](toronto-vulnerable-services-map/) | Toronto/Ontario services for vulnerable populations: shelters, warming & respite centres, drop-ins, harm reduction, housing supports. |
| [trca-flood-plain-map/](trca-flood-plain-map/) | TRCA riverine flood plain polygons and attributed floodline boundaries, filterable by watershed and source. |
| [union-station-transit-isochrone/](union-station-transit-isochrone/) | The morning commute-shed of Toronto's Union Station — where you can reach Union by transit in 30 / 60 / 90 / 120 min. |

## Chart interface convention

Chart projects use a warm light page (`#f5f6f3`), a white chart surface, dark
slate text (`#182d37`), muted labels (`#596b71`) and subtle gridlines (`#dce2df`).
Use system sans-serif typography, a readable title and short subtitle above the
plot, a 1200px maximum page width, and compact linked sources in a disclosure
below it. Chart labels should stay legible at 11–12px. Match PNG typography,
backgrounds and colors to the interactive version where a PNG is provided.

Use consistent colors for shared metrics: S&P 500 / primary series teal
(`#116965`), M2 blue (`#466aa0`), margin debt / secondary series rust (`#aa5633`),
CPI purple (`#806493`) and PPI slate (`#70868b`). Keep lines about 2px wide,
forecasts dashed, legends above the plot, and distinct
units explicitly labelled. Multi-panel plots share a horizontal time scale.

Use native SVG and page components modelled on the Ontario mortgage chart:
compact legend above, plot/panels on one time scale, and collapsed definitions
and sources. Fit the viewport without a plotting-library toolbar. Hover, tap or
use the arrow keys to show the selected date and values beside the vertical
guide. Legend taps
can toggle lines. Keep only essential controls, such as the FCF ratio choice.
Rebasing is a build-time option in the macro projects.

Use `staticsites.charts` and the shared plot assets in `src/staticsites/assets/plots/`. Native charts embed their data/scripts/styles in the HTML and
make no external runtime requests.

All three chart projects support the same review-image commands as maps:
`make -C <project> snapshot-browser` explicitly sets up headless Chromium, then
`make -C <project> snapshots` rebuilds and captures desktop (1440 × 900) and
mobile (390 × 844) JPEGs in `tests/snapshots/`. Capture waits for every plot,
readout, fonts and geometry to settle and rejects horizontal overflow or script
errors. The chart pages are self-contained; capture blocks external requests and
works offline after setup. Review snapshots show the initial viewport; the
macro projects' Matplotlib PNGs remain separate static charts.

## Map interface convention

Map projects use a dark teal title bar, a desktop sidebar and an expandable
mobile bottom panel. Keep search and matching counts above the **Layers**,
**Results** and **Data sources** tabs, with provenance in the footer. All features
must belong to toggleable layers and remain findable through search. Put zoom,
**Center on my location** and **Fit matching features** controls together on the
map. Request location only after a click; show accuracy and useful retry messages.

Keep project-specific details (inspection histories, permit records, transit
itineraries) accessible from features and results. Clearly label what counts mean
and document spatial accuracy, snapshot dates and linked upstream sources. Layer
badges show query matches before selection; the headline count and results respect
selected layers. Use the shared controls and styles in `src/staticsites/assets/maps/`; keep project-specific search fields and filters configurable in the local adapter.

All seven map projects also provide explicit review snapshots:
`make -C <project> snapshot-browser` downloads headless Chromium once, and
`make -C <project> snapshots` rebuilds and captures desktop (1440 × 900) and
mobile (390 × 844) images under that project's `tests/snapshots/`.
Capture waits for map initialization, tiles and motion to settle. These commands
use the root environment’s locked Playwright dependency; they are never run by ordinary
builds, tests or data refreshes. Snapshot capture requires network access to map
assets. Review and commit the images after visual changes.

Optional interaction checks use only Node.js built-ins (Node 18+):
`node admin_tests/map_explorer.cjs`. They verify all seven projects' layer-aware
counts, search, location success/error/retry behavior, and mobile fit padding.
Project builds and pytest suites continue to use their own Python environments.

## Setup and commands

The repository has one `pyproject.toml`, one `uv.lock`, and one root `.venv`.
`.python-version` selects Python 3.12 for the standard build environment.
Install [uv](https://docs.astral.sh/uv/) manually, or use `make system-deps` on
macOS with Homebrew already installed. System tools and browser binaries are
never installed by ordinary builds or tests. Transit additionally needs Java 21
and osmium-tool; `make -C union-station-transit-isochrone system-deps` installs
those explicitly on macOS.

```sh
make deps                         # uv sync --locked --all-groups; install the root package editable
make -C canada-mortgage-stress     # offline build of one project
make -C canada-mortgage-stress test
make test STATUSES=off             # shared/admin tests, then every project's tests and build
make -C <project> data             # explicit data refresh for one project, then rebuild
make data                         # explicit refresh of all projects; refresh is an alias
make manifest                     # regenerate sites.json
make check                        # metadata, shared Python tests and repo-admin tests
```

All project `make deps` commands refer to the same root environment. A current
stamp reuses it; an incomplete environment fails without automatic repair.
`make clean-deps && make deps` at the root explicitly recreates the shared
environment, affecting every project. It preserves data, caches, sources,
lockfiles, outputs and review images. `make -C <project> clean` removes only that
project's generated outputs. Ignored legacy project `.venv` directories are no
longer used and are not deleted automatically.

Automatic dependency cleanup is limited to `.venv`, `.venv-*` and nested
`.venv/` directories inside this checkout. Other custom environment locations
must be cleaned manually. Changing `.python-version` invalidates the shared
setup stamp just like changing the dependency manifests.

Use `uv add <dependency>` or `uv add --group <group> <dependency>` **from the
repository root**. Groups `plots`, `maps`, `transit`, and `dev` describe the
optional toolsets; Make installs all groups for complete verification. Advanced
partial setups are possible with uv’s group flags, but are outside the
complete stamped Make workflow. After manually changing a stamped environment,
use explicit cleanup/setup before normal verification.
There is no separate Python environment per group or project. The initial root lock constrains existing numeric and geometry engines to
avoid mixing dependency upgrades into the extraction. Review those constraints
when deliberately upgrading. Run the full suite whenever the root lockfile changes. Browser/system installation remains
explicit even after dependency changes.

For an isolated verification environment use `make test STATUSES=off VENV=.venv-ci`.
That is one alternate **repository** environment used by metadata and all
project commands, not ten separate installations.

## Shared components and project boundaries

`src/staticsites/` is the editable build-time Python package:

- `assets.py` and `assets/maps/`: safe JSON embedding, map controls, layers/results/sources tabs,
  mobile panels/dialogs, keyboard/location/fit behavior and styles. Search stays
  project-configured: addresses, names, categories, watersheds or stations.
- `charts.py` and `assets/plots/`: native SVG plotting, legends, axes, shared
  inspection, page layout/provenance and Matplotlib styling. Ontario's indexed
  chart remains a local adapter with its own data/coverage semantics.
- `snapshots.py`: one capture implementation with map/chart readiness policies,
  fresh desktop/mobile contexts, explicit browser setup, and staged publication.
- `pipeline.py`: atomic write-if-changed, content-aware timestamped snapshots,
  provenance sidecar recovery and caches that do not persist service failures.
- `sources.py` and `geocoding.py`: bounded HTTP GET retries, CKAN envelopes,
  ArcGIS error handling, and Nominatim client/rate-limit setup.

Keep domain-specific parsing, joins, geometry preparation, validation bounds,
reporting-period alignment and fallback decisions in each project's `src/`.
Data and geocoding caches stay project-local. No project imports another
project. Avoid a pipeline framework: extract real repeated behavior and keep
source-specific policies explicit. Shared assets are included as Make
prerequisites for HTML/PNG outputs. Data-derived artifacts such as routed
GeoJSON retain their project-specific prerequisites and cached inputs.

## Project layout and metadata

```text
<project>/
  site.toml       # [site] name, title, description (listing metadata only)
  pytest.ini      # testpaths=tests, pythonpath=src
  Makefile        # project builder/inputs; includes ../artifact-project.mk
  README.md       # purpose, sources, limitations and commands
  src/            # local adapters, fetchers and builders
  tests/          # project tests and committed review snapshots
  data/           # committed build inputs and persistent caches
  output/         # committed standalone HTML and secondary artifacts
```

`environment.mk` manages the root environment and explicit setup/cleanup;
`python-project.mk` supplies the project commands. `artifact-project.mk` adds
the common builder/input/format rules used by all ten projects; transit adds its
geometry and clipping recipes locally. Every project implements
`all`, `deps`, `system-deps`, `test`, `data`, `open`, `clean`, `clean-deps` and
`clean-venv`. Snapshot-enabled projects also expose `snapshot-browser`,
`snapshots`, and `browser-test` (explicit offline browser fixtures).

Scripts resolve paths relative to their own project root. The primary output
is `output/<project>.html`; secondary artifacts share the stem. Generated pages
must name and link their data sources. Commit rebuilt outputs and review
snapshots with visual changes. JSON stays readable with `indent=2`.

`generate_manifest.py` reads every project's `site.toml` and writes the unchanged
`sites.json` schema used by downstream consumers. `[site].description` starts
with `"<title> — "`; the prefix is removed in the generated manifest. Run
`make manifest` after adding a project or changing its listing metadata.

## Data refresh guarantees

Only explicit `make data` / `make refresh` fetches or prepares datasets. Ordinary
builds and tests stay offline after dependency setup. Validate every required
source before publishing, normalize unordered records, preserve timestamps and
bytes when substantive content is unchanged, and fail without publishing a
partial dataset. Preserve successful geocodes and cache genuine no-matches,
never service errors. Credentials remain operator-supplied. Large OSM/GTFS
inputs stay ignored and documented in project data READMEs.

Review snapshot capture is separate from builds/tests/data refresh. Maps may
load their existing remote assets; charts block external requests. Run
`make -C <project> snapshot-browser` explicitly after Playwright upgrades and
`make -C <project> snapshots` to capture desktop/mobile JPEGs. The images show
the initial viewport; longer pages continue below the captured image.

## Local CI and GitHub statuses

`local_ci.py` discovers projects through `*/Makefile`, runs `make check` and
separate project test/build processes, and continues after independent failures.
Separate processes keep local module names such as `fetch_data` from colliding.
It uses the same root environment throughout.

`STATUSES=off` is local only; `auto` publishes `local-ci/metadata` and each
`local-ci/<project>` for a clean pushed commit; `required` refuses dirty or
unpublished state. A run pins HEAD and checks all tracked/untracked changes
before publishing success. Status-publication failures are visible and nonzero.
Logs remain ignored under `.local-ci/<sha>/`. There are no hosted workflows.
The existing `gh` session/keychain supplies authentication; never print tokens.

Optional interaction checks: `node admin_tests/map_explorer.cjs`,
`node admin_tests/permit_search.cjs`, and each plot project's Node model tests.

## Adding a project

Always run `./new-project.py my-new-project`. It creates the standard layout
and a working placeholder using the root environment. Replace the fetch/build
placeholders and README TODOs, configure shared components, update `site.toml`,
add a catalog row above, then run `make manifest`. New projects inherit the root
lock; add genuinely new dependencies at the root rather than creating another
environment. Update the scaffolder whenever the standard changes.

## Reuse audit

The common Make recipes live in environment.mk, python-project.mk and
artifact-project.mk. Project Makefiles now declare their builder, inputs and
formats; transit retains its routing, GeoJSON and osmium rules. Makefile/fragment
changes also invalidate their configured artifacts. Successful builds must
produce the declared output; unchanged bytes still advance the build mtime so
Make does not repeatedly rerun a content-aware publisher. Keep these small
configuration files rather than inferring build dependencies from filenames.

This pass also consolidated safe script JSON, atomic HTML publication,
monthly/quarterly time-series mechanics, search normalization and existing map
HTML escaping. The cleanup guard rejects ancestor/source/data directories, and
Python-version changes invalidate environment setup.

The remaining candidates have different policies and should not be merged
blindly:

- **Downloads:** a shared streaming/staging helper could serve permits, DineSafe
  and transit. Preserve conditional requests, fresh-stream retries, bulk-export
  fallback and read-only operator-supplied files as explicit caller policies.
- **ArcGIS batches:** crime and flood maps both enumerate IDs and validate
  complete batches. Share the mechanics only with hooks for ID extraction,
  GET/POST transport, geometry format and source-change checks. Keep schema
  validation, joins and geometry simplification local.
- **Map initialization and marker factories:** repeated Leaflet setup, tile
  attribution and marker styling are candidates. Preserve clustering, pane order
  and project-specific styling; do not turn all map logic into a generic framework.
- **DOM/SVG primitives:** the Ontario mortgage plot and shared plot renderer
  still have small element/date-tick helpers in common. Share primitives before
  trying to unify their different axis, coverage and observation semantics.
- **Provenance fallback:** the shared plot helper retains the existing CSV-mtime
  fallback when the retrieval sidecar is absent. Prefer a preserved source or
  reported retrieval date before that fallback; clone time should not imply new
  upstream data.
- **Dependency groups:** shared Python files currently invalidate all HTML/PNG
  outputs. Separate map/plot/pipeline prerequisites would avoid unrelated rebuilds
  as the package grows, without invalidating cached data-derived GeoJSON.

Address matching, business-name matching, reporting-period policies, source
parsers, outlier rejection and fallback geography remain local by design.
