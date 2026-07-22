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
> DineSafe set (~18k establishments, one pin each) so the site builds and tests
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

> **The committed `data/dinesafe.json` is summary-only** (latest inspection per
> establishment, without the per-infraction detail). The build handles both
> shapes: with summary data the sidebar shows the latest inspection and notes that
> details load on refresh; run **`make data`** to pull the full per-inspection
> history and the sidebar fills in every past inspection and infraction.

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
