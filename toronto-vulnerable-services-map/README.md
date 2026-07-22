# Toronto & Ontario Vulnerable-Services Map

An interactive Leaflet map of city/provincial services for vulnerable
populations: emergency shelter access, warming & winter respite centres,
food/drop-ins, harm reduction, and housing supports. Companion to
[Toronto Vulnerable Services Sources](./Toronto%20Vulnerable%20Services%20Sources.md).

## Run

```bash
make        # builds output/toronto-vulnerable-services-map.html from data/ (offline)
make data   # geocodes addresses + pulls EVERY shelter location, then rebuilds (needs internet)
make open   # builds and opens it in your browser
```

`make` uses only the Python standard library — no dependencies, no network.
`make data` is the enrichment step: it geocodes the curated addresses into
accurate pins and adds every distinct shelter location from the Open Data API
as its own toggleable layer. Results are cached on disk (`data/geocode_cache.json`),
so re-runs are fast and reproducible; commit the cache and `data/shelters.json` to
share the geocoded data. Open `output/toronto-vulnerable-services-map.html` in any browser; internet is needed
only for map tiles and the live stats panel.

## What's on the map

* **Marker layers** (toggle on/off, colour-coded): Intake & walk-in, Warming
  centres, Winter respite, Food & drop-in, Harm reduction. Click a marker for
  the address, notes, and a link to the source.
* **Live shelter stats panel** — fetches the latest *Daily Shelter & Overnight
  Service Occupancy* snapshot from the [Toronto Open Data CKAN API](https://open.toronto.ca/dataset/daily-shelter-overnight-service-occupancy-capacity/)
  client-side and shows people served / programs / locations for the most
  recent date. Degrades gracefully when offline.
* **Directories & data** — links to the non-mappable sources (211, Central
  Intake, RGI/community-housing waitlists, PiT counts, etc.).

## Files

| File | Purpose |
|------|---------|
| `data/services.json` | Curated locations (coords) + directory links — **edit this to update the map** |
| `src/build_map.py` | Generator: merges curated + cache + shelters into the HTML template |
| `src/fetch_data.py` | Network step (`make data`): geocodes addresses, pulls shelter locations |
| `data/geocode_cache.json` | Address → `[lat, lon]` cache produced by `make data` (commit it) |
| `data/shelters.json` | Geocoded shelter locations produced by `make data` (commit it) |
| `output/toronto-vulnerable-services-map.html` | Generated output (committed so it works without a build) |
| `Makefile` | `make` builds, `make data` enriches, `make open` opens, `make clean` removes output |

## Caveats

* Curated marker coordinates start **approximate** (derived from street
  addresses). Run `make data` once to replace them with geocoded coordinates.
* Warming/respite sites are **seasonal** — confirm status on the live City
  pages before relying on a pin.
* Harm-reduction sites are volatile (several Ontario sites closed/relocated in
  2025); pins are flagged "verify".
* The Open Data set has addresses but no coordinates, so `make data` geocodes
  each distinct shelter location (via Nominatim, cached) before pinning it.
  Until you run it, only the curated locations appear and the stats panel +
  dataset link represent the full system.
