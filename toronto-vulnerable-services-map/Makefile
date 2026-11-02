# Artifact configuration; recipes and environment management are shared.
PROJECT := toronto-vulnerable-services-map
BUILD_SCRIPT := src/build_map.py
DATA_INPUTS := data/services.json $(wildcard data/shelters.json data/geocode_cache.json)
SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../artifact-project.mk
