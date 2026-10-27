# StaticSites

A collection of self-contained static-site projects — interactive maps and plots
that build to a single file you can open in a browser with no server.

**Each project lives in its own top-level directory**, with its own
dependencies, its own virtualenv, its own tests, and its own committed output.
Projects never import from one another and there is nothing to install at the
repo root. Their Makefiles include the shared [Python/uv template](python-project.mk),
so build them within the repository checkout.

| Project | What it is |
| --- | --- |
| [fcf-macro-indicators/](fcf-macro-indicators/) | Quarterly free cash flow and cash balances of a basket of large public companies vs. M2, the S&P 500, and the 3M / 2Y / 10Y / 30Y Treasury curve, rebased to a chosen anchor quarter. Renders a static PNG and a zoomable HTML chart. |
| [margin-sp500-m2-visualization/](margin-sp500-m2-visualization/) | FINRA margin debt vs. S&P 500, M2, CPI, and PPI, rebased to a configurable anchor date. Renders a static PNG and a zoomable HTML chart. |
| [ontario-physiotherapy-clinics-map/](ontario-physiotherapy-clinics-map/) | The 255 publicly-funded (OHIP-covered) physiotherapy clinics and hospitals listed by the province, searchable by name / city / postal code. |
| [toronto-building-permits-map/](toronto-building-permits-map/) | Toronto’s complete active building permit register, searchable by address / number / description with status, type and application-year filters. |
| [toronto-crime-map/](toronto-crime-map/) | Toronto Police reported crimes from 2025 onward, with approximate locations, offence/date/neighbourhood filters, and separate homicide and shooting layers. |
| [toronto-dinesafe-map/](toronto-dinesafe-map/) | Toronto's DineSafe food-safety inspection results, one pin per establishment coloured by its latest outcome (Pass / Conditional Pass / Closed), searchable by name / type / address. |
| [toronto-vulnerable-services-map/](toronto-vulnerable-services-map/) | Toronto/Ontario services for vulnerable populations: shelters, warming & respite centres, drop-ins, harm reduction, housing supports. |
| [trca-flood-plain-map/](trca-flood-plain-map/) | TRCA riverine flood plain polygons and attributed floodline boundaries, filterable by watershed and source. |
| [union-station-transit-isochrone/](union-station-transit-isochrone/) | The morning commute-shed of Toronto's Union Station — where you can reach Union by transit in 30 / 60 / 90 / 120 min. |

## Usage

Each project works independently. You need
[uv](https://docs.astral.sh/uv/) installed; it creates the virtualenv for you on
first build.

```bash
cd <project>
make system-deps # install system tools on macOS (requires Homebrew)
make          # build output/<project>.html from the committed data/
make open     # build, then open it in a browser
make test     # run this project's tests
make deps     # install this project's dependencies from its committed lockfile
make clean-deps # remove this project's environment for a fresh install
make data     # refresh every required input and rebuild
```

You can also select a project from the repo root with `make -C`:

```bash
make -C <project> deps     # install this project's isolated .venv
make -C <project> data     # refresh this project's inputs and rebuild its output
```

Target names are consistent across projects; each project's Makefile defines
its own sources, dependencies, and build steps. The root Makefile delegates `test` and `data` to all projects and
provides repository metadata commands (`manifest`, `check`, and `help`). Supply credentials
such as `SEC_USER_AGENT` through the environment. `make system-deps` installs
`uv` and transit's Java 21 / `osmium` prerequisites on macOS with Homebrew;
other platforms require manual installation.

Or just open the committed `output/<project>.html` directly — the sites work
straight from a clone.

## Project standard

Every project follows the same layout and the same `make` targets, so any
project is navigable once you have seen one, and CI stays generic. The full
specification — including the rules for agents working in this repo — is in
[AGENTS.md](AGENTS.md); the short version:

```
<project>/
  README.md        # what it is, data sources, caveats
  Makefile         # the standard targets below
  pyproject.toml   # dependencies + pytest config
  uv.lock          # committed
  src/             # all Python source
  tests/           # all tests, pytest
  data/            # inputs consumed by the build (committed where small)
  output/          # generated artifacts, committed
```

Python projects include [`python-project.mk`](python-project.mk) after setting
their configuration variables, then define their own artifact build rules:

```make
PROJECT := example-map
OUTPUTS := output/$(PROJECT).html

include ../python-project.mk

$(OUT): src/build_map.py data/locations.json
	$(PY) src/build_map.py
```

The template supplies dependency setup/validation, pytest, data refresh followed
by a rebuild, opening output, cleanup, and explicit Homebrew installation.
Projects configure these through variables before the include:

| Variables | Default / purpose |
| --- | --- |
| `PROJECT`, `OUT`, `OUTPUTS` | Project directory name; primary HTML; all generated artifacts |
| `VENV`, `PY`, `STAMP` | `.venv`, its Python executable, and dependency stamp |
| `FETCH_SCRIPT`, `PYTEST_ARGS` | `src/fetch_data.py`, `-q` |
| `OPEN_FILE`, `CLEAN_FILES` | Primary HTML to open; declared outputs to clean |
| `BREW_FORMULAE`, `BREW_CASKS` | `uv`; no casks by default |

Rendering recipes and their source/data prerequisites stay in project Makefiles.
Charts declare their additional PNG output; transit declares its GeoJSON,
Java/osmium packages, extra cleanup, and OSM clipping target. Each project keeps
its own Python dependencies and environment. Copying a project out of this repo
also requires the shared `.mk` file at the expected parent path.

| Target | What it does | Network |
| --- | --- | --- |
| `make` / `make all` | Rebuild `output/` from committed `data/` | **No** |
| `make system-deps` | Explicitly install project system tools (macOS/Homebrew) | **Yes** |
| `make deps` | Install the complete locked environment when new or manifests change | Setup |
| `make test` | Run the project's pytest suite | **No** |
| `make data` | Install dependencies as needed, refresh all required inputs, then rebuild | **Yes** |
| `make open` | Open `output/<project>.html` | No |
| `make clean` | Remove generated output | No |
| `make clean-deps` | Remove the configured environment and stamp for a fresh install (`clean-venv` is an alias) | No |

The command rules apply to every project and to newly scaffolded projects:

- Target names and common Python/uv recipes come from `python-project.mk`;
  project Makefiles declare their own configuration, inputs, and build recipes.
  The root Makefile delegates `test` and `data` without owning project build rules.
- `make deps` installs all Python dependencies for fetching, building, and testing
  from the project's committed lockfile. Separate manual package installs are
  unnecessary.
- `make data` ensures dependency setup, obtains every required upstream input,
  prepares it, and rebuilds all outputs. Curated inputs remain committed; a
  required-source failure fails the command.
- Existing environments are reused without automatic repair. Use
  `make clean-deps && make deps` to reinstall explicitly. Cleanup removes only
  the configured environment and stamp (normally `.venv` and `.venv/.stamp`),
  preserving data, caches, lockfiles, and outputs.
- System tools have their own explicit `make system-deps` command; other targets
  never invoke it. Homebrew is required on macOS; other platforms require manual
  installation. Credentials remain operator-supplied prerequisites.

The load-bearing rule is that **build and test logic stays offline** —
every source fetch, download, and geocode lives behind `make data`, and its results are
committed. That is what lets CI build and test all projects hermetically,
and what lets you rebuild any site offline after dependency setup. Dependency
bootstrap can need the network for a new environment or changed manifests.
All targets reuse an installed environment until the dependency manifests change.
To reinstall it, run `make clean-deps && make deps` inside the project.
Missing or stale locks fail instead of being rewritten.
Use `uv add` / `uv lock` deliberately; use `uv lock --upgrade` for upgrades.

A successful `make data` refreshes all required sources and rebuilds outputs.
Unchanged content preserves data timestamps and bytes; missing generated files
are restored. Required-source failures retain previous datasets and return an
error instead of publishing a partial refresh.

## Local checks and GitHub statuses

GitHub Actions workflows have been removed. Run the complete checks locally:

```bash
make test                      # metadata checks + every project's test and all
make test STATUSES=off         # no GitHub access (dependency setup may need network)
make test STATUSES=required    # require a clean, committed, pushed HEAD and status publication
```

Projects are discovered from one-level-deep `*/Makefile` files. The root target
runs `make check`, then `make -C <project> test all` for every project in sorted
order, continuing to the next project after a failure and exiting nonzero if any
check fails. Build and test commands remain project-local and offline once their
locked environments are installed. Existing incomplete environments fail with
instructions for explicit `make clean-deps && make deps`; they are not repaired.
For verification in a separate environment while preserving an existing one,
use `make test CI_VENV=.venv/ci-verification`. This configures a distinct locked
environment inside each project; it does not change the normal `.venv` setup.

`STATUSES=auto` is the default: uncommitted work is checked locally without
attaching results to an older commit. For a clean checkout, the runner uses your
existing [GitHub CLI](https://cli.github.com/) login to publish `pending` then
`success`, `failure`, or `error` commit statuses under `local-ci/<project>`, plus
`local-ci/metadata`. Commit and push first. It pins the SHA for the whole run and
rechecks HEAD and the complete working tree before reporting success. Generated
output changes require committing the output and rerunning. Status/API errors
return a nonzero exit code while local checks still run. No commits, pushes,
pull requests, or credentials are created by `make test`.

Full transcripts stay in ignored `.local-ci/<commit>/<project>.log` files; GitHub
receives only a short result. To require these statuses for merging, select the
`local-ci/...` contexts in your repository's branch protection after their first
successful publication. Old GitHub Actions required checks must be removed from
that configuration separately.

## Refreshing data and outputs locally

```bash
make data                      # refresh data and outputs for every project
make refresh                   # alias for make data
make -C toronto-dinesafe-map data  # refresh just one project
```

Before a full refresh, provide the SEC identification required by the FCF
project, using your own name/organization and contact email:

```bash
export SEC_USER_AGENT='Your Name contact@example.com'
make data
make test
```

With system tools installed and credentials supplied, these Make commands handle
fetching, preparation, and rendering. Toronto permit downloads retry interrupted
transfers; DineSafe automatically falls back from failed pagination to the
official bulk CSV. Both validate exact source counts before publishing data.
Persistent upstream failures still return an error and preserve the last snapshot.

If an existing environment is damaged, explicitly run
`make -C <project> clean-deps` followed by `make -C <project> deps` before retrying.
To preserve it and use a separate environment instead, the matching commands are
`make data VENV=.venv/ci-verification` and
`make test CI_VENV=.venv/ci-verification`; each project still has its own environment.

Root `make data` invokes each project's existing `make data` sequentially. Each
project fetches all its required inputs and rebuilds its output; failures are
reported and the other independent projects still get an attempt. This is an
explicit network operation, including the transit project's large OSM/GTFS
inputs, Java 21 / `osmium` prerequisites, and any required operator credentials
such as `SEC_USER_AGENT`. It does not install system tools, publish statuses,
commit changes, push, or open PRs. Review generated changes, commit them, then
run `make test` to publish checks for that commit.

Data refreshes run only when root `make data` / `make refresh` or a project's
`make data` is invoked. Outputs are rebuilt by those commands and by explicit
build commands (`make` / `make all` inside a project, including the build step in
root `make test`). There is no configured update frequency or automatic refresh.

## Adding a project

Use the scaffolder — it is the recommended way to start a project, and it writes
the layout and target contract above for you:

```bash
./new-project.py my-new-map
cd my-new-map && make && make test    # both pass immediately
```

The generated project is a working end-to-end placeholder: `src/fetch_data.py`
writes `data/`, `src/build_site.py` renders `output/my-new-map.html` from it, and
a smoke test covers the build. Replace those three with the real thing, fill in
the `TODO`s in the project's `README.md`, set the homepage blurb in
`pyproject.toml` (`[project].description` + `[tool.staticsite].title`), and add a
row to the table at the top of this README. Make its real fetch content-aware
so unchanged upstream data preserves committed bytes and timestamps. Root
`make test` and `make data` discover the project automatically.

Do not hand-roll a new project directory; scaffolding keeps the projects
identical in shape.

## Machine-readable index (`sites.json`)

Each project's title and one-line blurb are aggregated into
[`sites.json`](sites.json) — a structured index that downstream consumers (e.g.
[tianle91.github.io](https://github.com/tianle91/tianle91.github.io), which
vendors this repo as a submodule) read to regenerate their site list without
parsing prose. Regenerate it from the repo root whenever a project's metadata
changes:

```bash
make manifest    # rewrite sites.json from the projects' pyproject.toml
make check       # fail if sites.json is stale (also included in root make test)
```

See [AGENTS.md](AGENTS.md#site-listing-metadata-sitesjson) for the metadata
fields and conventions.
