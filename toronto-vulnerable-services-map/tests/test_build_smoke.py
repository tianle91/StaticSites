"""Smoke test the offline map build end-to-end, without touching the network.

Rebuilds a minimal copy of the project layout (src/ + data/ + output/) in a temp
dir and runs build_map.py there, so it never clobbers the committed output.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "toronto-vulnerable-services-map"
INPUTS = ("services.json", "shelters.json", "geocode_cache.json")


@pytest.fixture
def built(tmp_path):
    for sub in ("src", "data", "output"):
        (tmp_path / sub).mkdir()
    shutil.copy(ROOT / "src" / "build_map.py", tmp_path / "src" / "build_map.py")
    for name in INPUTS:
        shutil.copy(ROOT / "data" / name, tmp_path / "data" / name)
    subprocess.run([sys.executable, "src/build_map.py"], cwd=tmp_path, check=True)
    return (tmp_path / "output" / f"{PROJECT}.html").read_text()


def test_html_is_self_contained(built):
    assert built.startswith("<!DOCTYPE html")
    assert "__PAYLOAD__" not in built            # payload was substituted


def test_curated_and_shelter_locations_both_render(built):
    services = json.loads((ROOT / "data" / "services.json").read_text())["locations"]
    shelters = json.loads((ROOT / "data" / "shelters.json").read_text())["locations"]
    assert services and shelters, "committed data is empty"
    assert json.dumps(services[0]["name"])[1:-1] in built
    assert json.dumps(shelters[0]["name"])[1:-1] in built
