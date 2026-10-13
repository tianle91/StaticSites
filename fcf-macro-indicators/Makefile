# Free cash flow vs. M2 / S&P 500 / the Treasury curve, rebased to an anchor date.
# Run from this directory: cd fcf-macro-indicators && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := fcf-macro-indicators
OUT_PNG := output/$(PROJECT).png
OUTPUTS := output/$(PROJECT).html $(OUT_PNG)
SCRIPT := src/plot_fcf_macro.py

include ../python-project.mk

$(OUT): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt)
	$(PY) $(SCRIPT) -o $(OUT)

$(OUT_PNG): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt)
	$(PY) $(SCRIPT) -o $(OUT_PNG)
