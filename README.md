# StaticSites

A collection of self-contained static sites — interactive maps and plots that
build to a single file you can open in a browser with no server.

**Every top-level subdirectory is its own independent project.** Each one has its
own `README.md`, its own `Makefile`, its own data, and its own committed output.
Projects never import from one another. The only thing they share is the Python
environment described below.

| Project | What it is |
| --- | --- |
| [margin-sp500-m2-visualization/](margin-sp500-m2-visualization/) | FINRA margin debt vs. S&P 500, M2, CPI, and PPI, rebased to a configurable anchor date. Renders a static PNG and a zoomable HTML chart. |
| [ontario-physiotherapy-clinics-map/](ontario-physiotherapy-clinics-map/) | The 255 publicly-funded (OHIP-covered) physiotherapy clinics and hospitals listed by the province, searchable by name / city / postal code. |
| [toronto-vulnerable-services-map/](toronto-vulnerable-services-map/) | Toronto/Ontario services for vulnerable populations: shelters, warming & respite centres, drop-ins, harm reduction, housing supports. |
| [union-station-transit-isochrone/](union-station-transit-isochrone/) | The morning commute-shed of Toronto's Union Station — where you can reach Union by transit in 30 / 60 / 90 / 120 min. |

## Setup

One [uv](https://docs.astral.sh/uv/)-managed virtualenv at the repo root serves
every project. There are no per-project virtualenvs and no per-project
requirements files.

```bash
uv sync        # creates ./.venv from pyproject.toml + uv.lock
```

You rarely need to run that by hand: every `make` target syncs the environment
first, and `uv sync` is a no-op once the tree is warm.

## Usage

Build one project from its own directory:

```bash
cd <project> && make        # build the output
cd <project> && make open   # build and open in a browser (maps)
cd <project> && make test   # run that project's tests
```

Or fan out across all of them from the repo root:

```bash
make          # build every project
make test     # run every project's tests
make clean    # remove every project's generated output
```

## Dependencies

All Python dependencies for all projects live in a single root
[`pyproject.toml`](pyproject.toml), locked in `uv.lock`. Adding a dependency for
one project means adding it there:

```bash
uv add <package>            # runtime dependency
uv add --dev <package>      # test-only dependency
```

Most projects are stdlib-only and pull nothing from that list — they use the
shared environment purely to get a modern interpreter instead of whatever
`python3` happens to be. The heavy dependencies (r5py, geopandas, shapely) are
needed only by `union-station-transit-isochrone`'s optional `make data` step,
which additionally requires a Java 21 JDK and `osmium-tool`; see
[its README](union-station-transit-isochrone/README.md).

Shared Make settings — the path to the root virtualenv and the `uv sync` rule —
live in [`common.mk`](common.mk), which every project's `Makefile` includes.
