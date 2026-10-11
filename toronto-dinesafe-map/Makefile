# Toronto Dinesafe Map.
# Run from this directory: cd toronto-dinesafe-map && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := toronto-dinesafe-map
VENV  := .venv
PY    := $(VENV)/bin/python
STAMP := $(VENV)/.stamp
OUT   := output/$(PROJECT).html

.PHONY: all deps test data open clean clean-venv

# Default target: one-shot offline build from the committed data/.
all: $(OUT)

# Create/refresh .venv from pyproject.toml. The stamp keeps `uv sync` from
# re-running on every build once the tree is warm.
# Explicit setup repairs environment drift even when the stamp is current.
deps:
	@command -v uv >/dev/null || { echo "Install uv before running make deps." >&2; exit 1; }
	@test -f uv.lock || { echo "Missing uv.lock: run uv lock deliberately and commit it." >&2; exit 1; }
	uv sync --locked
	@touch $(STAMP)

# Ordinary commands use the fast path, but a leftover stamp cannot hide a
# missing interpreter. The lockfile is mandatory and is never rewritten here.
ifeq ($(wildcard $(PY)),)
.PHONY: $(STAMP)
endif
$(STAMP): pyproject.toml uv.lock
	$(MAKE) deps

uv.lock:
	@echo "Missing uv.lock: run uv lock deliberately and commit it." >&2
	@exit 1

$(OUT): src/build_map.py data/dinesafe.json $(wildcard data/geocode_cache.json) | $(STAMP)
	$(PY) src/build_map.py

test: | $(STAMP)
	$(PY) -m pytest -q

# Network step: refresh data/ from upstream, then rebuild. Everything that hits
# the network belongs here - `all` and `test` must stay offline.
data: | $(STAMP)
	$(PY) src/fetch_data.py
	$(MAKE) all

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

clean:
	rm -f $(OUT)

clean-venv:
	rm -rf $(VENV)
