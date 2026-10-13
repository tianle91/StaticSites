# Interactive map of Ontario's publicly-funded physiotherapy clinics.
# Run from this directory: cd ontario-physiotherapy-clinics-map && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := ontario-physiotherapy-clinics-map
VENV  := .venv
PY    := $(VENV)/bin/python
STAMP := $(VENV)/.stamp
OUT   := output/$(PROJECT).html

.PHONY: all system-deps deps test data open clean clean-deps clean-venv

# Default target: one-shot offline build from the committed data/.
all: $(OUT)

# System installation is explicit and separate from Python setup and data refresh.
# Homebrew itself is an operator prerequisite; see README for other platforms.
system-deps:
	@test "$$(uname -s)" = Darwin || { echo "system-deps supports macOS with Homebrew; see README for manual prerequisites." >&2; exit 1; }
	@command -v brew >/dev/null || { echo "Install Homebrew from https://brew.sh before running make system-deps." >&2; exit 1; }
	brew install uv

# Create/refresh .venv from pyproject.toml. The stamp keeps `uv sync` from
# re-running on every build once the tree is warm.
# Install from the lockfile only when the environment is new or manifests change.
# Reset a damaged environment explicitly with `make clean-deps && make deps`.
deps: $(STAMP)
	@test -x $(PY) || { echo "Environment incomplete: run make clean-deps then make deps." >&2; exit 1; }

$(STAMP): pyproject.toml uv.lock
	@command -v uv >/dev/null || { echo "Install uv (make system-deps on macOS) before running make deps." >&2; exit 1; }
	uv sync --locked
	@touch $(STAMP)

uv.lock:
	@echo "Missing uv.lock: run uv lock deliberately and commit it." >&2
	@exit 1

$(OUT): src/build_map.py data/clinics.json $(wildcard data/geocode_cache.json) | $(STAMP)
	$(PY) src/build_map.py

test: | $(STAMP)
	$(PY) -m pytest -q

# Network step: pull the clinic list from Ontario's open-data CKAN datastore and
# geocode every address (cached in data/geocode_cache.json), then rebuild. The
# first run takes ~5 min because Nominatim allows only 1 request/second.
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
