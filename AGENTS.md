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
source package, and there is no repo-level virtualenv or dependency file, and no
shared build system. **Do not add one.** If two projects need the same helper,
duplicating it is the right call here. Scope a change to a single project and read
that project's own `README.md` first.

The only repo-level code is a small amount of repo-admin tooling, none of which a
project may depend on:

- [`new-project.py`](new-project.py) — the scaffolder (see below).
- [`generate_manifest.py`](generate_manifest.py) — regenerates
  [`sites.json`](sites.json) from the projects' metadata (see "Site-listing
  metadata" below).
- [`Makefile`](Makefile) — **admin targets only** (`make manifest`, `make
  check`). This is the one allowed repo-root Makefile; it is not a build system
  and must never gain build/test/deps targets — those stay per project. CI
  discovers projects with `*/Makefile` (one level deep), so this root Makefile is
  invisible to that glob and never becomes a phantom project.

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
make check       # fail if sites.json is stale  (CI runs this)
```

`sites.json` must not drift: CI fails the `manifest` job if it is out of date, so
**run `make manifest` and commit the result whenever you change a project's
`title`/`description` or add a project.** The generator is stdlib-only (it must
run on the system `python3`, which is 3.9 and predates `tomllib`), matching the
scaffolder.

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
