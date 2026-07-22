# Build a self-contained interactive map of Ontario's publicly-funded
# physiotherapy clinics. The code is stdlib-only; it runs on the repo's shared
# virtualenv (../.venv) just to get a modern interpreter.
include ../common.mk

.PHONY: all data test open clean

# Default target: one-shot build of the map (offline, no dependencies).
all: index.html

# Regression tests for the address cleaner (stdlib only, no network).
test: | $(PY)
	$(PY) test_clean_street.py

index.html: build_map.py clinics.json | $(PY)
	$(PY) build_map.py

# Network step: pull the clinic list from Ontario's open-data CKAN datastore and
# geocode every address (cached on disk), then rebuild. Requires internet; the
# first run takes ~5 min because Nominatim allows only 1 request/second.
data: | $(PY)
	$(PY) fetch_data.py
	$(PY) build_map.py

# Build then open in the default browser (macOS `open`, fallback to xdg-open).
open: index.html
	open index.html 2>/dev/null || xdg-open index.html 2>/dev/null || echo "Open index.html manually."

clean:
	rm -f index.html
