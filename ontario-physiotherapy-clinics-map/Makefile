# Artifact configuration; recipes and environment management are shared.
PROJECT := ontario-physiotherapy-clinics-map
BUILD_SCRIPT := src/build_map.py
DATA_INPUTS := data/clinics.json $(wildcard data/geocode_cache.json)
SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../artifact-project.mk
