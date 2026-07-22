# `data/` — inputs for `make data` (r5py)

Drop the OpenStreetMap extract and the GTFS feeds here, then run `make data` from
the parent folder. These files are **gitignored** (they're large and change often)
— only this README is tracked.

`src/fetch_isochrones.py` looks for:
* `OSM_PBF` → `data/gtha.osm.pbf` by default (override with the `OSM_PBF` env var)
* `GTFS_DIR` → `data/` by default; it loads **every `*.zip`** in here

## 1. OpenStreetMap extract (the street + walk network)

Geofabrik's Ontario extract covers the whole GTHA:

```bash
cd data
curl -L -o gtha.osm.pbf https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf
```

It's ~900 MB and covers all of Ontario. **This must be clipped to the GTHA** —
R5 rejects geographic extents above ~975,000 km² (all of Ontario is far larger),
and the clip also makes r5py build faster and use less RAM.

`make data` does this for you: it runs `osmium extract` to produce
`gtha-clipped.osm.pbf` and routes from that — you just need [osmium](https://osmcode.org/osmium-tool/)
installed (`brew install osmium-tool`). To clip manually:

```bash
osmium extract -b -80.6,43.05,-78.7,44.40 gtha.osm.pbf -o gtha-clipped.osm.pbf
```

(That bbox matches `BBOX_*` in `src/fetch_isochrones.py` and `BBOX` in the Makefile:
west,south,east,north.)

## 2. GTFS feeds (the transit schedules)

Minimum for "TTC + GO/UP" reach from Union — download both into `data/`:

```bash
cd data
# TTC: subway + streetcar + bus (Toronto Open Data, ~6-weekly updates)
curl -L -o ttc.zip "http://opendata.toronto.ca/toronto.transit.commission/ttc-routes-and-schedules/OpenData_TTC_Schedules.zip"
# GO Transit + UP Express (Metrolinx Open Data)
curl -L -o go.zip "https://assets.metrolinx.com/raw/upload/Documents/Metrolinx/Open%20Data/GO-GTFS.zip"
```

* TTC dataset page (use this if the direct link 404s):
  <https://open.toronto.ca/dataset/merged-gtfs-ttc-routes-and-schedules/>
* GO/UP feed (download requires accepting Metrolinx's use agreement):
  <https://www.metrolinx.com/en/about-us/open-data> ·
  <https://www.gotransit.com/en/partner-with-us/software-developers>

Use **current** feeds: `src/fetch_isochrones.py` routes for the *next non-holiday Wednesday* (arriving Union ~09:00, morning peak), so
the GTFS `calendar` must cover that date or you'll get empty isochrones.

### Optional — 905 / regional agencies for fuller suburban reach

Add any of these as extra `*.zip` files in `data/` (each loads automatically):
MiWay (Mississauga), YRT/Viva (York), Brampton Transit, Durham Region Transit,
Oakville/Burlington Transit, Hamilton HSR. Most are on their city open-data
portals or mirrored on [Transitland](https://www.transit.land/) /
[Mobility Database](https://mobilitydatabase.org/).

## 3. Run it

First install the Java 21 JDK and osmium once (see the repo README for details):

```bash
brew install --cask temurin@21   # Java 21 JDK that r5py needs
brew install osmium-tool         # used to clip the OSM extract
```

Then:

```bash
cd ..
make data   # syncs .venv, clips OSM, routes Union -> grid, writes data/reachability.json
make open   # rebuild + open the map
```

Tunables (env vars): `ARRIVE_HHMM` (default `09:00`, arrival at Union),
`PERCENTILE` (`1`, best-timed trip; `50` for the median — see the repo README),
`GRID_SPACING_M` (`1000`; raise for speed, lower for detail — reverse routing is one
search per point, so lowering is much slower), `MAX_MINUTES` (`120`, also the
departure-window length before arrival), and `BBOX_S/N/W/E`.
