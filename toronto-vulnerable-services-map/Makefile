# Interactive map of Toronto/Ontario services for vulnerable populations.
# Run from this directory: cd toronto-vulnerable-services-map && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := toronto-vulnerable-services-map

include ../python-project.mk

$(OUT): src/build_map.py data/services.json $(wildcard data/shelters.json data/geocode_cache.json)
	$(PY) src/build_map.py
