# Shared build settings for every project in this repo.
#
# Each project's Makefile starts with `include ../common.mk` and then uses $(PY)
# instead of a bare `python3`. That keeps every project on the single repo-level
# virtualenv (../.venv) described by the root pyproject.toml -- no project has
# its own venv or requirements file.

# Every Makefile includes this file first, which would otherwise make `venv` (the
# first target defined below) the default goal. Every project defines `all`.
.DEFAULT_GOAL := all

# Absolute path to the repo root: the directory holding this file.
REPO_ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
VENV      := $(REPO_ROOT)/.venv
PY        := $(VENV)/bin/python

# Create/refresh the shared virtualenv. `uv sync` is a no-op on a warm tree, so
# build targets can depend on it for free; it needs the network only when the
# lockfile or pyproject.toml changed.
.PHONY: venv
venv:
	@cd $(REPO_ROOT) && uv sync

$(PY):
	@cd $(REPO_ROOT) && uv sync
