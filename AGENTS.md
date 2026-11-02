# AGENTS.md

Coding guidance for StaticSites. Humans: see README.md.

## Architecture and standalone outputs

Projects have local source, data, tests, configuration and committed outputs.
They share **one repository Python environment** and the build-time package in
`src/staticsites/`. This supersedes the former independent-environment/local-copy
model. Do not import another project's code; extract reusable behavior into the
shared package instead. Read each project's README before editing it.

The deliverable is still a standalone static site: embed application JS, CSS,
data and shared components into `output/<project>.html`. A deployed artifact
must never need Python, this checkout, the root package, or a component server.
Retain documented map CDN/tile dependencies; charts are self-contained/offline.
Secondary artifacts share the project stem. Commit outputs whenever builders or
shared assets change. Every generated page names and links its data sources.
JSON in data and HTML is readable with `indent=2`, never minified.

## Environment and Make contract

- Root `pyproject.toml`, `uv.lock`, and `.venv` are the sole Python dependency
  manifest, lock and normal environment. Root `uv sync --locked --all-groups`
  installs the editable shared package and complete dev/plots/maps/transit groups.
- `environment.mk` owns setup/cleanup. Common project Makefiles declare their
  builder/inputs/formats and include `../artifact-project.mk`, which includes
  `python-project.mk`. Transit adds its own geometry/clipping rules and limits
  the common artifact recipe to its HTML output.
  Scripts resolve paths from their own project root.
- `make deps` from any project uses the root environment. Install only if the
  shared stamp is missing or the root manifests changed. Do not probe packages,
  auto-repair environments, or force synchronization when the stamp is current.
  Missing/incomplete environments fail with an explicit cleanup instruction.
- Root `make clean-deps && make deps` explicitly recreates the shared environment;
  the project aliases do the same. Preserve inputs, geocode caches, lockfiles,
  sources, outputs and review images. Do not silently delete legacy project envs.
- Add dependencies **from the repo root** using `uv add` or `uv add --group`.
  Declare directly used libraries and explain their role. Update locks deliberately;
  missing/stale locks fail rather than being rewritten by build/test commands.
- Use `$(PY)` in recipes, never system Python, pip, or manual venv creation for
  project work. Stdlib-only repo-admin entry scripts may bootstrap on system 3.9.
- `VENV=.venv-ci` selects one alternate environment relative to the repository,
  shared by metadata and all projects. It is not relative to the current project.
- System tools install only through explicit `make system-deps`. Homebrew must
  already exist on macOS; fail clearly otherwise. Transit configures Java 21 and
  osmium-tool. Other targets never install system tools or obtain credentials.

Every project implements `all` (default), `deps`, `system-deps`, `test`, `data`,
`open`, `clean`, `clean-deps`, and `clean-venv`. `all` builds committed inputs,
`test` runs pytest, `data` refreshes all required inputs then recursively builds,
`clean` removes only declared generated artifacts. Project Makefiles hold their
own build prerequisites and configuration. Shared assets/Python sources are Make
prerequisites so edits rebuild outputs. Root data/refresh dispatches to projects
and continues after failures, returning nonzero when any fail.

## Shared components

- `staticsites.assets` and `assets/maps/`: safe JSON embedding, map controls, tab markup, styles,
  location/fit actions, mobile panels/dialogs. Search fields and ranking remain
  configurable by project; never assume all maps search only by address.
- `staticsites.charts` and `assets/plots/`: native SVG plots, legends, shared
  time scale/inspection, page/provenance components and Matplotlib styling.
  Keep data definitions, units, aggregation and special dual-axis logic local.
- `staticsites.timeseries`: CSV loading, provenance and rebasing mechanics;
  callers choose the monthly/quarterly period policy explicitly.
- `staticsites.pipeline`: content-aware atomic publication, provenance and caches.
- `staticsites.sources` / `geocoding`: HTTP, CKAN/ArcGIS envelopes and rate limits.
  Keep source-specific parsing, validation, geographic fallbacks and joins local.
- `staticsites.snapshots`: common browser capture with explicit map/chart policies.

Prefer small modules over a configurable framework. Extract real repetition,
retain project-specific hooks, and test behavior at the shared boundary. Assets
ship in the package, but are embedded into generated pages at build time.

## Data refresh and persistence

Only explicit `make data` / `make refresh` fetches datasets. Build/test stay
strictly offline once dependencies are installed. Do not run data refresh as a
routine check. Validate every required input before publishing; required-source
failures must not publish partial datasets. Normalize unordered records and
preserve bytes, timestamps and mtimes when content is unchanged. Restore missing
sidecars. Keep all successful geocodes and cache genuine no-matches; never cache
service failures. Preserve large ignored OSM/GTFS inputs and document acquisition
in project data READMEs. Credentials remain operator-supplied.

## Layout, metadata and scaffolding

Always scaffold new projects with `./new-project.py <slug>`. Standard layout:
`README.md`, `site.toml`, `pytest.ini`, `Makefile`, project-specific `.gitignore`,
`src/`, `tests/`, `data/`, and `output/`. There are no project pyproject/lockfiles.
Update the scaffolder whenever the standard changes.

`site.toml` declares `[site].name` (directory slug), `title`, and `description`.
Description starts with `"<title> — "`; generate_manifest.py strips that prefix
and preserves the downstream `sites.json` schema. Run `make manifest` and commit
it after adding projects or changing metadata. Builds run within the checkout.
Tests import local `src/` via pytest.ini, never sys.path hacks or conftest.py.
Run project suites in separate processes to avoid local module-name collisions.

## Verification, snapshots and CI

Run `make -C <project> test all` for affected projects, `make check` for shared
code/admin changes, and `make test STATUSES=off` after root lock/shared component
changes. Root CI discovers `*/Makefile`, runs shared/admin checks and each local
suite/build, and continues after independent failures. Do not fetch live datasets.

Snapshot-enabled projects set SNAPSHOT_SCRIPT and provide `snapshot-browser`,
`snapshots`, `browser-test`. Browser setup is explicit and never triggered by
ordinary builds/tests/data refreshes. Capture serves loopback in fresh light-mode
contexts at desktop 1440×900 and mobile 390×844, waits for fonts/rendering/stable
geometry, rejects overflow/errors and publishes only after both views succeed.
Maps may load existing external scripts/tiles; chart capture blocks external
requests. This is the explicit exception to data-only network fetching. Store
review JPEGs under `tests/snapshots/`, review and commit after visual changes.
Browser fixtures are explicit; ordinary pytest never launches/downloads browsers.

`STATUSES=off` never contacts GitHub. `auto` publishes local-ci/metadata and
local-ci/<project> only for clean pushed commits; `required` refuses dirty state.
Pin HEAD and verify tracked/untracked changes before success publication; status
API failures return nonzero. Keep logs ignored in `.local-ci/<sha>/`. No hosted
workflows. Use the existing gh session/keychain; a sandboxed auth failure does
not prove the login is broken. Retry with normal keychain access before asking
for authentication, and never print tokens.
