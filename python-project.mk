# Shared Python/uv target contract. Include from a project's Makefile after its
# configuration variables; keep source/data prerequisites and build recipes local.
# Paths intentionally stay relative to the project (including with make -C).
.DEFAULT_GOAL := all

PROJECT ?= $(notdir $(CURDIR))
VENV ?= .venv
PY ?= $(VENV)/bin/python
STAMP ?= $(VENV)/.stamp
OUT ?= output/$(PROJECT).html
OUTPUTS ?= $(OUT)
OPEN_FILE ?= $(OUT)
CLEAN_FILES ?= $(OUTPUTS)
FETCH_SCRIPT ?= src/fetch_data.py
PYTEST_ARGS ?= -q
BREW_FORMULAE ?= uv
BREW_CASKS ?=

.PHONY: all system-deps deps test data open clean clean-deps clean-venv

all: $(OUTPUTS) | deps

# Phony validation must run even for current artifacts, but must not invalidate
# their timestamps. Projects add ordinary source/data prerequisites themselves.
$(OUTPUTS): | deps

# System installation is explicit; other targets never invoke this one.
# Homebrew itself is an operator prerequisite, with manual setup elsewhere.
system-deps:
	@test "$$(uname -s)" = Darwin || { echo "system-deps supports macOS with Homebrew; see README for manual prerequisites." >&2; exit 1; }
	@command -v brew >/dev/null || { echo "Install Homebrew from https://brew.sh before running make system-deps." >&2; exit 1; }
ifneq ($(strip $(BREW_FORMULAE)),)
	brew install $(BREW_FORMULAE)
endif
ifneq ($(strip $(BREW_CASKS)),)
	brew install --cask $(BREW_CASKS)
endif

# Install only for a new environment or changed manifests. A damaged existing
# environment requires explicit `make clean-deps && make deps`, never repair.
deps: $(STAMP)
	@test -x $(PY) || { echo "Environment incomplete: run make clean-deps then make deps." >&2; exit 1; }

$(STAMP): pyproject.toml uv.lock
	@command -v uv >/dev/null || { echo "Install uv (make system-deps on macOS) before running make deps." >&2; exit 1; }
	UV_PROJECT_ENVIRONMENT="$(VENV)" uv sync --locked
	@touch $(STAMP)

uv.lock:
	@echo "Missing uv.lock: run uv lock deliberately and commit it." >&2
	@exit 1

test: | deps
	$(PY) -m pytest $(PYTEST_ARGS)

# Keep the rebuild as a recursive invocation: refresh may create previously
# missing optional inputs, so their wildcard prerequisites must be re-evaluated.
data: deps
	$(PY) $(FETCH_SCRIPT)
	$(MAKE) all

open: $(OPEN_FILE) | deps
	open $(OPEN_FILE) 2>/dev/null || xdg-open $(OPEN_FILE) 2>/dev/null || echo "Open $(OPEN_FILE) manually."

clean:
	rm -f $(CLEAN_FILES)

# Dependency cleanup preserves inputs, caches, lockfiles, and output artifacts.
clean-deps:
	rm -rf $(VENV)

clean-venv: clean-deps
