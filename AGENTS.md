# AGENTS.md

Guidance for coding agents working in this repo. Humans: see [README.md](README.md).

## Repo shape: one project per top-level subdirectory

This is a **multi-project repo, not a monorepo of one system**. Every top-level
subdirectory is a separate, self-contained static-site project:

- `margin-sp500-m2-visualization/`
- `ontario-physiotherapy-clinics-map/`
- `toronto-vulnerable-services-map/`
- `union-station-transit-isochrone/`

Projects are independent. No project imports from another, there is no shared
source package, and there is no repo-level virtualenv, `Makefile`, or dependency
file. **Do not add one.** If two projects need the same helper, duplicating it is
the right call here. Scope a change to a single project and read that project's
own `README.md` first.

The only repo-level code is [`new-project.py`](new-project.py), the scaffolder —
see below.

## Creating a project

**Always scaffold; never hand-roll the directory.**

```bash
./new-project.py my-new-map
```

That writes the full standard layout and a working end-to-end placeholder, so
`cd my-new-map && make && make test` passes immediately and CI picks it up with
no workflow changes. Then replace `src/fetch_data.py` (the real upstream fetch),
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

## The standard Make target contract

CI and humans only ever invoke these. Every project implements every target;
inapplicable ones are omitted only if genuinely meaningless.

| Target | Contract | Network |
| --- | --- | --- |
| `all` (default) | Rebuild everything in `output/` from committed `data/` | **No** |
| `deps` | `uv sync` into `./.venv` | First run only |
| `test` | `pytest` | **No** |
| `data` | Refresh `data/` from upstream, then rebuild `output/` | **Yes** |
| `open` | Open `output/<project>.html` in a browser | No |
| `clean` | Remove generated `output/` files | No |
| `clean-venv` | Remove `./.venv` | No |

**The rule CI depends on: `all` and `test` never touch the network.** Anything
that fetches from an API, geocodes, or downloads lives behind `data`, whose
outputs are committed. If you add a build step that needs the network, move the
fetch into `data` and commit its result instead of relaxing this.

## Dependencies

Each project has its own `pyproject.toml`, its own `uv.lock`, and its own
`./.venv`, all managed with [uv](https://docs.astral.sh/uv/):

```bash
cd <project>
uv sync                  # create/refresh .venv  (or just `make deps`)
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

## Verifying changes

```bash
cd <project> && make && make test
```

That is exactly what CI runs, once per project, via a matrix auto-discovered
from `*/Makefile` — see [.github/workflows/ci.yml](.github/workflows/ci.yml).
Adding a project that follows this standard needs no CI changes.

Do **not** run `make data` as a routine check: it is slow and hits live APIs
(Nominatim allows 1 request/second, so one map takes ~5 minutes).
`union-station-transit-isochrone`'s `make data` additionally needs a Java 21 JDK
and `osmium-tool`.

## Conventions

- Match the surrounding style: these builders are heavily commented, explaining
  *why* a step exists (API quirks, geographic limits, rate limits). Keep that.
- Geocoding results and other slow fetches are cached in committed files (e.g.
  `data/geocode_cache.json`). Preserve them — regenerating means hours of
  rate-limited requests.
