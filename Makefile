include environment.mk
# Repository entry points use one environment and delegate project builds/refreshes.
.DEFAULT_GOAL := help
PROJECTS := $(sort $(patsubst %/Makefile,%,$(wildcard */Makefile)))
STATUSES ?= auto

.PHONY: test data refresh manifest check help

# Dirty checkouts run locally; clean commits also get GitHub commit statuses.
# STATUSES=off is fully local; STATUSES=required refuses uncommitted changes.
test: deps
	./local_ci.py --statuses "$(STATUSES)" --venv "$(ENV_DIR)"

# Each project's data target already rebuilds all its declared outputs.
# Continue after a failure so every project gets an attempt.
data:
	@failed=0; for project in $(PROJECTS); do \
		$(MAKE) -C "$$project" data || failed=1; \
	done; exit $$failed

refresh: data

# Regenerate the committed sites.json from every project's site.toml.
manifest:
	./generate_manifest.py

# Verify sites.json and repo-admin tests.
check: deps
	./generate_manifest.py --check
	$(PY) -m unittest discover -s admin_tests
	$(PY) -m pytest -q tests

help:
	@echo "make test      - check metadata, test/build every project, report clean commits to GitHub"
	@echo "                 STATUSES=off: local only; STATUSES=required: require publishing"
	@echo "                 VENV=.venv-ci: use an alternate shared environment"
	@echo "make data      - refresh data and outputs for every project (network; refresh is an alias)"
	@echo "make manifest  - regenerate sites.json from the projects' site.toml metadata"
	@echo "make check     - validate sites.json and run repo-admin tests"
