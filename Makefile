# Repo-admin targets only -- NOT a project build system.
#
# Every project is still fully self-contained (its own Makefile, venv, deps); see
# AGENTS.md. This root Makefile exists solely for repo-wide bookkeeping that has
# no home inside a single project: the sites.json manifest and refresh schedule.
# Do not add build/test/deps targets here -- those live per project.
#
# CI discovers projects with `*/Makefile` (one level deep), so this root Makefile
# is invisible to that glob and never becomes a phantom project.

.PHONY: manifest check help

# Regenerate the committed sites.json from every project's pyproject.toml.
manifest:
	./generate_manifest.py

# Verify sites.json and scheduled-refresh metadata (what CI runs).
check:
	./generate_manifest.py --check
	./refresh_projects.py check
	python3 -m unittest discover -s admin_tests

help:
	@echo "make manifest  - regenerate sites.json from the projects' metadata"
	@echo "make check     - validate sites.json and project refresh metadata"
