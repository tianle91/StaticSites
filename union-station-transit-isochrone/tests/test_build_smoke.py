"""Smoke test the stdlib builders end-to-end in isolation (no r5py/Java/GTFS).

Copies the scripts + the committed transit_model.json into a temp dir and runs
them there, so it neither needs the heavy deps nor clobbers committed outputs.
Without reachability.json, build_isochrones.py falls back to the curated model.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def built(tmp_path):
    for name in ("build_isochrones.py", "build_map.py", "transit_model.json"):
        shutil.copy(REPO / name, tmp_path / name)
    for script in ("build_isochrones.py", "build_map.py"):
        subprocess.run([sys.executable, script], cwd=tmp_path, check=True)
    return tmp_path


def test_isochrones_geojson_is_valid(built):
    geo = json.loads((built / "isochrones.geojson").read_text())
    assert geo["type"] == "FeatureCollection"
    assert geo["features"], "no band polygons produced"
    minutes = {f["properties"]["minutes"] for f in geo["features"]}
    assert minutes <= {30, 60, 90, 120}
    for f in geo["features"]:
        assert f["geometry"]["type"] == "MultiPolygon"


def test_index_html_rendered(built):
    html = (built / "index.html").read_text()
    assert html.startswith("<!DOCTYPE html")
    assert "__PAYLOAD__" not in html          # payload was substituted
    assert "Morning commute to Union Station" in html
    assert "service_assumption" in html       # data wired through
