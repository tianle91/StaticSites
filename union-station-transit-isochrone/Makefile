# Interactive transit isochrone map around Union Station (30 / 60 / 90 / 120 min).
# Run from this directory: cd union-station-transit-isochrone && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := union-station-transit-isochrone
GEOJSON := output/isochrones.geojson
OUTPUTS := output/$(PROJECT).html $(GEOJSON)
# Keep the routed grid cleanup: plain make then uses the curated fallback.
CLEAN_FILES := $(OUTPUTS) data/reachability.json
BREW_FORMULAE := uv osmium-tool
BREW_CASKS := temurin@21

# Raw Ontario OSM must be clipped before R5 can load it.
OSM_RAW := data/gtha.osm.pbf
OSM_PBF := data/gtha-clipped.osm.pbf
BBOX := -80.6,43.05,-78.7,44.40

include ../python-project.mk

$(OUT): src/build_map.py $(GEOJSON) data/transit_model.json $(wildcard data/reachability.json)
	$(PY) src/build_map.py

# Depends on data/reachability.json when present so a fresh `make data`
# re-contours; `make clean` removes it to fall back to data/transit_model.json.
$(GEOJSON): src/build_isochrones.py data/transit_model.json $(wildcard data/reachability.json)
	$(PY) src/build_isochrones.py

.PHONY: osm

# Clip the raw OSM download to the GTHA bbox (needs osmium: `brew install
# osmium-tool`). R5 rejects extents above ~975,000 km2, so this is required.
osm: $(OSM_PBF)

$(OSM_PBF): $(OSM_RAW)
	osmium extract -b $(BBOX) $(OSM_RAW) -o $(OSM_PBF) --overwrite
