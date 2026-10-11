# FINRA margin debt vs. S&P 500 / M2 / CPI / PPI, rebased to an anchor date.
# Run from this directory: cd margin-sp500-m2-visualization && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := margin-sp500-m2-visualization
VENV  := .venv
PY    := $(VENV)/bin/python
STAMP := $(VENV)/.stamp
OUT     := output/$(PROJECT).html
OUT_PNG := output/$(PROJECT).png
SCRIPT  := src/plot_macro_series.py

.PHONY: all deps test data open clean clean-venv

# Default target: one-shot offline render from the committed data/series.csv.
all: $(OUT) $(OUT_PNG)

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

$(OUT): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt) | $(STAMP)
	$(PY) $(SCRIPT) -o $(OUT)

$(OUT_PNG): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt) | $(STAMP)
	$(PY) $(SCRIPT) -o $(OUT_PNG)

test: | $(STAMP)
	$(PY) -m pytest -q

# Network step: refetch the FINRA / FRED / Yahoo series into data/series.csv,
# then re-render both charts.
data: | $(STAMP)
	$(PY) src/fetch_data.py
	$(MAKE) all

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

clean:
	rm -f $(OUT) $(OUT_PNG)

clean-venv:
	rm -rf $(VENV)
