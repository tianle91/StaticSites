# Interactive map of Toronto/Ontario services for vulnerable populations.
# Run from this directory: cd toronto-vulnerable-services-map && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := toronto-vulnerable-services-map
VENV  := .venv
PY    := $(VENV)/bin/python
STAMP := $(VENV)/.stamp
OUT   := output/$(PROJECT).html

.PHONY: all deps test data open clean clean-deps clean-venv

# Default target: one-shot offline build from the committed data/.
all: $(OUT)

# Create/refresh .venv from pyproject.toml. The stamp keeps `uv sync` from
# re-running on every build once the tree is warm.
# Install from the lockfile only when the environment is new or manifests change.
# Reset a damaged environment explicitly with `make clean-deps && make deps`.
deps: $(STAMP)
	@test -x $(PY) || { echo "Environment incomplete: run make clean-deps then make deps." >&2; exit 1; }

$(STAMP): pyproject.toml uv.lock
	@command -v uv >/dev/null || { echo "Install uv before running make deps." >&2; exit 1; }
	uv sync --locked
	@touch $(STAMP)

uv.lock:
	@echo "Missing uv.lock: run uv lock deliberately and commit it." >&2
	@exit 1

$(OUT): src/build_map.py data/services.json $(wildcard data/shelters.json data/geocode_cache.json) | $(STAMP)
	$(PY) src/build_map.py

test: | $(STAMP)
	$(PY) -m pytest -q

# Network step: geocode curated addresses + pull every shelter location from the
# Toronto Open Data API (cached in data/geocode_cache.json), then rebuild.
# Fetching first installs this project's dependencies if needed.
data: deps
	$(PY) src/fetch_data.py
	$(MAKE) all

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

clean:
	rm -f $(OUT)

# Explicitly discard installed dependencies; the next make installs them anew.
clean-deps:
	rm -rf $(VENV)

# Compatibility with the previous target name.
clean-venv: clean-deps
