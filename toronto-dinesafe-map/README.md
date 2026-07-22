# Toronto DineSafe Map

An interactive Leaflet map of Toronto's
[DineSafe](https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/)
food-safety inspection results — one pin per establishment, coloured by the
outcome of its most recent inspection (**Pass**, **Conditional Pass**, or
**Closed**), with a name / type / address filter and directions links.

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

> **Committed data is a small sample.** The repo ships a handful of *fictional*
> placeholder establishments so the site builds and tests offline. The live
> DineSafe dataset (~16k establishments) is fetched by `make data`, which
> requires network access to Toronto Open Data. Run it to replace the sample
> with real inspection results; the page shows a banner until you do.

## Where the data comes from

`src/fetch_data.py` (`make data`) queries the DineSafe resource on the Toronto
Open Data CKAN datastore:

```
https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search?resource_id=<current DineSafe resource>
```

The dataset has **one row per inspection/infraction line**. The fetch collapses
it to one record per establishment — its latest inspection date, that
inspection's status, and how many infractions it recorded — so the committed
`data/dinesafe.json` stays small and maps cleanly. Most rows carry
`Latitude`/`Longitude`; the few that don't are geocoded from their address with
OpenStreetMap Nominatim (cached in `data/geocode_cache.json`, 1 request/second).

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
| `data/dinesafe.json` | Per-establishment data consumed by the build (sample until `make data` is run) |
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
