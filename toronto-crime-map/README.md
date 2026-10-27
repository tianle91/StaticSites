# Toronto reported crime map

An interactive Leaflet map of Toronto Police Service (TPS) reports from **2025
onward**, with offence, date, neighbourhood and text filters. Separate datasets
cover the five main offence categories, homicides, and shootings/firearm
discharges. Cluster numbers count records, including records sharing the same
published point. Clicking a point shows its record details (up to 20 at once).
The neighbourhood table follows the same filters and can focus the map.

## Usage

```sh
make          # offline build from committed inputs
make test     # offline tests
make data     # explicitly refresh all three TPS sources and browser assets, then rebuild
make open     # open output/toronto-crime-map.html
```

Open the committed HTML directly without a server. All records, Leaflet and
marker-cluster code/styles are embedded; only OpenStreetMap basemap tiles need
internet. On narrow screens the filter panel scrolls above the map.

The default inclusion window is fixed at 2025 onward to keep the portable file
manageable. Earlier records are available upstream (main offences since 2014;
homicides and shootings since 2004). To deliberately expand this project's
snapshot within the supported common history, run
`.venv/bin/python src/fetch_data.py --start-year 2020`, then `make`.
The next `make data` returns to the documented default of 2025 onward.
There is no automatic data refresh.

## Data sources

- [TPS Community Safety Indicators](https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/Major_Crime_Indicators_Open_Data/FeatureServer/0)
  (formerly Major Crime Indicators): assault, break and enter, auto theft,
  robbery and theft over. Sexual violations are excluded.
- [TPS Homicides](https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/Homicides_Open_Data_ASR_RC_TBL_002/FeatureServer/0).
- [TPS Shootings & firearm discharges](https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/Shooting_and_Firearm_Discharges_Open_Data/FeatureServer/0).
- © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (basemap).

Contains information licensed under the
[Open Government Licence – Ontario](https://www.ontario.ca/page/open-government-licence-ontario).
Toronto Police Service is the information provider. This is an independent
project and does not imply TPS endorsement.

Leaflet 1.9.4 and Leaflet.markercluster 1.5.3 are fetched from pinned unpkg URLs
only by the explicit data step. Their upstream licence files and source notices
are retained in `data/`. Python uses the standard library; pytest is the only
test dependency.

## Scope and caveats

- **Approximate intersection locations:** TPS deliberately displaces coordinates
  to nearby road intersection nodes. They identify no specific address,
  individual or property; there is no fixed published accuracy radius.
- **Record counts versus incidents:** main-feed records represent offences and/or
  victims, so several rows can share an incident ID. All rows are retained;
  incident counts use distinct event IDs within the selected dataset.
- **Layers overlap:** shootings may also appear as assaults or homicides. Do not
  add layer totals. The dataset selector presents one source at a time.
- **Different inclusion dates:** main-feed rows are selected by report year;
  homicide/shooting rows by occurrence year. Date controls use Toronto calendar
  dates converted from upstream UTC timestamps. Main offences can be filtered
  by either report or occurrence date; older occurrences may be present when
  reported within the window. Occurrence filtering cannot recover reports
  excluded by the report-year scope. Each layer shows its latest included date.
- **Unmapped records:** missing, nonfinite, zero or out-of-Toronto coordinates
  remain in totals and neighbourhood summaries, with their number displayed.
- **Neighbourhood counts:** use the supplied 158-neighbourhood labels, not a
  spatial join of displaced points. Displacement can still affect TPS geographic
  counts. These are raw counts, not population-adjusted rates or a safety score.
- Data covers police-reported records, is preliminary, can be revised, and does
  not represent all crime or personal risk. It is a committed snapshot, not a
  live feed. Categories and coverage are limited to the selected datasets.

## Fetch validation and reproducibility

The fetcher discovers the complete matching object-ID set for each source,
requests IDs in bounded POST batches, validates exact membership with no missing
or duplicate records, and rechecks source IDs and edit metadata afterward.
Truncated batches, unexpected schemas/categories, upstream errors or sources
changing during download fail the refresh. All three sources and all browser
assets must download and validate before any input is replaced. Inputs are
written atomically per file; required-source failures retain the previous data.

Rows are sorted by source and object ID. Content-identical source records retain
the committed fetch timestamp, bytes and file modification time even if ArcGIS
edit metadata changes. Missing browser assets are restored. The builder has no
network code and writes byte-identical HTML from identical inputs.

## Layout

| Path | Purpose |
| --- | --- |
| `src/fetch_data.py` | Explicit network step and source validation |
| `src/build_site.py` | Offline HTML assembly |
| `src/map.html`, `src/map.js` | Map layout, filters, clusters and summaries |
| `data/crimes.json` | Timestamped snapshot; `columns` describes each readable array row |
| `data/*.js`, `data/*.css`, `data/*LICENSE.txt` | Pinned browser dependencies and licences |
| `output/toronto-crime-map.html` | Committed portable page |
| `tests/` | Offline fetch, publication and build checks |

## Refresh and dependencies

This project includes the repository's [shared Python/uv Make template](../python-project.mk).
Its own Makefile defines artifact inputs, rendering rules, and any configuration
overrides. Build inside the repository checkout so the shared template is available.

`make system-deps` installs [uv](https://formulae.brew.sh/formula/uv)
on macOS using [Homebrew](https://brew.sh), which must already be installed.
On other platforms, install those tools manually before `make deps` / `make data`.
System installation runs only when explicitly requested; other targets never
invoke it. Credentials must be supplied separately.

`make deps` installs this project's complete locked Python environment, including
test dependencies, when it is new or the dependency manifests change. `make data`
uses the same setup before fetching all required upstream inputs. Repeated commands
reuse the environment; they do not attempt repairs. To reinstall from scratch, run
`make clean-deps && make deps` (`clean-venv` remains an alias). Missing or stale
locks fail without being rewritten.
Dependency setup may require network access; installed builds/tests are offline.
`make data` obtains every required input and rebuilds outputs automatically.
Unchanged upstream content preserves data timestamps; missing generated files are
restored. Required-source failures retain previous datasets and return an error.
