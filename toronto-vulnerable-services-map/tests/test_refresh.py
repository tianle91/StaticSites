import pytest

import fetch_data


def test_shelter_reordering_and_required_failure(tmp_path, monkeypatch):
    destination = tmp_path / "shelters.json"
    monkeypatch.setattr(fetch_data, "SHELTERS_PATH", destination)
    rows = [{"LOCATION_ID": name, "LOCATION_NAME": name, "LOCATION_ADDRESS": "1 Test St",
             "SERVICE_USER_COUNT": 10} for name in ("Z", "A")]
    def ckan(action, **kwargs):
        if action == "package_show":
            return {"resources": [{"datastore_active": True, "name": "test", "id": "1"}]}
        if kwargs.get("limit") == 1:
            return {"records": [{"OCCUPANCY_DATE": "2026-10-01"}]}
        return {"records": rows}
    monkeypatch.setattr(fetch_data, "ckan", ckan)
    monkeypatch.setattr(fetch_data, "geocode", lambda address: [43.65, -79.38])
    fetch_data.fetch_shelters()
    before = destination.stat().st_mtime_ns
    previous = destination.read_bytes()
    rows.reverse()
    fetch_data.fetch_shelters()
    assert destination.stat().st_mtime_ns == before
    monkeypatch.setattr(fetch_data, "refine_curated", lambda: None)
    def fail():
        raise OSError("shelter API unavailable")
    monkeypatch.setattr(fetch_data, "fetch_shelters", fail)
    with pytest.raises(OSError):
        fetch_data.main()
    assert destination.read_bytes() == previous


def test_geocoder_service_failure_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_data, "cache", {})
    monkeypatch.setattr(fetch_data, "CACHE_PATH", tmp_path / "cache.json")
    def fail(*a, **kw):
        raise OSError("service unavailable")
    monkeypatch.setattr(fetch_data, "_lookup", fail)
    with pytest.raises(OSError):
        fetch_data.geocode("test")
    assert fetch_data.cache == {}
