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

.PHONY: all system-deps deps test data open clean clean-deps clean-venv

# Default target: one-shot offline render from the committed data/series.csv.
all: $(OUT) $(OUT_PNG) | deps

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
# Order-only deps prerequisites validate even current outputs without rebuilding them.
deps: $(STAMP)
	@test -x $(PY) || { echo "Environment incomplete: run make clean-deps then make deps." >&2; exit 1; }

$(STAMP): pyproject.toml uv.lock
	@command -v uv >/dev/null || { echo "Install uv (make system-deps on macOS) before running make deps." >&2; exit 1; }
	uv sync --locked
	@touch $(STAMP)

uv.lock:
	@echo "Missing uv.lock: run uv lock deliberately and commit it." >&2
	@exit 1

$(OUT): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt) | deps
	$(PY) $(SCRIPT) -o $(OUT)

$(OUT_PNG): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt) | deps
	$(PY) $(SCRIPT) -o $(OUT_PNG)

test: | deps
	$(PY) -m pytest -q

# Network step: refetch the FINRA / FRED / Yahoo series into data/series.csv,
# then re-render both charts.
# Fetching first installs this project's dependencies if needed.
data: deps
	$(PY) src/fetch_data.py
	$(MAKE) all

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

clean:
	rm -f $(OUT) $(OUT_PNG)

# Explicitly discard installed dependencies; the next make installs them anew.
clean-deps:
	rm -rf $(VENV)

# Compatibility with the previous target name.
clean-venv: clean-deps
