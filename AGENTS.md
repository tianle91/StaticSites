# AGENTS.md

Guidance for coding agents working in this repo.

## Repo shape: one project per top-level subdirectory

This is a **multi-project repo, not a monorepo of one system**. Every top-level
subdirectory is a separate, self-contained static-site project:

- `margin-sp500-m2-visualization/`
- `ontario-physiotherapy-clinics-map/`
- `toronto-vulnerable-services-map/`
- `union-station-transit-isochrone/`

What that means in practice:

- **Projects are independent.** No project imports from another, and there is no
  shared source package. Do not create one; if two projects need the same helper,
  duplicating it is the right call here.
- **Scope your work to one project.** A change requested for one project should
  not touch the others' files. Read that project's own `README.md` first — each
  documents its data sources, build steps, and caveats.
- **Each project owns its build.** Every project has a `Makefile` with `all`,
  `clean`, and usually `test`; maps also have `open`, and projects that fetch
  from the network have `data`.
- **Outputs are committed.** The generated `index.html` / PNG / HTML chart is
  checked in on purpose, so the sites work straight from a clone. Rebuild and
  commit the output when you change a builder.

The one thing shared across projects is the Python environment.

## The single shared Python environment

There is exactly one virtualenv (`./.venv`) and one dependency list
(`./pyproject.toml`, locked in `./uv.lock`), managed with
[uv](https://docs.astral.sh/uv/). Per-project virtualenvs and per-project
`requirements.txt` files were deliberately removed — **do not reintroduce them.**

```bash
uv sync                  # create/refresh ./.venv
uv add <package>         # add a runtime dependency (for any project)
uv add --dev <package>   # add a test-only dependency
```

`common.mk` at the repo root defines `$(PY)` (the shared interpreter) and the
`uv sync` rule. Every project's `Makefile` starts with `include ../common.mk` and
invokes `$(PY)` rather than a bare `python3`. When adding or editing a Makefile:

- Include `../common.mk` first; it sets `.DEFAULT_GOAL := all`, which is what
  keeps a bare `make` from resolving to the `venv` target defined in that file.
- Depend on the interpreter order-only — `target: deps... | $(PY)` — so an
  existing venv never forces a rebuild.
- Never call `python3`, `pip`, or `python -m venv` directly.

Note that the system `python3` on this machine is old (3.9). The shared env
targets Python ≥ 3.11, which is the reason even stdlib-only projects run through
`$(PY)`.

## Verifying changes

From the repo root:

```bash
make          # build every project
make test     # run every project's tests
```

Or per project: `cd <project> && make && make test`.

`make test` is hermetic — no network, no Java, no GTFS feeds — and is what CI
runs ([.github/workflows/ci.yml](.github/workflows/ci.yml)). The `make data`
targets do hit the network (open-data APIs, geocoding, transit routing) and are
slow; do not run them as a routine check. `union-station-transit-isochrone`'s
`make data` additionally needs a Java 21 JDK and `osmium-tool`.

## Conventions

- Match the surrounding style: these builders are heavily commented, explaining
  *why* a step exists (API quirks, geographic limits, rate limits), and the
  Makefiles carry that same commentary. Keep it.
- Prefer the standard library. Most projects are stdlib-only by design; reach for
  a dependency only when a project genuinely needs it.
- Geocoding results and other slow fetches are cached in committed JSON files
  (e.g. `geocode_cache.json`). Preserve them — regenerating means hours of
  rate-limited requests.
