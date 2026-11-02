# Toronto building permits map

An interactive Leaflet map of Toronto's **complete active building permit
register**, with address search and filters for
status, permit type and application year. Pins group permits at the same address;
click for work, structure, application / issue dates, estimated cost and description.
All matching locations are clustered; cluster numbers count permit records,
not addresses. Type layers group the six most common permit types plus Other,
with exact type, status and year controls under More filters.
The sidebar lists the first 50 matching records, including unmatched addresses.
Map-pin popups show all matching permits at the location.

Address queries such as `8 The Esplanade` match the complete house number in
the address field, excluding `38`, `58`, and mentions in another property's
description. Case, extra spaces, commas and periods are ignored. Street text
can be partial while typing. House-number suffixes and ranges are literal:
`8A` and `8-10` are separate from `8`; trailing unit information is allowed.
A house number alone also requires a complete-number match. Street-name-only
queries match partial address text. Permit numbers and descriptions are shown
in the results/details but are not searched.

## Visual snapshots

[Desktop (1440 × 900)](tests/snapshots/desktop.jpg) ·
[Mobile (390 × 844)](tests/snapshots/mobile.jpg)

Regenerate both review images explicitly:

```sh
make snapshot-browser  # one-time headless Chromium download; repeat after Playwright upgrades
make snapshots         # rebuild from committed inputs, then capture both views
```

The shared capture helper serves this project on a temporary loopback port and uses fresh,
light-mode Chromium contexts with no search or user location. Mobile uses touch
emulation and the compact panel; browser chrome and the on-screen keyboard are
excluded. It waits for initialization, fonts, loaded tiles and settled map motion.
Both captures must succeed before existing images are replaced. Images are visual
review references, not automated pixel comparisons; upstream map tiles can change.

Snapshot capture needs network access to the page's map scripts and tiles. It
never refreshes committed data or installs browsers automatically. Ordinary
`make`, `make test` and `make data` do not capture snapshots. Python dependencies
remain locked in the repository-root environment. On Linux, install Chromium's
[manual system prerequisites](https://playwright.dev/python/docs/browsers#install-system-dependencies)
if required; these targets do not install OS packages. Recapture after visual
changes and commit the reviewed images with them.

## Map controls

The desktop sidebar puts search and the matching count above **Layers**,
**Results**, and **Data sources** tabs. On phones, the same controls live in an
expandable bottom panel. Search and selected layers determine both the count
and results; layer badges show matches available before layer selection. Results
list up to 50 matches; narrow the search to find a specific feature.
On phones, the compact panel keeps search and counts visible. **Show results & filters**
expands it; **Show more map** folds it down. Focusing search also expands the
panel. It follows the visible viewport when the keyboard opens, and Search/Enter
dismisses the keyboard. Source links remain available under **Data sources**.
Long location details open in a scrollable mobile dialog with a persistent close
button; short map labels remain anchored popups. Desktop keeps its sidebar and popups.

Use **Center on my location** (◎) to request browser location and show its
accuracy circle, or **Fit matching features** (⛶) to frame the current selection.
Location is requested only after a click and stays in browser memory. HTTPS or
localhost is needed for location in most browsers. Denied, unavailable and timed
out requests show a message and can be retried. The **Provenance** footer opens
source links, snapshot information and accuracy caveats.

## Usage

```sh
make        # offline build from committed data/permits.json
make test   # offline normalization and rendering tests
make data   # download permits and address points, then rebuild (internet required)
make open   # open output/toronto-building-permits-map.html
```

## Data sources

- [City of Toronto — Building Permits: Active Permits](https://open.toronto.ca/dataset/building-permits-active-permits/).
- [City of Toronto — Address Points (Municipal)](https://open.toronto.ca/dataset/address-points-municipal-toronto-one-address-repository/).
- Contains information licensed under the [Open Government Licence – Toronto](https://open.toronto.ca/open-data-license/).
- [Leaflet](https://leafletjs.com/) and © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)
  for the map library and base-map tiles.

Leaflet.markercluster 1.5.3 is vendored in `src/vendor/` with its upstream
MIT licence, so clustering builds without downloads.

## Fetch and layout

`src/fetch_data.py` discovers the current downloads through Toronto Open
Data's CKAN catalogue. It downloads the complete permit CSV and streams the municipal address GeoJSON, joins permit `GEO_ID`
to municipal `ADDRESS_POINT_ID` (not `ADDRESS_ID`), normalizes and sorts the register, and
atomically replaces `data/permits.json` only after validation. The address GeoJSON is large, so `ijson` streams it to keep memory bounded. No geocoding API
or geocoding cache is needed. Upstream rows are retained even without a matching
address point: the page reports coverage and keeps those rows searchable.

The committed JSON uses a `columns` schema plus indented row arrays to keep the
complete register manageable. Builder/applicant names are not retained. Invalid
or sentinel construction costs become null (displayed as not disclosed).
`src/build_site.py` embeds it in `src/page.html` to produce the single-file
`output/toronto-building-permits-map.html`.
The snapshot is embedded as inert JSON and parsed at startup, avoiding compilation
of the full register as JavaScript. The raw JSON element is then removed.
Markercluster inserts markers in timed batches, coalescing filter changes until
the current insertion finishes so an older search cannot repopulate the map.

### Mobile troubleshooting

Search stays disabled until initial marker insertion finishes. A loading message
names the current phase. Startup and later JavaScript failures show an error,
**Retry loading permits**, and **Show diagnostic details** instead of a blank
result area. **Data sources → Diagnostic details** is also available after a
successful load. It contains a deterministic build fingerprint, browser/version,
visible viewport, snapshot/count, recent phases and the error, when present.
Script-load diagnostics identify the source (without URL queries or fragments)
and whether it is required by the map. Failed scripts inserted by a browser or
host are recorded without disabling the map. Runtime errors include the source
and line/column when the browser exposes them; Leaflet requests anonymous CORS
so its runtime errors can be reported with details.
Diagnostics stay on the device; nothing is sent automatically, and the report
does not collect the search text or geolocation. Select/copy the report when
reporting a phone issue. Reloading retries the whole initialization.

Optional offline interaction regressions from the repo root:
`node admin_tests/map_explorer.cjs` and `node admin_tests/permit_search.cjs`
(Node 18+). These use DOM/Leaflet fixtures; they do not emulate an iPhone keyboard
or establish the cause of an error on a particular physical device.

For an initial import or a portal outage, previously downloaded official files
can be supplied explicitly with `src/fetch_data.py --permits-csv PATH
--addresses-geojson PATH --expected-permits COUNT --expected-addresses COUNT`, using this project's `../.venv/bin/python`. Use exact counts from the official datastore metadata. Both are validated;
no partial or empty snapshot is published. `--addresses-csv PATH` is also accepted in place of GeoJSON. The standard `make data` downloads
both sources and verifies row counts against the datastore. Raw downloads are temporary; the normalized snapshot is committed.
Unchanged normalized content retains its retrieval timestamp, bytes and mtime.
Downloads use `requests` with streamed responses and three bounded attempts;
an interrupted transfer restarts its temporary file rather than appending to it.
These official bulk downloads and count checks run directly through `make data`;
manual overrides are optional recovery tools, not a normal refresh prerequisite.

## Caveats

This is an active-register snapshot, not all historical permits or a measure of
construction volume. Old permits may remain open and a current status may have
changed since retrieval. Application-year comparisons reflect which permits
remain active, not how many were issued in a year. Confirm current status with
the [City's permit lookup](https://www.toronto.ca/services-payments/building-construction/building-permit/after-you-apply-for-a-building-permit/search-the-status-of-a-building-permit-application/).

Address points approximate a property's location and do not identify the exact
construction footprint. Unmatched permits have no pin. Data is embedded in the
HTML; the Leaflet library and map tiles require internet access. The complete
register is large, so initial page loading may take a few seconds.
Data refreshes run only when `make data` is invoked.

## Refresh and dependencies

This project includes the repository's [shared Python/uv Make template](../python-project.mk).
Its own Makefile defines artifact inputs, rendering rules, and any configuration
overrides. Build inside the repository checkout so the shared template is available.

`make system-deps` installs [uv](https://formulae.brew.sh/formula/uv)
on macOS using [Homebrew](https://brew.sh), which must already be installed.
On other platforms, install those tools manually before `make deps` / `make data`.
System installation runs only when explicitly requested; other targets never
invoke it. Credentials must be supplied separately.

`make deps` installs the repository's complete locked Python environment, including
test dependencies, when it is new or the dependency manifests change. `make data`
uses the same setup before fetching all required upstream inputs. Repeated commands
reuse the environment; they do not attempt repairs. To reinstall from scratch, run
`make clean-deps && make deps` (`clean-venv` remains an alias). Missing or stale
locks fail without being rewritten.
Dependency setup may require network access; installed builds/tests are offline.
`make data` obtains every required input and rebuilds outputs automatically.
Unchanged upstream content preserves data timestamps; missing generated files are
restored. Required-source failures retain previous datasets and return an error.

Shared build-time components and the single Python environment are documented
in the [repo README](../README.md). Project `make clean-deps` removes that shared
environment, not a private environment. Add dependencies at the repository root;
`site.toml` holds listing metadata and `pytest.ini` configures this project’s tests.
The generated HTML remains standalone and embeds its application assets/data.
