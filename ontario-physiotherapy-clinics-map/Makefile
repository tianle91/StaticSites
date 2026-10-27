# Interactive map of Ontario's publicly-funded physiotherapy clinics.
# Run from this directory: cd ontario-physiotherapy-clinics-map && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := ontario-physiotherapy-clinics-map

include ../python-project.mk

$(OUT): $(wildcard src/*.html src/*.js src/*.css src/vendor/*) src/build_map.py data/clinics.json $(wildcard data/geocode_cache.json)
	$(PY) src/build_map.py
