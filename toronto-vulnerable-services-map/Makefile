# Interactive map of Toronto/Ontario services for vulnerable populations.
# Run from this directory: cd toronto-vulnerable-services-map && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := toronto-vulnerable-services-map
VENV  := .venv
PY    := $(VENV)/bin/python
STAMP := $(VENV)/.stamp
OUT   := output/$(PROJECT).html

.PHONY: all deps test data open clean clean-venv

# Default target: one-shot offline build from the committed data/.
all: $(OUT)

# Create/refresh .venv from pyproject.toml. The stamp keeps `uv sync` from
# re-running on every build once the tree is warm.
deps: $(STAMP)

$(STAMP): pyproject.toml $(wildcard uv.lock)
	uv sync
	@touch $@

$(OUT): src/build_map.py data/services.json data/shelters.json | $(STAMP)
	$(PY) src/build_map.py

test: | $(STAMP)
	$(PY) -m pytest -q

# Network step: geocode curated addresses + pull every shelter location from the
# Toronto Open Data API (cached in data/geocode_cache.json), then rebuild.
data: | $(STAMP)
	$(PY) src/fetch_data.py
	$(PY) src/build_map.py

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

clean:
	rm -f $(OUT)

clean-venv:
	rm -rf $(VENV)
