# StaticSites

A collection of self-contained static-site projects — interactive maps and plots
that build to a single file you can open in a browser with no server.

**Each project lives in its own top-level directory**, with its own
dependencies, its own virtualenv, its own tests, and its own committed output.
Projects never import from one another and there is nothing to install at the
repo root.

| Project | What it is |
| --- | --- |
| [fcf-macro-indicators/](fcf-macro-indicators/) | Quarterly free cash flow and cash balances of a basket of large public companies vs. M2, the S&P 500, and the 3M / 2Y / 10Y / 30Y Treasury curve, rebased to a chosen anchor quarter. Renders a static PNG and a zoomable HTML chart. |
| [margin-sp500-m2-visualization/](margin-sp500-m2-visualization/) | FINRA margin debt vs. S&P 500, M2, CPI, and PPI, rebased to a configurable anchor date. Renders a static PNG and a zoomable HTML chart. |
| [ontario-physiotherapy-clinics-map/](ontario-physiotherapy-clinics-map/) | The 255 publicly-funded (OHIP-covered) physiotherapy clinics and hospitals listed by the province, searchable by name / city / postal code. |
| [toronto-dinesafe-map/](toronto-dinesafe-map/) | Toronto's DineSafe food-safety inspection results, one pin per establishment coloured by its latest outcome (Pass / Conditional Pass / Closed), searchable by name / type / address. |
| [toronto-vulnerable-services-map/](toronto-vulnerable-services-map/) | Toronto/Ontario services for vulnerable populations: shelters, warming & respite centres, drop-ins, harm reduction, housing supports. |
| [union-station-transit-isochrone/](union-station-transit-isochrone/) | The morning commute-shed of Toronto's Union Station — where you can reach Union by transit in 30 / 60 / 90 / 120 min. |

## Usage

Each project works independently. You need
[uv](https://docs.astral.sh/uv/) installed; it creates the virtualenv for you on
first build.

```bash
cd <project>
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
its own sources, dependencies, and build steps. The root Makefile only provides
repository metadata commands (`manifest`, `check`, and `help`). Supply credentials
such as `SEC_USER_AGENT` through the environment; install `uv` and transit's
Java 21 / `osmium` prerequisites first.

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

| Target | What it does | Network |
| --- | --- | --- |
| `make` / `make all` | Rebuild `output/` from committed `data/` | **No** |
| `make deps` | Install the complete locked environment when new or manifests change | Setup |
| `make test` | Run the project's pytest suite | **No** |
| `make data` | Install dependencies as needed, refresh all required inputs, then rebuild | **Yes** |
| `make open` | Open `output/<project>.html` | No |
| `make clean` | Remove generated output | No |
| `make clean-deps` | Remove the project's `./.venv` for a fresh install (`clean-venv` is an alias) | No |

The command rules apply to every project and to newly scaffolded projects:

- Target names are consistent; each project owns its implementation. The root
  Makefile only provides `manifest`, `check`, and `help`.
- `make deps` installs all Python dependencies for fetching, building, and testing
  from the project's committed lockfile. Separate manual package installs are
  unnecessary.
- `make data` ensures dependency setup, obtains every required upstream input,
  prepares it, and rebuilds all outputs. Curated inputs remain committed; a
  required-source failure fails the command.
- Existing environments are reused without automatic repair. Use
  `make clean-deps && make deps` to reinstall explicitly. Cleanup removes only
  `.venv`, preserving data, caches, lockfiles, and outputs.
- System tools and credentials are documented prerequisites supplied by the
  operator.

The load-bearing rule is that **build and test logic stays offline** —
every source fetch, download, and geocode lives behind `make data`, and its results are
committed. That is what lets CI build and test all six projects hermetically,
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

On pull requests, CI runs `make test` and `make all` for each changed project on
self-hosted runners, using a matrix discovered automatically from `*/Makefile`.
Pushes to `main` run every project as a full-project safety net
([.github/workflows/ci.yml](.github/workflows/ci.yml)). A new project that
follows the standard needs no CI changes.

## Automated data refreshes

[`.github/workflows/refresh-data.yml`](.github/workflows/refresh-data.yml) wakes
daily at 06:17 UTC on the self-hosted runner. It reads each project's
`[tool.staticsite.refresh]` metadata, runs `make data`, `make test`, and `make
all` for projects due that day, and opens one PR containing all updates from
that invocation. If the substantive upstream data is unchanged, the fetchers
preserve the committed timestamps and outputs, and no PR is created.

Cadence is deterministic rather than stored as mutable "last run" metadata. A
project runs on `anchor_date`, then every `every_days` UTC dates:

```toml
[tool.staticsite.refresh]
enabled = true
every_days = 7
anchor_date = "2026-08-03"
timeout_minutes = 45
```

Validate or inspect the schedule locally without touching the network:

```bash
./refresh_projects.py check
./refresh_projects.py select --date 2026-08-03
```

The workflow also supports manual runs for due projects, every enabled project,
or one explicitly named project. The transit isochrone refresh is disabled
until its runner has the Java, `osmium`, and download/routing capacity documented
in that project.

### Self-hosted runner setup

Register a repository runner with the standard `self-hosted` label. It needs the
GitHub Actions runner's standard tools plus `make`; the workflows install `uv`.
Under **Settings → Actions → General**, enable **Allow GitHub Actions to create
and approve pull requests**. The refresh workflow grants its short-lived
`GITHUB_TOKEN` only the `contents: write` and `pull-requests: write` permissions
needed to push a refresh branch and open its pull request. Add `SEC_USER_AGENT`
as a repository Actions secret for the SEC-backed FCF refresh. Pull requests
opened with `GITHUB_TOKEN` require a maintainer to approve their CI run.

> **Security warning:** pull-request CI and the secret-bearing refresh workflow
> share this persistent machine. GitHub's `self-hosted` label routes jobs but
> does not isolate them. Malicious PR code could leave processes or files behind
> and capture secrets from a later refresh job. This setup assumes every PR is
> trusted. Before accepting untrusted contributions, use separate labelled
> runners—preferably an ephemeral runner for PR CI.

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
row to the table at the top of this README. Once its real fetch is content-aware,
enable and configure `[tool.staticsite.refresh]`. CI and the refresh scheduler
then pick the project up automatically—no workflow changes.

Do not hand-roll a new project directory; scaffolding it is what keeps the six
(and counting) projects identical in shape.

## Machine-readable index (`sites.json`)

Each project's title and one-line blurb are aggregated into
[`sites.json`](sites.json) — a structured index that downstream consumers (e.g.
[tianle91.github.io](https://github.com/tianle91/tianle91.github.io), which
vendors this repo as a submodule) read to regenerate their site list without
parsing prose. Regenerate it from the repo root whenever a project's metadata
changes:

```bash
make manifest    # rewrite sites.json from the projects' pyproject.toml
make check       # fail if sites.json is stale (CI enforces this)
```

See [AGENTS.md](AGENTS.md#site-listing-metadata-sitesjson) for the metadata
fields and conventions.
