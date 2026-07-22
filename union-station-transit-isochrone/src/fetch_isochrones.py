#!/usr/bin/env python3
"""Recommended `make data` step: compute travel times TO Union Station across the
full TTC + GO network with r5py (RAPTOR routing over GTFS + OpenStreetMap), then
write reachability.json for build_isochrones.py to contour.

This is a *reverse* isochrone - the morning commute-shed of Union: for each grid
point it routes that point -> Union arriving by ARRIVE_HHMM (weekday morning peak),
so the bands show where you can live and still reach Union by ~9am. Because each
grid point is a separate routing origin, use a coarse GRID_SPACING_M (reverse
routing is one r5py search per point, far slower than the one-to-many forward case).

Why r5py: unlike a hosted isochrone API, r5py does real multimodal public-transit
routing (subway + streetcar + bus + GO + UP) including the street-network walk at
each end, and it respects peak-direction service. The committed isochrones.geojson
keeps the map working without it.

Inputs (place in ./data/, or set env vars):
  OSM_PBF   - OpenStreetMap extract clipped to the GTHA, .osm.pbf (R5 caps the
              geographic extent; `make data` clips it for you). Default: data/gtha.osm.pbf
  GTFS_DIR  - folder of GTFS .zip feeds (TTC, GO/UP, and any 905 agencies).
              Default: ./data  (every *.zip in it is loaded)

Requirements: Java 21 (JDK), and `pip install r5py` (see dependencies/requirements.txt).
This step needs a few GB of RAM and is NOT run in restricted/offline sandboxes -
the committed isochrones.geojson keeps the map working without it.

Output: reachability.json
  { "origin": {...}, "direction": "to_union", "arrival": "...", "grid_spacing_m": N,
    "points": [[lat, lon, minutes], ...] }   # minutes = time to reach Union, <= MAX_MINUTES
"""
import datetime
import glob
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
MODEL = json.loads((DATA_DIR / "transit_model.json").read_text(encoding="utf-8"))
ORIGIN = MODEL["origin"]
OUT = DATA_DIR / "reachability.json"

# Tunables (env-overridable).
# This computes a *reverse* isochrone: travel time TO Union, arriving by ARRIVE_HHMM
# during the weekday morning peak. Every grid point is a routing origin (one r5py
# search each), so coarse spacing keeps the build to minutes, not hours.
MAX_MINUTES = int(os.environ.get("MAX_MINUTES", "120"))
GRID_SPACING_M = int(os.environ.get("GRID_SPACING_M", "1000"))  # finer = sharper, MUCH slower (reverse routes per point)
ARRIVE_HHMM = os.environ.get("ARRIVE_HHMM", "09:00")    # weekday morning-peak arrival at Union
# Departure window spans the MAX_MINUTES before arrival ([ARRIVE - MAX, ARRIVE]),
# so even a MAX_MINUTES-long trip can depart early enough to arrive by ARRIVE_HHMM
# (a shorter window would make the outer bands necessarily arrive *after* it).
WINDOW_MIN = MAX_MINUTES
# Travel-time percentile over the departure window. Use a low value (best-timed
# trip): a commuter leaves home to catch the train, so the median is wrong for
# infrequent peak-direction lines (e.g. Richmond Hill GO has one useful inbound
# train near 9am - the median over the window would call it unreachable).
PERCENTILE = int(os.environ.get("PERCENTILE", "1"))
# Bounding box of destinations: GTHA, Hamilton -> Oshawa -> ~Barrie.
BBOX = (
    float(os.environ.get("BBOX_S", "43.05")),   # south lat
    float(os.environ.get("BBOX_N", "44.40")),   # north lat
    float(os.environ.get("BBOX_W", "-80.60")),  # west lon
    float(os.environ.get("BBOX_E", "-78.70")),  # east lon
)
OSM_PBF = os.environ.get("OSM_PBF", str(DATA_DIR / "gtha.osm.pbf"))
GTFS_DIR = os.environ.get("GTFS_DIR", str(DATA_DIR))


def _easter(year):
    """Gregorian Easter Sunday (anonymous algorithm) - needed for Good Friday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)


def _nth_weekday(year, month, weekday, n):
    """The nth (1-based) given weekday (Mon=0) in a month."""
    first = datetime.date(year, month, 1)
    return first + datetime.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def ontario_holidays(year):
    """Statutory holidays observed by Ontario transit (no/holiday service)."""
    easter = _easter(year)
    may24 = datetime.date(year, 5, 24)
    return {
        datetime.date(year, 1, 1),                       # New Year's Day
        _nth_weekday(year, 2, 0, 3),                      # Family Day (3rd Mon Feb)
        easter - datetime.timedelta(days=2),             # Good Friday
        may24 - datetime.timedelta(days=may24.weekday()),  # Victoria Day (last Mon on/before May 24)
        datetime.date(year, 7, 1),                       # Canada Day
        _nth_weekday(year, 8, 0, 1),                      # Civic Holiday (1st Mon Aug)
        _nth_weekday(year, 9, 0, 1),                      # Labour Day (1st Mon Sep)
        _nth_weekday(year, 10, 0, 2),                     # Thanksgiving (2nd Mon Oct)
        datetime.date(year, 12, 25),                     # Christmas Day
        datetime.date(year, 12, 26),                     # Boxing Day
    }


def next_weekday():
    """Next Wednesday from today, skipping statutory holidays - a representative
    ordinary service day (peak-direction GO lines do not run on holidays)."""
    today = datetime.date.today()
    wed = today + datetime.timedelta(days=(2 - today.weekday()) % 7 or 7)
    while wed in ontario_holidays(wed.year):
        wed += datetime.timedelta(days=7)
    return wed


def load_stop_coords():
    """GTFS stop locations from the feeds in GTFS_DIR: a name->(lat, lon) index
    and a flat list of (lat, lon) for nearest-stop fallback."""
    import csv
    import io
    import zipfile
    by_name, coords = {}, []
    for zpath in sorted(glob.glob(os.path.join(GTFS_DIR, "*.zip"))):
        with zipfile.ZipFile(zpath) as z:
            if "stops.txt" not in z.namelist():
                continue
            text = z.read("stops.txt").decode("utf-8-sig")
            for row in csv.DictReader(io.StringIO(text)):
                try:
                    ll = (float(row["stop_lat"]), float(row["stop_lon"]))
                except (KeyError, ValueError):
                    continue
                coords.append(ll)
                by_name.setdefault(row.get("stop_name", "").strip().lower(), ll)
    return by_name, coords


def snap_to_stop(name, lat, lon, stops, max_m=700):
    """Snap a curated station to its GTFS stop so it actually boards there. Curated
    coords drift ~100-300 m - enough to miss an infrequent peak train across a
    rail/road barrier (e.g. Richmond Hill GO). Prefer an exact stop-name match
    (lands on the right rail platform); otherwise use the nearest stop within
    max_m; otherwise keep the curated coordinate."""
    import math
    by_name, coords = stops
    exact = by_name.get(name.strip().lower())
    if exact:
        return exact
    best, best_d = None, max_m
    for slat, slon in coords:
        dy = (slat - lat) * 111_320.0
        dx = (slon - lon) * 111_320.0 * math.cos(math.radians(lat))
        d = math.hypot(dx, dy)
        if d < best_d:
            best, best_d = (slat, slon), d
    return best if best else (lat, lon)


def build_stations():
    """Modelled stations within BBOX, snapped to their GTFS stop. id is "stn_<k>"."""
    s_lat, n_lat, w_lon, e_lon = BBOX
    stops = load_stop_coords()
    out = []
    for k, n in enumerate(MODEL["nodes"]):
        if s_lat <= n["lat"] <= n_lat and w_lon <= n["lon"] <= e_lon:
            slat, slon = snap_to_stop(n["name"], n["lat"], n["lon"], stops)
            out.append({"id": f"stn_{k}", "name": n["name"], "mode": n.get("mode"),
                        "lat": slat, "lon": slon})
    return out


def build_grid(geopandas, shapely, stations):
    """Regular point grid over BBOX at GRID_SPACING_M, plus every station as an
    extra origin. On a coarse grid no cell lands close enough to a station to use
    an infrequent peak train (e.g. Richmond Hill GO), so sampling the stations
    directly lets the contour bulge around them."""
    import math
    s_lat, n_lat, w_lon, e_lon = BBOX
    mid = math.radians((s_lat + n_lat) / 2)
    dlat = GRID_SPACING_M / 111_320.0
    dlon = GRID_SPACING_M / (111_320.0 * math.cos(mid))
    ids, pts = [], []
    j = 0
    lat = s_lat
    while lat <= n_lat:
        lon = w_lon
        i = 0
        while lon <= e_lon:
            ids.append(f"{j}_{i}")
            pts.append(shapely.Point(lon, lat))
            lon += dlon
            i += 1
        lat += dlat
        j += 1
    for st in stations:
        ids.append(st["id"])
        pts.append(shapely.Point(st["lon"], st["lat"]))
    return geopandas.GeoDataFrame({"id": ids, "geometry": pts}, crs="EPSG:4326")


def load_gtfs_lookups():
    """From the GTFS feeds: route_id -> (name, route_type) and stop_id -> name."""
    import csv
    import io
    import zipfile
    routes, stops = {}, {}
    for zpath in sorted(glob.glob(os.path.join(GTFS_DIR, "*.zip"))):
        with zipfile.ZipFile(zpath) as z:
            names = z.namelist()
            if "routes.txt" in names:
                for r in csv.DictReader(io.StringIO(z.read("routes.txt").decode("utf-8-sig"))):
                    name = (r.get("route_long_name") or r.get("route_short_name") or "").strip()
                    try:
                        rtype = int(r.get("route_type", "3"))
                    except ValueError:
                        rtype = 3
                    routes[r["route_id"]] = (name, rtype)
            if "stops.txt" in names:
                for s in csv.DictReader(io.StringIO(z.read("stops.txt").decode("utf-8-sig"))):
                    stops[s["stop_id"]] = (s.get("stop_name") or "").strip()
    return routes, stops


# GTFS route_type -> friendly mode label.
_MODE_LABEL = {0: "Streetcar", 1: "Subway", 2: "Rail", 3: "Bus", 5: "Streetcar", 11: "Bus"}


def itinerary_legs(rows, routes, stops):
    """Turn the fastest option of one origin's DetailedItineraries rows into a
    compact list of legs: walk minutes collapsed, transit legs with line + stops."""
    rows = sorted(rows, key=lambda r: (r["option"], r["segment"]))
    by_opt = {}
    for r in rows:
        by_opt.setdefault(r["option"], []).append(r)

    def total(segs):
        return sum((s["travel_time"].total_seconds() + s["wait_time"].total_seconds())
                   for s in segs)

    # Prefer the fastest option that actually uses transit (skip the all-walk one).
    transit_opts = [s for s in by_opt.values()
                    if any(str(x["mode"]).split(".")[-1] != "WALK" for x in s)]
    chosen = min(transit_opts or by_opt.values(), key=total)

    legs, walk = [], 0.0
    for s in chosen:
        mode = str(s["mode"]).split(".")[-1]
        if mode == "WALK" or s["route_id"] != s["route_id"]:  # walk / NaN route
            walk += s["travel_time"].total_seconds() / 60.0
            continue
        if walk >= 0.5:
            legs.append({"mode": "Walk", "min": round(walk)})
        walk = 0.0
        name, rtype = routes.get(s["route_id"], (s["route_id"], 3))
        dep = s["departure_time"]
        legs.append({
            "mode": _MODE_LABEL.get(rtype, "Transit"),
            "route": name,
            "from": stops.get(s["start_stop_id"], ""),
            "to": stops.get(s["end_stop_id"], ""),
            "dep": dep.strftime("%H:%M") if dep == dep and dep is not None else "",
            "min": round(s["travel_time"].total_seconds() / 60.0),
        })
    if walk >= 0.5:
        legs.append({"mode": "Walk", "min": round(walk)})
    return legs


def main():
    try:
        import geopandas
        import shapely
        from r5py import (TransportNetwork, TravelTimeMatrix, DetailedItineraries,
                          TransportMode)
    except ImportError as exc:
        print(f"r5py/geopandas not installed: {exc}\n"
              f"Run `pip install -r dependencies/requirements.txt` (needs Java 21).",
              file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(OSM_PBF):
        print(f"OSM extract not found at {OSM_PBF}. Download a GTHA .osm.pbf "
              f"(e.g. from Geofabrik) or set OSM_PBF.", file=sys.stderr)
        sys.exit(1)
    gtfs = sorted(glob.glob(os.path.join(GTFS_DIR, "*.zip")))
    if not gtfs:
        print(f"No GTFS .zip feeds in {GTFS_DIR}. Add TTC + GO feeds or set GTFS_DIR.",
              file=sys.stderr)
        sys.exit(1)

    date = next_weekday()
    hh, mm = (int(x) for x in ARRIVE_HHMM.split(":"))
    arrival = datetime.datetime(date.year, date.month, date.day, hh, mm)
    departure = arrival - datetime.timedelta(minutes=WINDOW_MIN)  # window ends at arrival
    print(f"OSM: {OSM_PBF}")
    print(f"GTFS: {', '.join(os.path.basename(g) for g in gtfs)}")
    print(f"Arrive Union by: {arrival}  |  depart window {WINDOW_MIN} min  |  "
          f"max {MAX_MINUTES} min  |  grid {GRID_SPACING_M} m")

    network = TransportNetwork(OSM_PBF, gtfs)
    union = geopandas.GeoDataFrame(
        {"id": ["union"], "geometry": [shapely.Point(ORIGIN["lon"], ORIGIN["lat"])]},
        crs="EPSG:4326")
    stations = build_stations()
    grid = build_grid(geopandas, shapely, stations)
    # Reverse isochrone: route every grid point -> Union (one search per origin).
    print(f"Routing {len(grid)} grid points -> Union (transit + walk)...")

    ttm = TravelTimeMatrix(
        network,
        origins=grid,
        destinations=union,
        departure=departure,
        departure_time_window=datetime.timedelta(minutes=WINDOW_MIN),  # peak departures before arrival
        transport_modes=[TransportMode.TRANSIT, TransportMode.WALK],
        max_time=datetime.timedelta(minutes=MAX_MINUTES),
        percentiles=[PERCENTILE],  # best-timed trip (see PERCENTILE above)
    )

    # ttm columns: from_id (grid), to_id (union), travel_time_p{PERCENTILE} in minutes
    # (NaN if unreachable). r5py only renames the column to "travel_time" for p50.
    tt_col = "travel_time" if PERCENTILE == 50 else f"travel_time_p{PERCENTILE}"
    grid_xy = {row.id: (row.geometry.y, row.geometry.x) for row in grid.itertuples()}
    points = []
    stn_time = {}
    for row in ttm.itertuples():
        t = getattr(row, tt_col, None)
        if t is None or t != t or t > MAX_MINUTES:   # None / NaN / over budget
            continue
        if str(row.from_id).startswith("stn_"):
            stn_time[row.from_id] = t
        lat, lon = grid_xy[row.from_id]
        points.append([round(lat, 5), round(lon, 5), int(round(t))])

    # Detailed step-by-step trips for the reachable stations only (one heavier
    # search each), so the map can show the method to Union for the nearest station.
    reachable = [s for s in stations if s["id"] in stn_time]
    stations_out = []
    if reachable:
        print(f"Computing detailed itineraries for {len(reachable)} stations...")
        routes, stops = load_gtfs_lookups()
        stn_gdf = geopandas.GeoDataFrame(
            {"id": [s["id"] for s in reachable],
             "geometry": [shapely.Point(s["lon"], s["lat"]) for s in reachable]},
            crs="EPSG:4326")
        di = DetailedItineraries(
            network, origins=stn_gdf, destinations=union, force_all_to_all=True,
            departure=departure,
            departure_time_window=datetime.timedelta(minutes=WINDOW_MIN),
            transport_modes=[TransportMode.TRANSIT, TransportMode.WALK],
        )
        rows_by_id = {}
        for r in di.itertuples():
            rows_by_id.setdefault(r.from_id, []).append({
                "option": r.option, "segment": r.segment, "mode": r.transport_mode,
                "route_id": r.route_id, "departure_time": r.departure_time,
                "travel_time": r.travel_time, "wait_time": r.wait_time,
                "start_stop_id": r.start_stop_id, "end_stop_id": r.end_stop_id,
            })
        for s in reachable:
            legs = itinerary_legs(rows_by_id.get(s["id"], []), routes, stops) \
                if s["id"] in rows_by_id else []
            stations_out.append({
                "name": s["name"], "mode": s["mode"],
                "lat": round(s["lat"], 5), "lon": round(s["lon"], 5),
                "minutes": int(round(stn_time[s["id"]])), "legs": legs,
            })

    OUT.write_text(json.dumps({
        "origin": ORIGIN,
        "direction": "to_union",
        "arrival": arrival.isoformat(),
        "departure_window_min": WINDOW_MIN,
        "percentile": PERCENTILE,
        "grid_spacing_m": GRID_SPACING_M,
        "engine": "r5py RAPTOR over OSM + GTFS (TTC + GO/UP)",
        "points": points,
        "stations": stations_out,
    }), encoding="utf-8")
    print(f"Wrote {OUT} with {len(points)} reachable grid points, "
          f"{len(stations_out)} station itineraries. Now run `make`.")


if __name__ == "__main__":
    main()
