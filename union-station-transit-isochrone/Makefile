# Interactive transit isochrone map around Union Station (30 / 60 / 90 / 120 min).
# Run from this directory: cd union-station-transit-isochrone && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := union-station-transit-isochrone
VENV  := .venv
PY    := $(VENV)/bin/python
STAMP := $(VENV)/.stamp
OUT   := output/$(PROJECT).html
GEOJSON := output/isochrones.geojson

# OSM inputs for r5py. The raw download (e.g. all of Ontario) is too large for
# R5's geographic-extent limit, so it must be clipped to the GTHA bbox first.
OSM_RAW := data/gtha.osm.pbf
OSM_PBF := data/gtha-clipped.osm.pbf
BBOX    := -80.6,43.05,-78.7,44.40   # west,south,east,north (matches fetch_isochrones.py)

.PHONY: all deps test osm data open clean clean-venv

# Default target: one-shot offline build from the committed curated model.
all: $(OUT)

deps: $(STAMP)

$(STAMP): pyproject.toml $(wildcard uv.lock)
	uv sync
	@touch $@

$(OUT): src/build_map.py $(GEOJSON) | $(STAMP)
	$(PY) src/build_map.py

# Depends on data/reachability.json when present so a fresh `make data`
# re-contours; `make clean` removes it to fall back to data/transit_model.json.
$(GEOJSON): src/build_isochrones.py data/transit_model.json $(wildcard data/reachability.json) | $(STAMP)
	$(PY) src/build_isochrones.py

test: | $(STAMP)
	$(PY) -m pytest -q

# Clip the raw OSM download to the GTHA bbox (needs osmium: `brew install
# osmium-tool`). R5 rejects extents above ~975,000 km2, so this is required.
osm: $(OSM_PBF)

$(OSM_PBF): $(OSM_RAW)
	osmium extract -b $(BBOX) $(OSM_RAW) -o $(OSM_PBF) --overwrite

# Network step: real multimodal transit routing with r5py (RAPTOR over OSM +
# GTFS). Needs Java 21 (see README) and GTFS feeds in data/. Auto-clips the OSM
# extract, then writes data/reachability.json, which build_isochrones.py
# contours and build_map.py renders.
data: $(OSM_PBF) | $(STAMP)
	OSM_PBF=$(OSM_PBF) $(PY) src/fetch_isochrones.py
	$(PY) src/build_isochrones.py
	$(PY) src/build_map.py

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

# Remove generated outputs incl. the r5py grid, so the next plain `make` rebuilds
# from the committed curated model. Re-run `make data` to regenerate the grid.
clean:
	rm -f $(OUT) $(GEOJSON) data/reachability.json

clean-venv:
	rm -rf $(VENV)
