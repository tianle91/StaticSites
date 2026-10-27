PROJECT := toronto-crime-map

include ../python-project.mk

$(OUT): src/build_site.py src/map.html src/map.js $(wildcard data/*)
	$(PY) src/build_site.py
