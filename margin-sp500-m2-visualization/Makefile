# FINRA margin debt vs. S&P 500 / M2 / CPI / PPI, rebased to an anchor date.
# Run from this directory: cd margin-sp500-m2-visualization && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := margin-sp500-m2-visualization
OUT_PNG := output/$(PROJECT).png
OUTPUTS := output/$(PROJECT).html $(OUT_PNG)
SCRIPT := src/plot_macro_series.py

include ../python-project.mk

$(OUT): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt)
	$(PY) $(SCRIPT) -o $(OUT)

$(OUT_PNG): $(SCRIPT) data/series.csv $(wildcard data/generated_at.txt data/fcf_source.txt)
	$(PY) $(SCRIPT) -o $(OUT_PNG)
