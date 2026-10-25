# Repository entry points delegate to independent project Makefiles.
# Rendering, fetching, tests and dependency environments remain project-local.
.DEFAULT_GOAL := help
PROJECTS := $(sort $(patsubst %/Makefile,%,$(wildcard */Makefile)))
STATUSES ?= auto
CI_VENV ?=

.PHONY: test data refresh refresh-due manifest check help

# Dirty checkouts run locally; clean commits also get GitHub commit statuses.
# STATUSES=off is fully local; STATUSES=required refuses uncommitted changes.
test:
	./local_ci.py --statuses "$(STATUSES)" $(if $(CI_VENV),--venv "$(CI_VENV)")

# Explicit full refresh includes projects whose scheduled refresh is disabled.
# Each project's data target already rebuilds all its declared outputs.
# Continue after a failure so every independent project gets an attempt.
data:
	@failed=0; for project in $(PROJECTS); do \
		$(MAKE) -C "$$project" data || failed=1; \
	done; exit $$failed

refresh: data

# Optional local use of the source-controlled per-project cadence.
refresh-due:
	./refresh_projects.py run

# Regenerate the committed sites.json from every project's pyproject.toml.
manifest:
	./generate_manifest.py

# Verify sites.json, refresh metadata, and repo-admin tests.
check:
	./generate_manifest.py --check
	./refresh_projects.py check
	python3 -m unittest discover -s admin_tests

help:
	@echo "make test      - check metadata, test/build every project, report clean commits to GitHub"
	@echo "                 STATUSES=off: local only; STATUSES=required: require publishing"
	@echo "                 CI_VENV=.venv/ci-verification: use separate per-project environments"
	@echo "make data      - refresh data and outputs for every project (network; refresh is an alias)"
	@echo "make refresh-due - refresh/test/build only projects due under their metadata"
	@echo "make manifest  - regenerate sites.json from the projects' metadata"
	@echo "make check     - validate sites.json and project refresh metadata"
