# Repo-level convenience targets. Each project is independent and is normally
# built from its own directory (`cd <project> && make`); these targets just fan
# out across all of them.
include common.mk

PROJECTS := margin-sp500-m2-visualization \
            ontario-physiotherapy-clinics-map \
            toronto-vulnerable-services-map \
            union-station-transit-isochrone

.PHONY: all test clean clean-venv

# Build every project. `venv` first so the shared environment is synced once
# rather than raced by each sub-make.
all: venv
	@for p in $(PROJECTS); do echo "==> $$p"; $(MAKE) -C $$p || exit 1; done

# Run every project's tests. toronto-vulnerable-services-map has none.
test: venv
	@for p in margin-sp500-m2-visualization ontario-physiotherapy-clinics-map union-station-transit-isochrone; do \
		echo "==> $$p"; $(MAKE) -C $$p test || exit 1; \
	done

clean:
	@for p in $(PROJECTS); do $(MAKE) -C $$p clean; done

# Delete the shared virtualenv; the next `make` recreates it via `uv sync`.
clean-venv:
	rm -rf $(VENV)
