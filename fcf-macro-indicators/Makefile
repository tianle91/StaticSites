# Artifact configuration; recipes and environment management are shared.
PROJECT := fcf-macro-indicators
BUILD_SCRIPT := src/plot_fcf_macro.py
DATA_INPUTS := data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt)
ARTIFACT_FORMATS := html png
BUILD_OUTPUT_FLAG := -o
BUILD_INPUTS := $(BUILD_SCRIPT)
SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../artifact-project.mk
