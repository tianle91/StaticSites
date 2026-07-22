#!/usr/bin/env python3
"""Turn the curated transit reachability graph (data/transit_model.json) into
nested transit-isochrone polygons around Union Station and write them to
output/isochrones.geojson.

Method (the standard "buffer reachable stops" isochrone approximation):
  For a band of T minutes, every transit station reachable from Union in
  t <= T minutes contributes a walking circle of radius
      r = min(T - t, egress_cap) * walk_speed
  i.e. the area you can still walk to after getting off transit. The isochrone
  for T is the union of all those circles (plus Union's own walk circle). Bands
  are naturally nested (30 subset of 60 subset of 90 subset of 120).

The union and smoothing are done with shapely; no network access is needed.
"""
import json
import math
import pathlib

from shapely.geometry import Point, mapping
from shapely.ops import unary_union

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"

MODEL = json.loads((DATA_DIR / "transit_model.json").read_text(encoding="utf-8"))
OUT = OUT_DIR / "isochrones.geojson"
REACH_PATH = DATA_DIR / "reachability.json"   # produced by `make data` (r5py); optional

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

# Circles are built in degrees, where a metric radius is an ellipse: one degree
# of longitude shrinks with latitude while one degree of latitude does not. So
# buffer in a longitude-stretched space and squash back afterwards, which keeps
# circles round on the ground across an extent this size (~1.5 deg of latitude).
LAT_REF = MODEL["origin"]["lat"]
LON_SCALE = max(0.2, math.cos(math.radians(LAT_REF)))
DEG_PER_M = 1 / 111_320.0

# Simplification tolerance in degrees (~20 m). Smooths the seams left by unioning
# hundreds of circles without visibly moving the outline, and keeps the committed
# GeoJSON small.
SIMPLIFY_DEG = 0.0002


def band_circles(minutes):
    """(lon, lat, radius_m) for everything reachable within `minutes` of Union."""
    if REACH:
        # The grid already encodes door-to-door transit+walk time, so every
        # reached cell gets the same radius (0.75 x spacing) - just enough that
        # neighbouring cells overlap into a solid area.
        r_m = REACH["grid_spacing_m"] * 0.75
        return [(lon, lat, r_m) for lat, lon, mins in REACH["points"] if mins <= minutes]

    circles = []
    for n in NODES:
        if n["minutes"] > minutes:
            continue
        walk_min = min(minutes - n["minutes"], EGRESS_CAP)
        if walk_min <= 0 and n["minutes"] > 0:
            # Station reached exactly at the limit with no walk budget: a tiny
            # nub so it still registers on the map.
            walk_min = 0.5
        circles.append((n["lon"], n["lat"], max(walk_min, 0.5) * WALK))
    return circles


def build_band(minutes):
    """Union the reachable walk-circles for `minutes` into GeoJSON coordinates."""
    blobs = [
        Point(lon * LON_SCALE, lat).buffer(r_m * DEG_PER_M, quad_segs=16)
        for lon, lat, r_m in band_circles(minutes)
    ]
    merged = unary_union(blobs).simplify(SIMPLIFY_DEG)

    def unstretch(ring):
        return [[round(x / LON_SCALE, 5), round(y, 5)] for x, y in ring]

    geom = mapping(merged)
    # Normalise to MultiPolygon coordinates: a list of polygons, each a list of
    # rings (exterior first, then any holes).
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else list(geom["coordinates"])
    return [[unstretch(ring) for ring in poly] for poly in polys]


def main():
    features = []
    # Largest band first so smaller (shorter-time) bands draw on top.
    for band in sorted(BANDS, key=lambda b: -b["minutes"]):
        features.append({
            "type": "Feature",
            "properties": {
                "minutes": band["minutes"],
                "label": band["label"],
                "color": band["color"],
            },
            "geometry": {"type": "MultiPolygon", "coordinates": build_band(band["minutes"])},
        })
    fc = {
        "type": "FeatureCollection",
        "properties": {
            "origin": MODEL["origin"],
            "service_assumption": MODEL["service_assumption"],
            "source": SOURCE,
        },
        "features": features,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fc), encoding="utf-8")
    counts = ", ".join(f'{f["properties"]["minutes"]}min:{len(f["geometry"]["coordinates"])} polygons'
                       for f in features)
    print(f"Wrote {OUT} from {SOURCE} ({counts})")


if __name__ == "__main__":
    main()
