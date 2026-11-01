# Offline artifact build; standard targets come from the shared template.
PROJECT := trca-flood-plain-map
SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../python-project.mk

$(OUT): $(wildcard src/*.html src/*.js src/*.css src/vendor/*) src/build_site.py src/page.html data/floodplain.json
	$(PY) src/build_site.py
