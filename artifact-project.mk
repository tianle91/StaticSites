# Declarative artifact rules for the common single-builder projects.
# Specialized workflows (transit routing/clipping) keep their own rules.
PROJECT ?= $(notdir $(CURDIR))
BUILD_SCRIPT ?= src/build_site.py
BUILD_INPUTS ?= $(wildcard src/*.py src/*.html src/*.css src/*.js src/vendor/*)
DATA_INPUTS ?=
ARTIFACT_FORMATS ?= html
BUILD_OUTPUT_FLAG ?=
BUILD_ARGS ?=
BUILD_CONFIG_INPUTS ?= $(filter %.mk %Makefile,$(MAKEFILE_LIST))
OUTPUTS ?= $(addprefix output/$(PROJECT).,$(ARTIFACT_FORMATS))
BUILD_OUTPUTS ?= $(OUTPUTS)

include $(dir $(lastword $(MAKEFILE_LIST)))python-project.mk

$(BUILD_OUTPUTS): $(BUILD_INPUTS) $(DATA_INPUTS) $(BUILD_CONFIG_INPUTS)
	$(PY) $(BUILD_SCRIPT) $(BUILD_ARGS) $(if $(BUILD_OUTPUT_FLAG),$(BUILD_OUTPUT_FLAG) "$@")
	@test -f "$@" || { echo "Builder did not produce $@" >&2; exit 1; }
# A byte-identical render is still a completed build of the changed sources.
# Refresh artifact mtime so content-aware publishers do not rerun forever.
	@touch "$@"
