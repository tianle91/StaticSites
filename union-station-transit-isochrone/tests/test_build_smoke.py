"""Smoke test the offline builders end-to-end in isolation (no r5py/Java/GTFS).

Rebuilds a minimal copy of the project layout (src/ + data/ + output/) in a temp
dir and runs the builders there, so it neither needs the routing stack nor
clobbers committed outputs. Without data/reachability.json, build_isochrones.py
falls back to the curated transit model.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def built(tmp_path):
    """Run both builders in a temp project tree; return its output/ directory."""
    for sub in ("src", "data", "output"):
        (tmp_path / sub).mkdir()
    shutil.copytree(ROOT / "src", tmp_path / "src", dirs_exist_ok=True)
    shutil.copy(ROOT / "data" / "transit_model.json", tmp_path / "data" / "transit_model.json")
    for script in ("build_isochrones.py", "build_map.py"):
        subprocess.run([sys.executable, f"src/{script}"], cwd=tmp_path, check=True)
    return tmp_path / "output"


def test_isochrones_geojson_is_valid(built):
    geo = json.loads((built / "isochrones.geojson").read_text())
    assert geo["type"] == "FeatureCollection"
    assert geo["features"], "no band polygons produced"
    minutes = {f["properties"]["minutes"] for f in geo["features"]}
    assert minutes <= {30, 60, 90, 120}
    for f in geo["features"]:
        assert f["geometry"]["type"] == "MultiPolygon"
        assert f["geometry"]["coordinates"], "band has no polygons"


def test_bands_are_nested(built):
    """A longer time budget must cover at least as much ground as a shorter one."""
    geo = json.loads((built / "isochrones.geojson").read_text())
    areas = {}
    for f in geo["features"]:
        rings = [ring for poly in f["geometry"]["coordinates"] for ring in poly]
        # Shoelace over exterior rings is a fine proxy at this scale.
        areas[f["properties"]["minutes"]] = sum(
            abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(r, r[1:]))) / 2 for r in rings
        )
    ordered = [areas[m] for m in sorted(areas)]
    assert ordered == sorted(ordered), f"bands not nested by area: {areas}"


def test_map_html_rendered(built):
    html = (built / "union-station-transit-isochrone.html").read_text()
    assert html.startswith("<!DOCTYPE html")
    assert "__PAYLOAD__" not in html          # payload was substituted
    assert "Morning commute to Union Station" in html
    assert "service_assumption" in html       # data wired through


def test_routed_station_snapshot_survives_without_large_grid(tmp_path):
    for sub in ('src','data','output'):
        (tmp_path/sub).mkdir()
    shutil.copytree(ROOT/'src',tmp_path/'src',dirs_exist_ok=True)
    for name in ('transit_model.json','station_itineraries.json'):
        shutil.copy(ROOT/'data'/name,tmp_path/'data'/name)
    (tmp_path/'output/isochrones.geojson').write_text(json.dumps({
        'type':'FeatureCollection','properties':{'source':'r5py travel-time grid'},'features':[]}))
    subprocess.run([sys.executable,'src/build_map.py'],cwd=tmp_path,check=True)
    html=(tmp_path/'output/union-station-transit-isochrone.html').read_text()
    payload=json.JSONDecoder().raw_decode(html.split('const DATA = ',1)[1])[0]
    cached=json.loads((ROOT/'data/station_itineraries.json').read_text())
    assert payload['stations'] == cached['stations']
    assert payload['generated_at'] == cached['generated_at']
    # A deliberate curated rebuild must not inherit routed station trip claims.
    subprocess.run([sys.executable,'src/build_isochrones.py'],cwd=tmp_path,check=True)
    subprocess.run([sys.executable,'src/build_map.py'],cwd=tmp_path,check=True)
    html=(tmp_path/'output/union-station-transit-isochrone.html').read_text()
    payload=json.JSONDecoder().raw_decode(html.split('const DATA = ',1)[1])[0]
    assert payload['stations'] == []
