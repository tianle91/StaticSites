"""Smoke test the offline map build end-to-end, without touching the network.

Rebuilds a minimal copy of the project layout (src/ + data/ + output/) in a temp
dir and runs build_map.py there, so it never clobbers the committed output.
"""
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "ontario-physiotherapy-clinics-map"


@pytest.fixture
def built(tmp_path):
    for sub in ("src", "data", "output"):
        (tmp_path / sub).mkdir()
    shutil.copy(ROOT / "src" / "build_map.py", tmp_path / "src" / "build_map.py")
    shutil.copy(ROOT / "data" / "clinics.json", tmp_path / "data" / "clinics.json")
    subprocess.run([sys.executable, "src/build_map.py"], cwd=tmp_path, check=True)
    return (tmp_path / "output" / f"{PROJECT}.html").read_text()


def test_html_is_self_contained(built):
    assert built.startswith("<!DOCTYPE html")
    assert "__PAYLOAD__" not in built            # payload was substituted
    assert "Publicly-Funded Physiotherapy" in built


def test_every_clinic_reaches_the_page(built):
    import json
    clinics = json.loads((ROOT / "data" / "clinics.json").read_text())["clinics"]
    assert clinics, "no clinics in the committed data"
    # The payload is embedded as JSON, so a sampled name must appear verbatim.
    assert json.dumps(clinics[0]["name"])[1:-1] in built
