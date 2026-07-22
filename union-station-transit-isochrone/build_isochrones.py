#!/usr/bin/env python3
"""Turn the curated transit reachability graph (transit_model.json) into nested
transit-isochrone polygons around Union Station and write them to
isochrones.geojson.

Method (the standard "buffer reachable stops" isochrone approximation):
  For a band of T minutes, every transit station reachable from Union in
  t <= T minutes contributes a walking circle of radius
      r = min(T - t, egress_cap) * walk_speed
  i.e. the area you can still walk to after getting off transit. The isochrone
  for T is the union of all those circles (plus Union's own walk circle). Bands
  are naturally nested (30 subset of 60 subset of 90 subset of 120).

Stdlib only - no pip install, no network. The union is computed on a fine
lat/lon raster and traced with marching squares, so there is no geometry
dependency. Resolution is controlled by GRID_DEG (smaller = smoother/slower).
"""
import json
import math
import pathlib

HERE = pathlib.Path(__file__).parent
MODEL = json.loads((HERE / "transit_model.json").read_text(encoding="utf-8"))
OUT = HERE / "isochrones.geojson"
REACH_PATH = HERE / "reachability.json"     # produced by `make data` (r5py); optional

PARAMS = MODEL["params"]
WALK = PARAMS["walk_speed_m_per_min"]       # metres per minute on foot
EGRESS_CAP = PARAMS["egress_cap_min"]       # cap on the final walk leg (minutes)
BANDS = MODEL["bands"]
NODES = MODEL["nodes"]

# If r5py produced a travel-time grid (reachability.json), contour that instead
# of the curated rapid-transit model: each reached grid point already includes
# the door-to-door walk, so it just needs a fixed radius (~grid cell) to merge
# neighbouring cells into a solid blob.
REACH = json.loads(REACH_PATH.read_text(encoding="utf-8")) if REACH_PATH.exists() else None
SOURCE = "r5py travel-time grid" if REACH else "curated rapid-transit model"

# Raster resolution in degrees. ~0.002 deg lat ~= 222 m; lon scaled by latitude.
# Smaller = smoother outlines but slower (raster cells scale ~1/GRID_DEG^2).
GRID_DEG = 0.002
PAD_DEG = 0.05  # margin around the reachable area so circles are not clipped


def metres_to_deg(metres, lat):
    """Return (dlat, dlon) degree offsets for a metric radius at a latitude."""
    dlat = metres / 111_320.0
    dlon = metres / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return dlat, dlon


def band_circles(minutes):
    """Circles (lat, lon, r_lat, r_lon) reachable within `minutes` of Union."""
    if REACH:
        return grid_circles(minutes)
    circles = []
    for n in NODES:
        if n["minutes"] > minutes:
            continue
        walk_min = min(minutes - n["minutes"], EGRESS_CAP)
        if walk_min <= 0 and n["minutes"] > 0:
            # Station reached exactly at the limit with no walk budget: a tiny
            # nub so it still registers on the map.
            walk_min = 0.5
        r_m = max(walk_min, 0.5) * WALK
        r_lat, r_lon = metres_to_deg(r_m, n["lat"])
        circles.append((n["lat"], n["lon"], r_lat, r_lon))
    return circles


def grid_circles(minutes):
    """Circles for each r5py grid point reached within `minutes`.

    The grid already encodes door-to-door transit+walk time, so every reached
    cell gets the same radius (0.75 x spacing) - just enough that neighbouring
    cells overlap into a solid area.
    """
    r_m = REACH["grid_spacing_m"] * 0.75
    circles = []
    for lat, lon, mins in REACH["points"]:
        if mins > minutes:
            continue
        r_lat, r_lon = metres_to_deg(r_m, lat)
        circles.append((lat, lon, r_lat, r_lon))
    return circles


def bbox(circles):
    lats_lo = [c[0] - c[2] for c in circles]
    lats_hi = [c[0] + c[2] for c in circles]
    lons_lo = [c[1] - c[3] for c in circles]
    lons_hi = [c[1] + c[3] for c in circles]
    return (min(lats_lo) - PAD_DEG, max(lats_hi) + PAD_DEG,
            min(lons_lo) - PAD_DEG, max(lons_hi) + PAD_DEG)


def trace_contours(mask, lat0, lon0, dlat, dlon):
    """Marching squares: emit closed rings around the True cells of `mask`.

    `mask[j][i]` is True when grid point (lat0 + j*dlat, lon0 + i*dlon) is
    covered. We walk the boundary edges between covered and uncovered cells and
    stitch them into closed rings (in [lon, lat] GeoJSON order).
    """
    rows = len(mask)
    cols = len(mask[0]) if rows else 0

    def inside(j, i):
        return 0 <= j < rows and 0 <= i < cols and mask[j][i]

    # Collect boundary segments as (p_start, p_end) on the half-integer grid.
    # Each covered cell contributes edges where its neighbour is outside.
    segs = {}
    for j in range(rows):
        for i in range(cols):
            if not mask[j][i]:
                continue
            # corners of this cell in grid coords (j,i) -> (j+1,i+1)
            tl = (j, i)
            tr = (j, i + 1)
            bl = (j + 1, i)
            br = (j + 1, i + 1)
            if not inside(j, i - 1):   # left edge
                segs.setdefault(bl, []).append(tl)
            if not inside(j, i + 1):   # right edge
                segs.setdefault(tr, []).append(br)
            if not inside(j - 1, i):   # top edge
                segs.setdefault(tl, []).append(tr)
            if not inside(j + 1, i):   # bottom edge
                segs.setdefault(br, []).append(bl)

    # Stitch directed segments into closed rings.
    rings = []
    while segs:
        start = next(iter(segs))
        ring = [start]
        cur = start
        while True:
            outs = segs.get(cur)
            if not outs:
                break
            nxt = outs.pop()
            if not outs:
                del segs[cur]
            ring.append(nxt)
            cur = nxt
            if cur == start:
                break
        if len(ring) >= 4:
            coords = [[lon0 + i * dlon, lat0 + j * dlat] for (j, i) in ring]
            rings.append(coords)
    return rings


def chaikin(ring, iterations=1):
    """Round a closed staircase ring with Chaikin corner-cutting (keeps it closed)."""
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring[:]
    for _ in range(iterations):
        if len(pts) < 3:
            break
        out = []
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            out.append([ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25])
            out.append([ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75])
        pts = out
    pts.append(pts[0])  # re-close
    return pts


def build_band(minutes):
    circles = band_circles(minutes)
    lat_lo, lat_hi, lon_lo, lon_hi = bbox(circles)
    dlat = GRID_DEG
    dlon = GRID_DEG  # square in degrees; lon circles already widened in metres_to_deg
    rows = int((lat_hi - lat_lo) / dlat) + 2
    cols = int((lon_hi - lon_lo) / dlon) + 2
    mask = [[False] * cols for _ in range(rows)]
    # Stamp each reachable circle onto the raster (only its own bbox of cells),
    # so cost scales with the circles, not cells x circles.
    for clat, clon, r_lat, r_lon in circles:
        j0 = max(0, int((clat - r_lat - lat_lo) / dlat))
        j1 = min(rows - 1, int((clat + r_lat - lat_lo) / dlat) + 1)
        i0 = max(0, int((clon - r_lon - lon_lo) / dlon))
        i1 = min(cols - 1, int((clon + r_lon - lon_lo) / dlon) + 1)
        for j in range(j0, j1 + 1):
            dy = (lat_lo + j * dlat - clat) / r_lat
            dy2 = dy * dy
            if dy2 > 1.0:
                continue
            row = mask[j]
            for i in range(i0, i1 + 1):
                dx = (lon_lo + i * dlon - clon) / r_lon
                if dx * dx + dy2 <= 1.0:
                    row[i] = True
    rings = trace_contours(mask, lat_lo, lon_lo, dlat, dlon)
    return [[[round(x, 5), round(y, 5)] for x, y in chaikin(r)] for r in rings]


def main():
    features = []
    # Largest band first so smaller (shorter-time) bands draw on top.
    for band in sorted(BANDS, key=lambda b: -b["minutes"]):
        rings = build_band(band["minutes"])
        # GeoJSON Polygon per ring (rings here are disjoint blobs/holes mixed;
        # MultiPolygon of single-ring polygons renders correctly for fill).
        polys = [[ring] for ring in rings]
        features.append({
            "type": "Feature",
            "properties": {
                "minutes": band["minutes"],
                "label": band["label"],
                "color": band["color"],
            },
            "geometry": {"type": "MultiPolygon", "coordinates": polys},
        })
    fc = {
        "type": "FeatureCollection",
        "properties": {
            "origin": MODEL["origin"],
            "service_assumption": MODEL["service_assumption"],
        },
        "features": features,
    }
    fc["properties"]["source"] = SOURCE
    OUT.write_text(json.dumps(fc), encoding="utf-8")
    counts = ", ".join(f'{f["properties"]["minutes"]}min:{len(f["geometry"]["coordinates"])} rings'
                       for f in features)
    print(f"Wrote {OUT} from {SOURCE} ({counts})")


if __name__ == "__main__":
    main()
