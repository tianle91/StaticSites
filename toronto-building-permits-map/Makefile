# Offline artifact build; standard targets come from the shared template.
PROJECT := toronto-building-permits-map
include ../python-project.mk

$(OUT): $(wildcard src/*.html src/*.js src/*.css src/vendor/*) src/build_site.py src/page.html data/permits.json
	$(PY) src/build_site.py
