# StaticSites

A collection of self-contained static sites — interactive maps and plots that
build to a single file you can open in a browser with no server.

**Every top-level subdirectory is its own independent project**, with its own
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
row to the table at the top of this README. CI picks the project up automatically
— no workflow changes.

Do not hand-roll a new project directory; scaffolding it is what keeps the four
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
