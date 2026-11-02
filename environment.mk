# One repository environment. Included by root and project Makefiles.
REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV ?= $(REPO_ROOT)/.venv
ENV_DIR := $(abspath $(if $(filter /%,$(VENV)),$(VENV),$(REPO_ROOT)/$(VENV)))
PY ?= $(ENV_DIR)/bin/python
STAMP ?= $(ENV_DIR)/.stamp
BREW_FORMULAE ?= uv
BREW_CASKS ?=

.PHONY: deps clean-deps clean-venv system-deps
deps: $(STAMP)
	@test -x "$(PY)" || { echo "Environment incomplete: run make clean-deps then make deps at the repo root." >&2; exit 1; }

$(STAMP): $(REPO_ROOT)/pyproject.toml $(REPO_ROOT)/uv.lock $(REPO_ROOT)/.python-version
	@command -v uv >/dev/null || { echo "Install uv (make system-deps on macOS) before make deps." >&2; exit 1; }
	cd "$(REPO_ROOT)" && UV_PROJECT_ENVIRONMENT="$(ENV_DIR)" uv sync --locked --all-groups
	@mkdir -p "$(dir $(STAMP))"
	@touch "$(STAMP)"

$(REPO_ROOT)/uv.lock:
	@echo "Missing root uv.lock: run uv lock deliberately and commit it." >&2
	@exit 1

# Explicitly affects the shared environment, regardless of calling directory.
clean-deps:
	@case "$(ENV_DIR)" in "$(REPO_ROOT)"/.venv|"$(REPO_ROOT)"/.venv-*|"$(REPO_ROOT)"/.venv/*) ;; *) echo "Refusing unsafe environment cleanup; use a .venv-style directory inside the repository." >&2; exit 1;; esac
	rm -f "$(STAMP)"
	rm -rf "$(ENV_DIR)"
clean-venv: clean-deps

system-deps:
	@test "$$(uname -s)" = Darwin || { echo "system-deps supports macOS with Homebrew; see README for manual prerequisites." >&2; exit 1; }
	@command -v brew >/dev/null || { echo "Install Homebrew from https://brew.sh before running make system-deps." >&2; exit 1; }
ifneq ($(strip $(BREW_FORMULAE)),)
	brew install $(BREW_FORMULAE)
endif
ifneq ($(strip $(BREW_CASKS)),)
	brew install --cask $(BREW_CASKS)
endif
