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
deps: $(STAMP)

$(STAMP): pyproject.toml $(wildcard uv.lock)
	uv sync
	@touch $@

$(OUT): $(SCRIPT) data/series.csv | $(STAMP)
	$(PY) $(SCRIPT) -o $(OUT)

$(OUT_PNG): $(SCRIPT) data/series.csv | $(STAMP)
	$(PY) $(SCRIPT) -o $(OUT_PNG)

test: | $(STAMP)
	$(PY) -m pytest -q

# Network step: refetch the FINRA / FRED / Yahoo series into data/series.csv,
# then re-render both charts.
data: | $(STAMP)
	$(PY) src/fetch_data.py
	$(PY) $(SCRIPT) -o $(OUT)
	$(PY) $(SCRIPT) -o $(OUT_PNG)

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

clean:
	rm -f $(OUT) $(OUT_PNG)

clean-venv:
	rm -rf $(VENV)
