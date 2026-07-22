# Interactive transit isochrone map around Union Station (30 / 60 / 90 / 120 min).
# The map build is stdlib-only; the RECOMMENDED enrichment (`make data`) needs
# r5py + friends, which come from the repo's shared virtualenv (../.venv).
include ../common.mk

.PHONY: all osm data test open clean

# OSM inputs for r5py. The raw download (e.g. all of Ontario) is too large for
# R5's geographic-extent limit, so it must be clipped to the GTHA bbox first.
OSM_RAW := data/gtha.osm.pbf
OSM_PBF := data/gtha-clipped.osm.pbf
BBOX    := -80.6,43.05,-78.7,44.40   # west,south,east,north (matches fetch_isochrones.py)

# Default target: one-shot offline build from the committed transit model.
all: index.html

index.html: build_map.py isochrones.geojson | $(PY)
	$(PY) build_map.py

# Depends on reachability.json when present so a fresh `make data` re-contours;
# `make clean` removes it to fall back to the curated transit_model.json.
isochrones.geojson: build_isochrones.py transit_model.json $(wildcard reachability.json) | $(PY)
	$(PY) build_isochrones.py

# Unit tests (dates, snapping, itinerary parsing) + a stdlib smoke test of the
# builders. No r5py / Java / GTFS needed, so this stays fast and hermetic.
test: | $(PY)
	$(PY) -m pytest -q

# Clip the raw OSM download to the GTHA bbox (needs osmium: `brew install
# osmium-tool`). R5 rejects extents above ~975,000 km2, so this is required.
osm: $(OSM_PBF)

$(OSM_PBF): $(OSM_RAW)
	osmium extract -b $(BBOX) $(OSM_RAW) -o $(OSM_PBF) --overwrite

# The build: real multimodal transit routing with r5py (RAPTOR over OSM + GTFS).
# Needs Java 21 (see README) and GTFS feeds in ./data/ (see fetch_isochrones.py).
# Auto-clips the OSM extract, then writes reachability.json, which
# build_isochrones.py contours and build_map.py renders.
data: $(OSM_PBF) | $(PY)
	OSM_PBF=$(OSM_PBF) $(PY) fetch_isochrones.py
	$(PY) build_isochrones.py
	$(PY) build_map.py

# Build then open in the default browser (macOS `open`, fallback to xdg-open).
open: index.html
	open index.html 2>/dev/null || xdg-open index.html 2>/dev/null || echo "Open index.html manually."

# Remove generated outputs incl. the r5py grid, so the next plain `make` rebuilds
# from the committed curated model. Re-run `make data` to regenerate the grid.
clean:
	rm -f index.html isochrones.geojson reachability.json
