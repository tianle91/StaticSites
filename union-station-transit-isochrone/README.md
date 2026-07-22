# Union Station Transit Isochrone Map

An interactive Leaflet map of the **morning commute-shed of Toronto's Union
Station**: where you can live and still **reach Union by public transit** in
**30 min, 1 h, 1.5 h and 2 h**, arriving during the weekday morning peak — subway,
streetcar, bus, GO rail and UP Express, plus the walk at each end. The result is a
self-contained `index.html` with toggleable layers, a legend, geolocation, and a
click-anywhere "which band is this in?" readout.

This is a **reverse isochrone** (travel time *to* Union, arriving by ~9 am), so it
respects peak-direction service. Routing direction is the one knob with real cost:
each map point is a separate r5py search, so the grid is coarse (~1 km) and builds
take a few minutes. Switch back to outbound or change resolution via the env vars
below.

## Quick start

The build computes real, full-network transit reach with
[r5py](https://r5py.readthedocs.io/) — multimodal RAPTOR routing over GTFS +
OpenStreetMap, including the street-network walk at each end. One-time setup,
then `make data`:

```bash
# 1. Install Java 21 (r5py needs it) and osmium (clips the OSM extract).
#    macOS + Homebrew — see "Installing Java 21" below for other platforms:
brew install --cask temurin@21
brew install osmium-tool

# 2. Download the OSM extract + GTFS feeds into ./data/
#    (copy-paste download commands are in data/README.md)

# 3. Build and open the map.
make data    # syncs ../.venv, clips OSM, routes, renders index.html
make open    # opens index.html in your default browser
```

`make data` uses the repo-level virtualenv at `../.venv`, which every target
creates on demand with `uv sync` (see the [repo README](../README.md)). It
auto-clips the OSM extract to the GTHA bbox (R5 caps the geographic
extent), then writes `reachability.json` (a grid→Union travel-time grid), contours
it into `isochrones.geojson`, and renders `index.html`. It routes for the next
non-holiday weekday (Wednesday).

The committed `index.html` is already built this way, so you can also just open
it directly — the internet is only needed for map tiles and the Leaflet library.

### Installing Java 21

r5py needs a **Java 21 JDK** on PATH. On macOS with Homebrew:

```bash
brew install --cask temurin@21   # prompts for your password to install the JDK
/usr/libexec/java_home -v 21     # verify: prints the JDK path
java -version                    # verify: shows 21.x
```

Temurin registers with macOS's `java_home`, so `java` is usually on PATH
automatically. If `java -version` still reports "Unable to locate a Java
Runtime", add to your `~/.zshrc` and re-open the shell:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
export PATH="$JAVA_HOME/bin:$PATH"
```

Not using Homebrew? Grab the Temurin 21 `.pkg` from
[adoptium.net](https://adoptium.net/temurin/releases/?version=21).

## What's on the map

* **Four time bands** (toggle on/off): ≤30 min, ≤1 h, ≤1.5 h, ≤2 h. Each band is
  the area from which you can *reach* Union within that time by transit + walking.
  They form the characteristic "octopus" shape — reach stretches along the subway
  and GO rail lines and pools around stations.
* **Station markers** (toggleable): every modelled subway / GO / UP station,
  colour-coded by mode. Click one for its line, routed time to Union, and the
  step-by-step trip (which line, where you board, departure time).
* **Click anywhere** → it tells you which time band the point falls in and shows
  the **suggested trip via the nearest station** — walk to the station, then the
  exact transit legs to Union. Great for "could I live here and still get to Union
  in under an hour, and how?"
* **Locate-me** → shows a "you are here" pin (automatically on load if the
  browser grants location, or via the ◎ button) and reports your own band.

## How the isochrones are built

`make data` routes a grid of points over the GTHA *to* Union with r5py (arriving
during the morning peak), where each trip already includes the door-to-door walk.
`build_isochrones.py` merges the points within each time `T` into a solid blob on
a fine lat/lon raster and traces the outline with marching squares (no geometry
dependency). Bands are nested by construction (30 ⊂ 60 ⊂ 90 ⊂ 120). It also runs
a second, heavier pass (`r5py.DetailedItineraries`) for the reachable stations to
record each one's step-by-step trip to Union, which the map shows on click.

### Why it's still an "isochrone"

An isochrone is any set of equal-travel-time contours anchored on a point. This map
measures time *to* Union rather than *from* it, which makes it a **reverse
isochrone** — also called a **catchment area** or **commute-shed**. The term still
fits: the bands are equal-travel-time contours, just inbound. The UI copy says
"commute-shed" because it reads more clearly; the code keeps `isochrone` in
filenames since both names describe the same thing.

### Travel-time model: best-timed vs typical

For each point, r5py samples a departure every minute across the window — the
`MAX_MINUTES` before arrival (07:00–09:00 by default, so even a 2-hour trip can
still arrive by 9) — and records each trip's travel time, a *distribution*, not one
number. `PERCENTILE` selects which point of it to report (lower = faster): `1` ≈
the best-timed trip, `50` the median. The choice only matters for infrequent
service (illustrative, sampled over an 8–9am window):

| station | p1 | p25 | p50 (median) |
|---|---|---|---|
| Richmond Hill GO (sparse peak rail) | **52** | 109 | unreachable |
| Downtown (frequent subway) | 24 | 27 | 27 |

Frequent subway is flat — whenever you leave, the trip is about the same, so the
percentile barely matters. Sparse peak-direction rail is a cliff: catch the one
useful inbound train and it's 52 min; miss it and you fall back to a ~109-min
bus+subway trip, and most departure-minutes can't make it at all (so the median
reads as *unreachable*).

The default `PERCENTILE=1` models a **planned commute** — you check the schedule and
leave to catch your train — which is the honest choice for an arrive-by-9am map; the
median would erase viable-but-infrequent GO lines. The trade-off: it assumes good
timing (Richmond Hill's 52 min is real, but only via that one train). Raise
`PERCENTILE` toward `50` for a conservative "turn up and go" reading.

### Tunables (env vars)

* `ARRIVE_HHMM` (default `09:00`) — arrival time at Union.
* `PERCENTILE` (default `1`) — travel-time percentile over the departure window;
  `1` ≈ the best-timed trip, `50` the median.
* `GRID_SPACING_M` (default `1000`) — grid resolution. **Reverse routing is one
  r5py search per point**, so finer grids are much slower (≈4× per halving).
* `MAX_MINUTES` (default `120`) — time budget *and* the departure-window length
  (window = `[ARRIVE_HHMM − MAX_MINUTES, ARRIVE_HHMM]`); `BBOX_S/N/W/E` — extent.

## Files

| File | Purpose |
|------|---------|
| `fetch_isochrones.py` | `make data`: real transit routing with r5py (OSM + GTFS) → `reachability.json` |
| `build_isochrones.py` | Stdlib-only: contours `reachability.json` into `isochrones.geojson` |
| `build_map.py` | Stdlib-only: renders `index.html` from the geojson + model |
| `transit_model.json` | Origin, bands, params + station list (used for markers and as the offline fallback) |
| `reachability.json` | r5py travel-time grid (each point → Union) + per-station step-by-step itineraries (generated by `make data`) |
| `isochrones.geojson` | Generated band polygons (committed so the map works without a build) |
| `index.html` | Generated map (committed) |
| `data/README.md` | Download commands for the OSM extract + GTFS feeds |
| `tests/` | pytest suite (dates/holidays, station snapping, itinerary parsing, builder smoke test) |
| `Makefile` | `make` builds the map from the committed model, `make data` re-routes it, `make osm` clips the OSM extract, `make open` opens it, `make clean` removes output |

## Tests

```bash
make test    # syncs ../.venv, then runs pytest
```

The suite is **stdlib + pytest only** — no r5py, Java, or GTFS needed — so it runs
fast and in CI. It covers the pure logic (Easter/holiday service-date selection,
station snapping, itinerary leg parsing) and a smoke test that runs the stdlib
builders end-to-end in a temp dir (falling back to the curated model). The r5py
routing itself isn't unit-tested (it needs Java + feeds); its helpers are.
[GitHub Actions](../.github/workflows/union-station-ci.yml) runs `pytest` on every push and PR.

## Caveats

* **Bands are for arriving at Union ~9 am on a weekday (morning peak).** Transit
  reach is highly time-dependent: **GO and UP run far less often off-peak** and
  several GO lines are peak-direction only, so the off-peak/return commute-shed is
  smaller. Tune with `ARRIVE_HHMM`.
* **Times assume a well-timed departure** (you leave home to catch the train) —
  the bands use the best trip in the window (`PERCENTILE=1`), not the median. See
  [Travel-time model](#travel-time-model-best-timed-vs-typical) for why, and raise
  `PERCENTILE` for a more conservative "turn up and go" reading.
* **The grid is coarse (~1 km) by default** because reverse routing runs one r5py
  search per point. Lower `GRID_SPACING_M` for sharper bands at the cost of a much
  longer build.
* **Use current GTFS feeds.** `make data` routes for the next non-holiday
  Wednesday, so each feed's `calendar` must cover that date or you'll get empty
  isochrones.
* Station-marker times are approximate all-day typicals (not the peak routed
  bands); coordinates are good to ~city scale.
