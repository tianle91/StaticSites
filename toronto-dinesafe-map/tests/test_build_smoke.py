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


def test_search_and_detail_sidebar_present(built):
    # The search box lists matches, and clicking a business opens a detail
    # sidebar with its inspection history.
    assert 'id="search"' in built
    assert 'id="results"' in built            # search results list
    assert 'id="sidebar"' in built            # detail sidebar container
    assert "openSidebar" in built             # marker/result click handler
    assert "Inspection history" in built


def _build_in(tmp_path, data):
    """Run the builder against a custom data/dinesafe.json and return the page."""
    for sub in ("src", "data", "output"):
        (tmp_path / sub).mkdir(exist_ok=True)
    shutil.copy(ROOT / "src" / "build_map.py", tmp_path / "src" / "build_map.py")
    (tmp_path / "data" / "dinesafe.json").write_text(json.dumps(data), encoding="utf-8")
    subprocess.run([sys.executable, "src/build_map.py"], cwd=tmp_path, check=True)
    return (tmp_path / "output" / (PROJECT + ".html")).read_text()


def _payload(built):
    marker = "const DATA = "
    start = built.index(marker) + len(marker)
    end = built.index(";\n", start)
    return json.loads(built[start:end])


def test_full_inspection_history_is_embedded(tmp_path):
    # When the data carries a per-inspection timeline (what `make data` produces),
    # the builder embeds it with per-inspection infraction detail for the sidebar.
    data = {
        "generated_at": "2026-01-01",
        "source_page": "https://open.toronto.ca/dataset/dinesafe/",
        "establishments": [{
            "name": "Test Diner", "type": "Restaurant", "address": "1 Test St",
            "lat": 43.65, "lon": -79.38, "status": "Conditional Pass",
            "last_inspection": "2026-01-01", "infractions": 1, "min_per_year": "3",
            "inspections": [
                {"date": "2026-01-01", "status": "Conditional Pass",
                 "infractions": [{"detail": "Sanitation deficiency",
                                  "severity": "C - Crucial", "action": "Corrected"}]},
                {"date": "2025-06-01", "status": "Pass", "infractions": []},
            ],
        }],
    }
    built = _build_in(tmp_path, data)
    est = _payload(built)["establishments"][0]
    assert len(est["inspections"]) == 2
    # Detail, severity and derived count are carried through for the sidebar.
    ins = est["inspections"][0]
    assert ins["infractions"][0]["detail"] == "Sanitation deficiency"
    assert ins["infractions"][0]["severity"] == "C - Crucial"
    assert ins["infraction_count"] == 1


def test_summary_only_data_still_builds(tmp_path):
    # Older summary-only data (no `inspections` key) must still build; the page
    # synthesises the timeline client-side, so no inspections key is embedded.
    data = {
        "establishments": [{
            "name": "Legacy Grill", "type": "Restaurant", "address": "2 Old Rd",
            "lat": 43.66, "lon": -79.39, "status": "Pass",
            "last_inspection": "2025-01-01", "infractions": 0, "min_per_year": "2",
        }],
    }
    built = _build_in(tmp_path, data)
    est = _payload(built)["establishments"][0]
    assert est["name"] == "Legacy Grill"
    assert "inspections" not in est          # synthesised at display time, not embedded
