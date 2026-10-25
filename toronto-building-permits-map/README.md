# Toronto building permits map

An interactive Leaflet map of Toronto's **complete active building permit
register**, with address / permit-number / description search and filters for
status, permit type and application year. Pins group permits at the same address;
click for work, structure, application / issue dates, estimated cost and description.
The map draws up to 6,000 locations in the current view; zoom in to see more.
The sidebar lists the first 50 matching records, including unmatched addresses.

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

For an initial import or a portal outage, previously downloaded official files
can be supplied explicitly with `src/fetch_data.py --permits-csv PATH
--addresses-geojson PATH --expected-permits COUNT --expected-addresses COUNT`, using this project's `.venv/bin/python`. Use exact counts from the official datastore metadata. Both are validated;
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
