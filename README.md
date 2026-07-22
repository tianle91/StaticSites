# StaticSites

A collection of self-contained static sites — interactive maps and plots that
build to a single file you can open in a browser with no server.

**Every top-level subdirectory is its own independent project**, with its own
dependencies, its own virtualenv, its own tests, and its own committed output.
Projects never import from one another and there is nothing to install at the
repo root.

| Project | What it is |
| --- | --- |
| [margin-sp500-m2-visualization/](margin-sp500-m2-visualization/) | FINRA margin debt vs. S&P 500, M2, CPI, and PPI, rebased to a configurable anchor date. Renders a static PNG and a zoomable HTML chart. |
| [ontario-physiotherapy-clinics-map/](ontario-physiotherapy-clinics-map/) | The 255 publicly-funded (OHIP-covered) physiotherapy clinics and hospitals listed by the province, searchable by name / city / postal code. |
| [toronto-vulnerable-services-map/](toronto-vulnerable-services-map/) | Toronto/Ontario services for vulnerable populations: shelters, warming & respite centres, drop-ins, harm reduction, housing supports. |
| [union-station-transit-isochrone/](union-station-transit-isochrone/) | The morning commute-shed of Toronto's Union Station — where you can reach Union by transit in 30 / 60 / 90 / 120 min. |

## Usage

Everything happens inside a project directory. You need
[uv](https://docs.astral.sh/uv/) installed; it creates the virtualenv for you on
first build.

```bash
cd <project>
make          # build output/<project>.html from the committed data/
make open     # build, then open it in a browser
make test     # run this project's tests
```

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
| `make deps` | `uv sync` into the project's `./.venv` | First run only |
| `make test` | Run the project's pytest suite | **No** |
| `make data` | Refresh `data/` from upstream APIs, then rebuild | **Yes** |
| `make open` | Open `output/<project>.html` | No |
| `make clean` | Remove generated output | No |
| `make clean-venv` | Remove the project's `./.venv` | No |

The load-bearing rule is that **`all` and `test` never touch the network** —
every fetch, download, and geocode lives behind `make data`, and its results are
committed. That is what lets CI build and test all four projects hermetically,
and what lets you rebuild any site offline.

CI runs `make test` and `make all` once per project, in a matrix discovered
automatically from `*/Makefile`
([.github/workflows/ci.yml](.github/workflows/ci.yml)). A new project that
follows the standard needs no CI changes.

## Adding a project

1. Create `<project>/` with the layout above.
2. `cd <project> && uv init --bare && uv add <deps>` — then add the pytest config
   block from [AGENTS.md](AGENTS.md) to `pyproject.toml`.
3. Copy a `Makefile` from a sibling project and adjust the inputs and outputs.
4. Add a row to the table at the top of this README.
