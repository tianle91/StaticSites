# Offline artifact build; standard targets come from the shared template.
PROJECT := trca-flood-plain-map
include ../python-project.mk

$(OUT): src/build_site.py src/page.html data/floodplain.json
	$(PY) src/build_site.py
