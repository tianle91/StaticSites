# Repo-admin targets only -- NOT a project build system.
#
# Every project is still fully self-contained (its own Makefile, venv, deps); see
# AGENTS.md. This root Makefile handles metadata bookkeeping and delegates
# explicit setup/refresh operations to independent projects.
# Root data/deps only delegate; build/test targets remain per project.
#
# CI discovers projects with `*/Makefile` (one level deep), so this root Makefile
# is invisible to that glob and never becomes a phantom project.

.PHONY: manifest check help data deps

# Regenerate the committed sites.json from every project's pyproject.toml.
manifest:
	./generate_manifest.py

# Verify sites.json and scheduled-refresh metadata (what CI runs).
check:
	./generate_manifest.py --check
	./refresh_projects.py check
	python3 -m unittest discover -s admin_tests

help:
	@echo "make data      - refresh and rebuild every project"
	@echo "make deps      - synchronize every project environment from its lockfile"
	@echo "make manifest  - regenerate sites.json from the projects' metadata"
	@echo "make check     - validate sites.json and project refresh metadata"

# Explicit networked operations; discovery follows CI's */Makefile convention.
data deps:
	python3 run_projects.py $@
