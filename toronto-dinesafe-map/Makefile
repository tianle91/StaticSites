# Toronto Dinesafe Map.
# Run from this directory: cd toronto-dinesafe-map && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := toronto-dinesafe-map

include ../python-project.mk

$(OUT): src/build_map.py data/dinesafe.json $(wildcard data/geocode_cache.json)
	$(PY) src/build_map.py
