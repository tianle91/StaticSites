# Artifact configuration; recipes and environment management are shared.
PROJECT := margin-sp500-m2-visualization
BUILD_SCRIPT := src/plot_macro_series.py
DATA_INPUTS := data/series.csv $(wildcard data/generated_at.txt)
ARTIFACT_FORMATS := html png
BUILD_OUTPUT_FLAG := -o
BUILD_INPUTS := $(BUILD_SCRIPT)
SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../artifact-project.mk
