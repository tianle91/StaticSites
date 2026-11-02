# Artifact configuration; recipes and environment management are shared.
PROJECT := toronto-dinesafe-map
BUILD_SCRIPT := src/build_map.py
DATA_INPUTS := data/dinesafe.json $(wildcard data/geocode_cache.json)
SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../artifact-project.mk
