# Shared project commands; one root Python environment, project-local artifacts.
.DEFAULT_GOAL := all
include $(dir $(lastword $(MAKEFILE_LIST)))environment.mk
PROJECT ?= $(notdir $(CURDIR))
OUT ?= output/$(PROJECT).html
OUTPUTS ?= $(OUT)
OPEN_FILE ?= $(OUT)
CLEAN_FILES ?= $(OUTPUTS)
FETCH_SCRIPT ?= src/fetch_data.py
PYTEST_ARGS ?= -q
SNAPSHOT_SCRIPT ?=
SHARED_INPUTS := $(shell find $(REPO_ROOT)/src/staticsites -type f \( -name '*.py' -o -name '*.js' -o -name '*.css' -o -name '*.html' \))

.PHONY: all test data open clean
all: $(OUTPUTS) | deps
# UI changes rebuild pages/images, not data-derived artifacts (e.g. routed
# GeoJSON whose optional raw inputs may be unavailable in a checkout).
SHARED_OUTPUTS ?= $(filter %.html %.png,$(OUTPUTS))
$(SHARED_OUTPUTS): $(SHARED_INPUTS)
$(OUTPUTS): | deps

test: | deps
	$(PY) -m pytest $(PYTEST_ARGS)

data: deps
	$(PY) $(FETCH_SCRIPT)
	$(MAKE) all

open: $(OPEN_FILE) | deps
	open $(OPEN_FILE) 2>/dev/null || xdg-open $(OPEN_FILE) 2>/dev/null || echo "Open $(OPEN_FILE) manually."

clean:
	rm -f $(CLEAN_FILES)

ifneq ($(strip $(SNAPSHOT_SCRIPT)),)
.PHONY: snapshots snapshot-browser browser-test
snapshot-browser: deps
	$(PY) -m playwright install --only-shell chromium
snapshots: all
	$(PY) $(SNAPSHOT_SCRIPT)
browser-test: deps
	$(PY) -m pytest -q -c "$(REPO_ROOT)/pyproject.toml" "$(REPO_ROOT)/tests/browser_snapshots.py"
endif
