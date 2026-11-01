# Canada Mortgage Stress.
# Run from this project: cd canada-mortgage-stress && make
# Shared Python/uv targets live in ../python-project.mk; build rules stay here.

PROJECT := canada-mortgage-stress

SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../python-project.mk

$(OUT): $(wildcard src/*.py src/*.html src/*.css src/*.js) data/series.json
	$(PY) src/build_site.py
