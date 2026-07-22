# Build a self-contained interactive map of Toronto/Ontario services for
# vulnerable populations. The code is stdlib-only; it runs on the repo's shared
# virtualenv (../.venv) just to get a modern interpreter.
include ../common.mk

.PHONY: all data open clean

# Default target: one-shot build of the map (offline, no dependencies).
all: index.html

index.html: build_map.py services.json | $(PY)
	$(PY) build_map.py

# Network step: geocode addresses + pull every shelter location from the
# Toronto Open Data API (cached on disk), then rebuild. Requires internet.
data: | $(PY)
	$(PY) fetch_data.py
	$(PY) build_map.py

# Build then open in the default browser (macOS `open`, fallback to xdg-open).
open: index.html
	open index.html 2>/dev/null || xdg-open index.html 2>/dev/null || echo "Open index.html manually."

clean:
	rm -f index.html
