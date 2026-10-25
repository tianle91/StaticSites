# AGENTS.md

Guidance for coding agents working in this repo. Humans: see [README.md](README.md).

## Repo shape: independent projects

This is a **multi-project repo, not a monorepo of one system**. Refer to the
independent sites as **projects**. Each project lives in its own top-level directory:

- `fcf-macro-indicators/`
- `margin-sp500-m2-visualization/`
- `ontario-physiotherapy-clinics-map/`
- `toronto-building-permits-map/`
- `toronto-dinesafe-map/`
- `toronto-vulnerable-services-map/`
- `trca-flood-plain-map/`
- `union-station-transit-isochrone/`

Projects have separate source, data, dependencies, environments, and outputs.
No project imports another project's code, and there is no repo-level virtualenv
or Python dependency manifest. Python/uv projects share only the Make target
contract in [`python-project.mk`](python-project.mk). Build within the repository
checkout: a project copied out by itself needs that shared file too. Duplicate
source helpers rather than introducing a shared Python package. Read a project's
own `README.md` before changing it.

The shared Make template is the only runtime dependency on repo-level code.
Repo-admin tools remain separate from project builds:

- [`python-project.mk`](python-project.mk) — shared Python/uv recipes included by
  project Makefiles; configuration and artifact build rules stay project-local.

- [`new-project.py`](new-project.py) — the scaffolder (see below).
- [`generate_manifest.py`](generate_manifest.py) — regenerates
  [`sites.json`](sites.json) from the projects' metadata (see "Site-listing
  metadata" below).
- [`Makefile`](Makefile) — root `test` delegates checks/builds to each project;
  root `data` (alias `refresh`) delegates each project's data-and-output refresh.
  `manifest`, `check`, `refresh-due`, and `help` support repo administration.
  Rendering, data preparation and dependency recipes remain project-local.
- [`local_ci.py`](local_ci.py) — stdlib-only local CI orchestration and GitHub
  commit statuses. Discovery uses one-level-deep `*/Makefile`, never the root
  Makefile or shared `.mk` template. There are no GitHub Actions workflows.

## Creating a project

**Always scaffold; never hand-roll the directory.**

```bash
./new-project.py my-new-map
```

That writes the full standard layout (including an initial `uv.lock`) and a
working end-to-end placeholder, so
`cd my-new-map && make && make test` passes immediately. Root `make test` and
`make data` discover it automatically.
Then replace `src/fetch_data.py` (the real upstream fetch),
`src/build_site.py` (the real rendering), and the `TODO`s in the project's
`README.md`, and add a row to the table in [README.md](README.md).

The script is stdlib-only and runs on the system `python3` on purpose — there is
no environment to set up before you can use it.

**If you change the standard, change the scaffolder too.** Its templates are the
executable copy of everything specified below; a divergence between them means
the next project starts out wrong.

## The standard layout

Every project has exactly this shape. It is what makes CI generic and what lets a
reader open any project and already know where things are.

```
<project>/
  README.md        # what it is, data sources, caveats
  Makefile         # the target contract below
  pyproject.toml   # dependencies + pytest config
  uv.lock          # committed
  .gitignore       # project-specific rules only; generic ones live at repo root
  src/             # all Python source
  tests/           # all tests, pytest
  data/            # inputs consumed by the build
  output/          # generated artifacts, committed
```

Rules that go with it:

- **Scripts live in `src/`** and resolve paths from the project root, never from
  their own directory:
  ```python
  ROOT = pathlib.Path(__file__).resolve().parent.parent
  DATA_DIR = ROOT / "data"
  OUT_DIR = ROOT / "output"
  ```
- **The primary artifact is `output/<project>.html`** — named after the directory
  it lives in, so it stays identifiable once downloaded or served. Secondary
  artifacts share the stem (`output/<project>.png`).
- **`output/` is committed.** These sites are meant to work straight from a
  clone. Rebuild and commit the output whenever you change a builder.
- **The site documents its own data sources.** Every generated page carries a
  "Data sources" section that names each upstream source and **links** it, so a
  reader who only has the HTML can see and follow the provenance — not just the
  README. Keep it in sync with the README's "Data sources" section. The
  scaffolder writes a placeholder version to fill in.
- **`data/` is committed** where it is small enough (curated JSON, geocode
  caches, fetched CSV). Large binary inputs — OSM extracts, GTFS feeds — are
  gitignored, with a `data/README.md` recording how to obtain them.
- **Tests import from `src/` via pytest config**, not `sys.path` hacks or a
  `conftest.py`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["src"]
  ```

## Site-listing metadata (`sites.json`)

Downstream consumers — chiefly [tianle91.github.io](https://github.com/tianle91/tianle91.github.io),
which vendors this repo as a submodule and lists every site — need each site's
**title** and **one-line blurb** in a structured form, so they can regenerate
their link list deterministically instead of scraping prose out of the READMEs.

Each project declares that in its `pyproject.toml`:

```toml
[project]
# Standalone one-liner. MUST start with "<title> — " so the blurb can be split
# out mechanically (see below).
description = "Toronto DineSafe food-safety inspections — one pin per establishment, coloured by its latest outcome, searchable by name / type / address."

[tool.staticsite]
title = "Toronto DineSafe food-safety inspections"   # the link text
```

[`generate_manifest.py`](generate_manifest.py) aggregates all of them into the
committed [`sites.json`](sites.json), one entry per project:

```json
{ "slug": "toronto-dinesafe-map",
  "title": "Toronto DineSafe food-safety inspections",
  "description": "one pin per establishment, coloured by its latest outcome, searchable by name / type / address.",
  "output": "toronto-dinesafe-map/output/toronto-dinesafe-map.html" }
```

`description` is `[project].description` with the leading `"<title> — "` removed,
so the title is stored once and the blurb is not duplicated. `output` is the
standard `<slug>/output/<slug>.html` artifact.

Regenerate and verify from the repo root:

```bash
make manifest    # rewrite sites.json  (== ./generate_manifest.py)
make check       # fail if sites.json is stale  (root make test runs this)
```

`sites.json` must not drift: root `make test` fails if it is out of date, so
**run `make manifest` and commit the result whenever you change a project's
`title`/`description` or add a project.** The generator is stdlib-only (it must
run on the system `python3`, which is 3.9 and predates `tomllib`), matching the
scaffolder.

## Scheduled data-refresh metadata

Every project also declares whether and how the optional local cadence selector
runs its networked `make data` target:

```toml
[tool.staticsite.refresh]
enabled = true
every_days = 7
anchor_date = "2026-08-03"
timeout_minutes = 45
```

The project is due on `anchor_date` and every `every_days` UTC dates after it.
Runtime "last run" state is intentionally not committed: deterministic dates
keep scheduling source-controlled without creating state-only commits. Local
command output records attempts and results.

[`refresh_projects.py`](refresh_projects.py) validates and selects this metadata.
It is stdlib-only because it runs before any project environment is installed.
`make check` validates both refresh metadata and `sites.json`.

New projects start with refresh disabled. Enable one only after its real fetch is
safe for unattended use and content-aware: when upstream records are unchanged,
`make data` must preserve committed data timestamps and produce byte-identical
output. `make refresh-due` runs all due projects sequentially. It does not commit, push,
or open PRs. Root `make data` explicitly refreshes every project regardless of
this metadata, including disabled projects.

## The standard Make target contract

Local CI and humans invoke these. Every project implements every target;
inapplicable ones are omitted only if genuinely meaningless.

Target names and contracts are consistent across projects. Each Python project's
Makefile configures and includes `../python-project.mk`, then supplies its own
artifact prerequisites and build recipes. Run targets
inside the project, or use `make -C <project> <target>` from the repo root.

| Target | Contract | Network |
| --- | --- | --- |
| `all` (default) | Rebuild everything in `output/` from committed `data/` | **No** |
| `system-deps` | Explicitly install this project's system tools (macOS/Homebrew) | **Yes** |
| `deps` | Install the complete locked environment when new or manifests change | Setup |
| `test` | `pytest` | **No** |
| `data` | Install dependencies as needed, obtain/refresh every required input, then `$(MAKE) all` | **Yes** |
| `open` | Open `output/<project>.html` in a browser | No |
| `clean` | Remove generated `output/` files | No |
| `clean-deps` | Remove the configured environment and stamp for a fresh install (`clean-venv` is an alias) | No |

These are requirements for every existing project and the scaffolder:

1. **Keep commands project-specific.** Reuse standard Python/uv recipes from
   `python-project.mk`; project Makefiles configure them and implement artifact
   build rules and extra targets. Root `make test` and `make data` are thin
   dispatchers as requested by the repository owner; they do not share project
   environments or duplicate project recipes. Do not add root dependency,
   system-installation or cleanup dispatchers.
2. **Install the whole project's Python dependencies.** `make deps` must cover
   fetching, building, and testing from the committed `pyproject.toml` and
   `uv.lock`, using `uv sync --locked`. Declare directly used third-party packages
   in that project's manifest. Do not require separate manual package installs
   for particular scripts.
3. **Prepare the whole project's data.** `make data` must ensure dependency setup,
   obtain or refresh every required upstream input, perform required preparation
   such as geocoding or clipping, and rebuild all project outputs. Curated inputs
   belong in committed `data/`; documented caller-managed overrides are validated
   rather than downloaded. A required-source failure must fail the target.
4. **Reuse dependencies without automatic repair.** Install when the environment
   stamp is missing or dependency manifests change. A current stamp means reuse:
   do not force synchronization, probe individual packages to reinstall them, or
   delete/recreate an existing environment to repair it. An incomplete environment
   must fail and direct the operator to explicit cleanup.
5. **Provide explicit dependency cleanup.** Every project must implement
   `make clean-deps` to remove only its configured environment and stamp (defaults
   `.venv` and `.venv/.stamp`). A custom stamp may live outside the environment;
   cleanup must remove that file too, preserving other files in its directory.
   `make clean-deps && make deps` performs a fresh install. Keep `clean-venv` as
   an alias. Dependency cleanup must preserve data, geocode caches, lockfiles,
   source files, and generated outputs; `make clean` handles generated outputs.
6. **Install system tools only through an explicit command.** Every project must
   configure `make system-deps` with its own required tools, independently of its
   Python environment. The supported installer is Homebrew on macOS: all projects
   need `uv`; transit also needs Java 21 and `osmium-tool`. Homebrew itself must
   already be installed. Fail clearly on unsupported platforms or missing
   Homebrew, and document manual prerequisites in the project's README.
   `deps`, `data`, `all`, and `test` must never invoke `system-deps` automatically.
   Credentials remain operator-supplied and must never be obtained automatically.

**Project build/test logic never touches the network.**
Dependency bootstrap may need the network when the environment is missing or
stale. Once dependencies are installed, `all` and `test` stay offline. Anything
that fetches from an API, geocodes, or downloads lives behind `data`, whose
outputs are committed. If you add a build step that needs the network, move the
fetch into `data` and commit its result instead of relaxing this.

## Dependencies

Configure the shared template before `include ../python-project.mk`. Defaults
cover `.venv`, `output/<project>.html`, `src/fetch_data.py`, `pytest -q`, and
Homebrew `uv`. Supported variables are `PROJECT`, `VENV`, `PY`, `STAMP`, `OUT`,
`OUTPUTS`, `OPEN_FILE`, `CLEAN_FILES`, `FETCH_SCRIPT`, `PYTEST_ARGS`,
`BREW_FORMULAE`, and `BREW_CASKS`. Use variables rather than overriding standard
target recipes. Keep file prerequisites and rendering recipes in each project.
The shared template sets `all` as the default goal and attaches order-only
dependency validation to every declared output. List every generated artifact
in `OUTPUTS`; transit also includes its routed grid in `CLEAN_FILES` to preserve
its curated-model fallback behavior. Do not add network fetching to build rules.

Each project has its own `pyproject.toml`, its own `uv.lock`, and its own
`./.venv`, all managed with [uv](https://docs.astral.sh/uv/):

```bash
cd <project>
make system-deps         # explicit macOS/Homebrew system-tool installation
make deps                # install the complete locked environment if needed
make clean-deps          # remove .venv; then make deps for a fresh install
uv add <package>         # runtime dependency
uv add --dev <package>   # test-only dependency
```

Makefiles invoke `$(PY)` = `.venv/bin/python`. **Never call `python3`, `pip`, or
`python -m venv` directly in a Makefile or script** — the system `python3` here
is 3.9, while every project targets ≥ 3.11.

Prefer a well-known package over hand-rolled logic, and say why the dependency
exists in a comment next to it. Current examples: `geopy` supplies the Nominatim
client, its rate limiter, and geodesic distance for both geocoding maps;
`shapely` unions the walk-circles into isochrone polygons. The reverse also
holds — the map HTML is hand-written Leaflet on purpose, because `folium` cannot
express the custom search/filter panels these maps have.

Python setup, build, test, and data targets use the same environment stamp:
install dependencies when pyproject/lock
changes or the stamp is missing. Repeated commands reuse the environment and do not
attempt repairs. Clear installed dependencies explicitly with `make clean-deps`,
then reinstall with `make deps`. Missing or stale locks fail; update them deliberately
with `uv lock` / `uv add` and commit them. Upgrades use `uv lock --upgrade`.

There is no root environment or shared dependency manifest.

`make data` succeeds only after all required sources were obtained and outputs
rebuilt. Validate before publishing; replace files atomically, preserve unchanged
bytes/timestamps, normalize unordered upstream records, and restore missing
sidecars. Preserve successful geocode caches; service errors must fail rather than
be cached as no-matches. Genuine no-match fallbacks remain project-specific.
System tools are installed separately via explicit `make system-deps` or manually
on other platforms. Credentials remain operator prerequisites.

## Verifying changes

```bash
cd <project> && make && make test
```

Root `make test` runs `make check`, then `make -C <project> test all` for every
project, continuing after independent failures. No hosted workflows remain.
`STATUSES=off` disables GitHub access. The default `STATUSES=auto` runs dirty
checkouts locally; clean, pushed commits receive `local-ci/<project>` and
`local-ci/metadata` statuses via the existing `gh` login. `STATUSES=required`
refuses uncommitted work. Pin the verified HEAD and recheck all tracked/untracked
changes before publishing success; never label a commit with tests of a dirty
checkout. Status-publication failures must be visible and return nonzero.
Full logs are ignored under `.local-ci/<sha>/` and are never uploaded.

Do **not** run `make data` as a routine check: it is slow and hits live APIs
(Nominatim allows 1 request/second, so one map takes ~5 minutes).
`union-station-transit-isochrone` additionally needs Java 21 and `osmium-tool`.
Root `make data` (alias `make refresh`) explicitly invokes every project's data
and output refresh, including projects with cadence selection disabled. It
continues after failures and returns nonzero if any project failed. It does not
commit, push, open PRs, or install system tools. Use `make refresh-due` for the
optional UTC cadence selector; there is no automatic scheduler.

## GitHub CLI access

The repository owner's `gh` authentication is available through the normal
terminal session and macOS keychain. A sandboxed `gh auth status` can incorrectly
report that the active token is invalid because it cannot use that session or
keychain. Before concluding that GitHub CLI authentication is broken, rerun the
check with normal terminal/keychain access (requesting approval when required).
Do not ask the repository owner to authenticate again based only on the
sandboxed result, and never print or copy the token itself.

## Conventions

- Match the surrounding style: these builders are heavily commented, explaining
  *why* a step exists (API quirks, geographic limits, rate limits). Keep that.
- Geocoding results and other slow fetches are cached in committed files (e.g.
  `data/geocode_cache.json`). Preserve them — regenerating means hours of
  rate-limited requests.
- Committed JSON (under `data/` and generated GeoJSON) and JSON payloads
  embedded in HTML are written with `indent=2` so diffs and source viewing stay
  readable. Do not minify them.
