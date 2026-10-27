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


def permit(number="22 100000 BLD", geo_id="42", address="10", revision="00"):
    return {"PERMIT_NUM": number, "REVISION_NUM": revision, "GEO_ID": geo_id,
            "STREET_NUM": address, "STREET_NAME": "TEST", "STREET_TYPE": "ST", "STATUS": "Inspection",
            "APPLICATION_DATE": "2022-01-01", "EST_CONST_COST": "DO NOT UPDATE OR DELETE THIS INFO FIELD"}


def test_full_register_keeps_unmatched_and_multiple_properties():
    records = [permit(), permit(address="12"), permit(geo_id="missing", revision="01")]
    data = fetch_data.normalize(records, {"42": (43.7, -79.4)}, expected_count=3)
    assert data["stats"] == {"total": 3, "mapped": 2, "unmatched": 1}
    assert len(data["permits"]) == 3
    fields = {name: i for i, name in enumerate(data["columns"])}
    assert all(row[fields["cost"]] is None for row in data["permits"])
    assert sum(row[fields["lat"]] is None for row in data["permits"]) == 1
    assert fetch_data.normalize(reversed(records), {"42": (43.7, -79.4)}) == data


def test_address_join_is_deterministic_and_prefers_land():
    rows = [{"ADDRESS_ID": "99", "ADDRESS_POINT_ID": "42", "ADDRESS_CLASS": "L",
             "geometry": {"type": "MultiPoint", "coordinates": [[-79.4, 43.7]]}},
            {"ADDRESS_ID": "100", "ADDRESS_POINT_ID": "42", "ADDRESS_CLASS": "E",
             "geometry": {"type": "Point", "coordinates": [-79.5, 43.8]}}]
    assert fetch_data.address_index(rows) == fetch_data.address_index(reversed(rows)) == {"42": (43.7, -79.4)}
    with pytest.raises(ValueError, match="Incomplete"):
        fetch_data.address_index(rows, expected_count=3)


def test_incomplete_permit_export_and_total_join_failure_are_rejected():
    with pytest.raises(ValueError, match="Incomplete"):
        fetch_data.normalize([permit()], {"42": (43.7, -79.4)}, expected_count=2)
    with pytest.raises(ValueError, match="No permits matched"):
        fetch_data.normalize([permit()], {})


@pytest.mark.parametrize("value", ["", "DO NOT UPDATE OR DELETE THIS INFO FIELD", "NaN", "Infinity", "-1"])
def test_invalid_costs_are_not_shown_as_numbers(value):
    assert fetch_data.cost(value) is None


def test_csv_schema_failure_and_bad_coordinates_fail(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("unexpected\n1\n")
    with pytest.raises(ValueError, match="Missing required"):
        list(fetch_data.records(path, {"PERMIT_NUM"}))
    with pytest.raises(ValueError, match="Invalid municipal"):
        fetch_data.point({"geometry": {"type": "Point", "coordinates": [0, 0]}})


def test_download_retries_interrupted_stream_without_appending(tmp_path, monkeypatch):
    import requests

    attempts = []

    class Response:
        def __enter__(self):
            attempts.append(1)
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            if len(attempts) == 1:
                yield b'partial'
                raise requests.ConnectionError('interrupted download')
            yield b'complete export'

    monkeypatch.setattr(fetch_data.requests, "get", lambda *a, **kw: Response())
    monkeypatch.setattr(fetch_data.time, "sleep", lambda delay: None)
    target = tmp_path / "export.csv"
    fetch_data.download("https://example.test/export.csv", target)
    assert target.read_bytes() == b'complete export'
    assert len(attempts) == 2


def test_download_server_failure_has_bounded_retries(tmp_path, monkeypatch):
    import requests

    attempts = []
    def fail(*args, **kwargs):
        attempts.append(1)
        raise requests.HTTPError('500')
    monkeypatch.setattr(fetch_data.requests, "get", fail)
    monkeypatch.setattr(fetch_data.time, "sleep", lambda delay: None)
    with pytest.raises(requests.HTTPError):
        fetch_data.download("https://example.test/export.csv", tmp_path / "export.csv")
    assert len(attempts) == 3
