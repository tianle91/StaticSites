PROJECT := toronto-crime-map

SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../python-project.mk

$(OUT): $(wildcard src/*.html src/*.js src/*.css src/vendor/*) src/build_site.py $(wildcard data/*)
	$(PY) src/build_site.py
