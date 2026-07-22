"""Smoke test the offline build end-to-end, without touching the network.

Rebuilds a minimal copy of the project layout (src/ + data/ + output/) in a temp
dir and runs the builder there, so it never clobbers the committed output.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "toronto-dinesafe-map"


@pytest.fixture
def built(tmp_path):
    for sub in ("src", "data", "output"):
        (tmp_path / sub).mkdir()
    shutil.copy(ROOT / "src" / "build_map.py", tmp_path / "src" / "build_map.py")
    shutil.copy(ROOT / "data" / "dinesafe.json", tmp_path / "data" / "dinesafe.json")
    subprocess.run([sys.executable, "src/build_map.py"], cwd=tmp_path, check=True)
    return (tmp_path / "output" / (PROJECT + ".html")).read_text()


def test_html_is_self_contained(built):
    assert built.startswith("<!DOCTYPE html")
    assert "__PAYLOAD__" not in built          # payload was substituted


def test_documents_data_sources(built):
    # Every site must document its data sources on the page itself.
    assert "Data sources" in built
    assert "open.toronto.ca/dataset/dinesafe" in built


def test_renders_every_committed_establishment(built):
    data = json.loads((ROOT / "data" / "dinesafe.json").read_text())
    # Pull the embedded payload back out of the page and compare by name, so the
    # check is exact regardless of HTML/JSON escaping (real names contain quotes,
    # ampersands, etc.).
    marker = "const DATA = "
    start = built.index(marker) + len(marker)
    end = built.index(";\n", start)
    payload = json.loads(built[start:end])
    rendered = {e["name"] for e in payload["establishments"]}
    for e in data["establishments"]:
        if e.get("lat") is not None and e.get("lon") is not None:
            assert e["name"] in rendered


def test_status_categories_present(built):
    # The three DineSafe outcomes drive the legend/colours.
    assert "Pass" in built
    assert "Conditional Pass" in built
    assert "Closed" in built
