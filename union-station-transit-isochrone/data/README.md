# Routing inputs

Run `make data` from the project directory. It obtains all default network
inputs, clips OSM, validates GTFS service for the next non-holiday Wednesday,
routes to Union, and rebuilds the map in one invocation. Install Java 21 and
`osmium-tool` first; Python dependencies are bootstrapped with `uv sync --locked`.

## Managed downloads

- `gtha.osm.pbf`: [Geofabrik Ontario OSM](https://download.geofabrik.de/north-america/canada/ontario.html).
- `ttc.zip`: [Toronto Open Data TTC schedules](https://open.toronto.ca/dataset/merged-gtfs-ttc-routes-and-schedules/).
- `go.zip` and `up.zip`: separate [Metrolinx GO and UP Express feeds](https://www.gotransit.com/en/partner-with-us/software-developers).

Metrolinx's download page documents its Access and Use Agreement.
OSM is a large download (about 1 GB). Conditional HTTP requests reuse unchanged
files; sources without validators are downloaded and compared. Downloads are
validated before replacement. Failed downloads retain previous valid files.

`gtha-clipped.osm.pbf` uses `BBOX_S/N/W/E` (defaults 43.05/44.40/-80.60/-78.70).
Clipping is repeated only when raw OSM, bounding box, or osmium version changes.
`refresh_cache.json` records HTTP validators, hashes, and routing signatures.
Routing reruns when content, service date, configuration, model, code, or the
project lock changes, or when reachability results are missing/invalid.

All binary inputs, cache metadata, and `reachability.json` are gitignored.
`transit_model.json` remains the committed offline fallback.

## Caller-managed inputs

Set `OSM_PBF` to a pre-clipped custom extract and/or `GTFS_DIR` to a folder of
custom feeds. These overrides are validated but never downloaded or overwritten.
Every `*.zip` in the selected feed folder is used and must have active trips for
the routing date. Optional regional feeds can also be added to the default
`data/` folder; they are retained and included in cache invalidation.

Other routing settings: `ARRIVE_HHMM`, `PERCENTILE`, `GRID_SPACING_M`,
`MAX_MINUTES`, and `BBOX_S/N/W/E`; see the project README for their meanings.
