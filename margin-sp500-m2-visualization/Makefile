# FINRA margin debt vs. S&P 500 / M2 / CPI / PPI, rebased to an anchor date.
# Run from this directory: cd margin-sp500-m2-visualization && make
# Dependencies come from the repo's shared virtualenv (../.venv).
include ../common.mk

SCRIPT := src/plot_macro_series.py
OUTPUT := output/margin_sp500_m2_2000.png
OUTPUT_HTML := output/margin_sp500_m2_2000.html

.PHONY: all plot html test clean

all: plot html

plot: | $(PY)
	$(PY) $(SCRIPT) -o $(OUTPUT)

html: | $(PY)
	$(PY) $(SCRIPT) -o $(OUTPUT_HTML)

test: | $(PY)
	PYTHONPATH=src $(PY) -m unittest discover -s tests -p 'test_*.py' -v

clean:
	rm -f $(OUTPUT) $(OUTPUT_HTML)
