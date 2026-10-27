# Toronto DineSafe Map

An interactive Leaflet map of Toronto's
[DineSafe](https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/)
food-safety inspection results — one pin per establishment, coloured by the
outcome of its most recent inspection (**Pass**, **Conditional Pass**, or
**Closed**).

- **Search** by name, type or address — matches are listed as you type; click one
  to fly to its pin and open its details. A **Nearest first** toggle (on by
  default) ranks the results by distance and labels each once you allow the
  browser to share your location; without a location it falls back to A–Z.
- **Detail sidebar** — clicking a pin (or a search result) opens a sidebar with
  the establishment's current status, key facts, and its **inspection history**:
  every inspection on record, each visit's outcome, and the individual
  infractions it found (description, severity, and the action ordered).
- **Directions** links out to Google Maps for each establishment.

DineSafe is Toronto Public Health's inspection and disclosure program for
restaurants, food stores, and other establishments that serve or sell food.

## Map controls

The desktop sidebar puts search and the matching count above **Layers**,
**Results**, and **Data sources** tabs. On phones, the same controls live in an
expandable bottom panel. Search and selected layers determine both the count
and results; layer badges show matches available before layer selection. Results
list up to 50 matches; narrow the search to find a specific feature.

Use **Center on my location** (◎) to request browser location and show its
accuracy circle, or **Fit matching features** (⛶) to frame the current selection.
Location is requested only after a click and stays in browser memory. HTTPS or
localhost is needed for location in most browsers. Denied, unavailable and timed
out requests show a message and can be retried. The **Provenance** footer opens
source links, snapshot information and accuracy caveats.


## Run

```bash
make        # builds output/toronto-dinesafe-map.html from data/dinesafe.json (offline)
make data   # re-pulls the live DineSafe dataset and rebuilds (needs internet)
make open   # build and open in a browser
make test   # run the tests
```

`uv` creates this project's `.venv` on first run. Targets follow the repo
standard — see the [repo README](../README.md).

> **Committed data is the live dataset.** `data/dinesafe.json` holds the full
> DineSafe set (~20k establishments, one pin each) so the site builds and tests
> offline straight from a clone. `make data` re-pulls it from Toronto Open Data
> (needs internet) whenever you want fresher inspection results.

## Where the data comes from

`src/fetch_data.py` (`make data`) queries the DineSafe resource on the Toronto
Open Data CKAN datastore:

```
https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search?resource_id=<current DineSafe resource>
```

The dataset has **one row per inspection/infraction line**. The fetch collapses
it to one record per establishment — its latest inspection date and status, plus
an `inspections` timeline (every inspection on record with that visit's status and
its individual infractions) that powers the detail sidebar. Most rows carry
`Latitude`/`Longitude`; the few that don't are geocoded from their address with
OpenStreetMap Nominatim (cached in `data/geocode_cache.json`, 1 request/second).

`make data` retries API requests up to three times. If pagination fails or
returns an incomplete dataset, it discards the partial rows and downloads the
official `dinesafe.csv` export discovered from the same catalogue. The CSV must
have the expected columns and match an exact, non-estimated datastore row count
before and after download. A truncated export, changing count, or failure of
both sources fails the command and retains the previous snapshot. No manual
download or temporary import script is needed for this recovery.

> **The committed `data/dinesafe.json` includes inspection history and infraction
> details.** The sidebar shows every inspection in the snapshot, grouped by visit.
> Run **`make data`** to refresh the snapshot from the latest upstream records.

## Data sources

- **DineSafe inspection results** — [Toronto Open Data](https://open.toronto.ca/dataset/dinesafe/)
  (Toronto Public Health), via the CKAN datastore API.
- **Program details** — [City of Toronto — DineSafe](https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/).
- **Geocoding & map tiles** — © [OpenStreetMap](https://www.openstreetmap.org/copyright)
  contributors (Nominatim for the address fallback, OSM tiles for the base map).

## Layout

| Path | What it is |
| --- | --- |
| `src/fetch_data.py` | Network step (`make data`): pulls DineSafe, reduces it to one pin per establishment |
| `src/build_map.py` | Offline build: renders `output/toronto-dinesafe-map.html` from `data/dinesafe.json` |
| `data/dinesafe.json` | Per-establishment data consumed by the build (full DineSafe set; refreshed by `make data`) |
| `data/geocode_cache.json` | Address → `[lat, lon]` cache produced by `make data` (commit it) |
| `output/toronto-dinesafe-map.html` | Generated map (committed so it works without a build) |

## Caveats

- **Statuses are point-in-time.** Each pin is the *most recent* inspection on
  record; establishments are re-inspected and statuses change. A **Closed**
  establishment may have since reopened. Confirm current status on the official
  [DineSafe site](https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/)
  before relying on a pin.
- **Conditional Pass** means minor infractions were found that must be corrected;
  it is not a failing grade.
- Pins use the dataset's own coordinates where present, otherwise a geocoded
  address, so some are approximate.
- The province/city update DineSafe continually; re-run `make data` for a fresh
  pull.

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
