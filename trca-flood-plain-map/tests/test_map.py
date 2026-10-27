import json
import pathlib

import pytest

import build_site
import fetch_data


def test_snapshot_is_content_aware_and_restores_missing_file(tmp_path):
    target = tmp_path / "data.json"
    assert fetch_data.write_snapshot(target, {"items": [1]})
    original, mtime = target.read_bytes(), target.stat().st_mtime_ns
    assert not fetch_data.write_snapshot(target, {"items": [1]})
    assert target.read_bytes() == original
    assert target.stat().st_mtime_ns == mtime
    target.unlink()
    assert fetch_data.write_snapshot(target, {"items": [1]})


def test_script_payload_cannot_end_its_html_element():
    rendered = build_site.render({"description": "</script><script>alert(1)</script>"})
    payload = rendered.split("const DATA = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(payload)["description"] == "</script><script>alert(1)</script>"
    assert "<script>" not in payload
    assert "__PAYLOAD__" not in rendered
    assert "Data sources" in rendered


def feature(kind="Polygon"):
    return {"type": "Feature", "properties": {"OBJECTID": 1, "Watershed": "Don River"},
            "geometry": {"type": kind, "coordinates": [[[-79.4, 43.7], [-79.3, 43.7], [-79.4, 43.8], [-79.4, 43.7]]]}}


def test_validation_rejects_wrong_geometry_and_coordinates():
    f = feature("LineString")
    with pytest.raises(ValueError, match="geometry"):
        fetch_data.validate_collection({"type": "FeatureCollection", "features": [f]}, "polygons")
    f = feature()
    f["geometry"]["coordinates"][0][0] = [0, 0]
    with pytest.raises(ValueError, match="outside"):
        fetch_data.validate_collection({"type": "FeatureCollection", "features": [f]}, "polygons")


def test_validation_preserves_nonspatial_source_records():
    f = feature()
    f["geometry"] = None
    fetch_data.validate_collection({"type": "FeatureCollection", "features": [feature(), f]}, "polygons")


def test_incomplete_batch_fails(monkeypatch):
    responses = iter([{"objectIds": [1, 2]}, {"features": [feature()]}])
    monkeypatch.setattr(fetch_data, "request_json", lambda *args: next(responses))
    with pytest.raises(ValueError, match="Incomplete"):
        fetch_data.fetch_layer("https://example.test", "OBJECTID", "polygons")


def test_second_source_failure_does_not_publish(monkeypatch, tmp_path):
    target = tmp_path / "floodplain.json"
    target.write_text('{"old": true}')
    monkeypatch.setattr(fetch_data, "OUT_PATH", target)
    def fetch(url, fields, kind):
        if kind == "lines":
            raise ValueError("source unavailable")
        return {"features": [feature()]}
    monkeypatch.setattr(fetch_data, "fetch_layer", fetch)
    with pytest.raises(ValueError, match="unavailable"):
        fetch_data.main()
    assert target.read_text() == '{"old": true}'


def test_all_null_geometry_response_is_rejected():
    f = feature()
    f["geometry"] = None
    with pytest.raises(ValueError, match="No drawable"):
        fetch_data.validate_collection({"type": "FeatureCollection", "features": [f]}, "polygons")
