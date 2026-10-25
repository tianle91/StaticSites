#!/usr/bin/env python3
"""Download both published TRCA Open Data floodline layers, never the viewer.

The polygon catalogue explicitly requires the attributed line layer alongside it.
Fetch every object ID in bounded batches, then validate the complete response
before replacing the committed snapshot. Build and tests never use the network.
"""
import datetime
import json
import math
import pathlib
import tempfile
import time
import urllib.parse
import urllib.request

from shapely.geometry import shape, mapping

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_PATH = DATA_DIR / "floodplain.json"
BASE = "https://services1.arcgis.com/d0ZCwU7eGKVeNiEE/arcgis/rest/services"
LAYERS = {
    "polygons": (BASE + "/Floodline_TRCA_Polygon/FeatureServer/1", "OBJECTID,FloodPlainSource,Watershed"),
    "lines": (BASE + "/Floodline_TRCA_Line/FeatureServer/0", "OBJECTID,Layer,Watershed"),
}


def request_json(url, params):
    address = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            request = urllib.request.Request(address, headers={"User-Agent": "StaticSites-trca-flood-plain-map/1.0"})
            with urllib.request.urlopen(request, timeout=120) as stream:
                result = json.load(stream)
            if "error" in result:
                raise ValueError("TRCA query failed: " + str(result["error"]))
            return result
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def validate_collection(collection, kind):
    allowed = {"Polygon", "MultiPolygon"} if kind == "polygons" else {"LineString", "MultiLineString"}
    if collection.get("type") != "FeatureCollection" or not collection.get("features"):
        raise ValueError("Empty or invalid " + kind + " collection")
    def coordinates(value):
        if not isinstance(value, list) or not value:
            raise ValueError("Invalid geometry coordinates")
        if isinstance(value[0], (float, int)):
            if len(value) < 2 or not all(math.isfinite(x) for x in value[:2]):
                raise ValueError("Nonfinite coordinates")
            if not (-81 < value[0] < -78 and 43 < value[1] < 45):
                raise ValueError("Coordinates outside TRCA region")
        else:
            for child in value:
                coordinates(child)
    if not any(f.get("geometry") for f in collection["features"]):
        raise ValueError("No drawable geometries in " + kind)
    for feature in collection["features"]:
        # TRCA publishes some attributed records without drawable geometry.
        # Keep them in the snapshot; the page reports them separately.
        if feature.get("geometry") is None:
            continue
        geometry = feature["geometry"]
        if geometry.get("type") not in allowed:
            raise ValueError("Unexpected " + kind + " geometry")
        coordinates(geometry.get("coordinates"))
        if not feature.get("properties", {}).get("Watershed"):
            raise ValueError("Missing watershed")


def fetch_layer(url, fields, kind):
    ids = request_json(url + "/query", {"f": "json", "where": "1=1", "returnIdsOnly": "true"}).get("objectIds")
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Missing or duplicate source IDs")
    features = []
    for offset in range(0, len(ids), 100):
        batch = sorted(ids)[offset:offset + 100]
        result = request_json(url + "/query", {
            "f": "geojson", "objectIds": ",".join(map(str, batch)),
            "outFields": fields, "outSR": 4326, "returnGeometry": "true",
            "geometryPrecision": 6,
        })
        received = result.get("features", [])
        if result.get("exceededTransferLimit") or len(received) != len(batch):
            raise ValueError("Incomplete TRCA batch")
        features.extend(received)
    features.sort(key=lambda f: f["properties"]["OBJECTID"])
    if [f["properties"]["OBJECTID"] for f in features] != sorted(ids):
        raise ValueError("TRCA IDs do not match response")
    collection = {"type": "FeatureCollection", "features": features}
    validate_collection(collection, kind)
    # Generalize locally: server-side maxAllowableOffset can silently return
    # null GeoJSON geometries. Preserve topology and reject any lost feature.
    for feature in features:
        if feature.get("geometry") is None:
            continue
        geometry = shape(feature["geometry"])
        simplified = geometry.simplify(0.0001, preserve_topology=True)
        if simplified.is_empty:
            raise ValueError("Simplification lost a flood feature")
        # Convert tuples to lists and round new vertices to about 0.1 metres.
        feature["geometry"] = json.loads(json.dumps(mapping(simplified)))
    validate_collection(collection, kind)
    return collection


def write_snapshot(path, substantive):
    existing = json.loads(path.read_text()) if path.exists() else {}
    previous = {k: v for k, v in existing.items() if k != "retrieved_at"}
    if previous == substantive:
        return False
    payload = {"retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), **substantive}
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = pathlib.Path(stream.name)
        try:
            json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main():
    # Publish only after both required sources succeeded.
    data = {kind: fetch_layer(url, fields, kind) for kind, (url, fields) in LAYERS.items()}
    changed = write_snapshot(OUT_PATH, data)
    print("Flood plain snapshot " + ("updated." if changed else "unchanged."))


if __name__ == "__main__":
    main()
