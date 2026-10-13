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

.PHONY: all system-deps deps test osm data open clean clean-deps clean-venv

# Default target: one-shot offline build from the committed curated model.
all: $(OUT) | deps

# System installation is explicit and separate from Python setup and data refresh.
# Homebrew itself is an operator prerequisite; see README for other platforms.
system-deps:
	@test "$$(uname -s)" = Darwin || { echo "system-deps supports macOS with Homebrew; see README for manual prerequisites." >&2; exit 1; }
	@command -v brew >/dev/null || { echo "Install Homebrew from https://brew.sh before running make system-deps." >&2; exit 1; }
	brew install uv osmium-tool
	brew install --cask temurin@21

# Install from the lockfile only when the environment is new or manifests change.
# Reset a damaged environment explicitly with `make clean-deps && make deps`.
# Order-only deps prerequisites validate even current outputs without rebuilding them.
deps: $(STAMP)
	@test -x $(PY) || { echo "Environment incomplete: run make clean-deps then make deps." >&2; exit 1; }

$(STAMP): pyproject.toml uv.lock
	@command -v uv >/dev/null || { echo "Install uv (make system-deps on macOS) before running make deps." >&2; exit 1; }
	uv sync --locked
	@touch $(STAMP)

uv.lock:
	@echo "Missing uv.lock: run uv lock deliberately and commit it." >&2
	@exit 1

$(OUT): src/build_map.py $(GEOJSON) data/transit_model.json $(wildcard data/reachability.json) | deps
	$(PY) src/build_map.py

# Depends on data/reachability.json when present so a fresh `make data`
# re-contours; `make clean` removes it to fall back to data/transit_model.json.
$(GEOJSON): src/build_isochrones.py data/transit_model.json $(wildcard data/reachability.json) | deps
	$(PY) src/build_isochrones.py

test: | deps
	$(PY) -m pytest -q

# Clip the raw OSM download to the GTHA bbox (needs osmium: `brew install
# osmium-tool`). R5 rejects extents above ~975,000 km2, so this is required.
osm: $(OSM_PBF)

$(OSM_PBF): $(OSM_RAW)
	osmium extract -b $(BBOX) $(OSM_RAW) -o $(OSM_PBF) --overwrite

# Network step: real multimodal transit routing with r5py (RAPTOR over OSM +
# GTFS). Needs Java 21 + osmium (see README). Downloads feeds and OSM, then clips
# extract, then writes data/reachability.json, which build_isochrones.py
# contours and build_map.py renders.
# Fetching first installs this project's dependencies if needed.
data: deps
	$(PY) src/fetch_data.py
	$(MAKE) all

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

# Remove generated outputs incl. the r5py grid, so the next plain `make` rebuilds
# from the committed curated model. Re-run `make data` to regenerate the grid.
clean:
	rm -f $(OUT) $(GEOJSON) data/reachability.json

# Explicitly discard installed dependencies; the next make installs them anew.
clean-deps:
	rm -rf $(VENV)

# Compatibility with the previous target name.
clean-venv: clean-deps
