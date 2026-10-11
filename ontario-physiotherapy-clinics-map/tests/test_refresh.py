"""Mocked refreshes must preserve good data and avoid ordering-only changes."""
import json

import pytest

import fetch_data


def test_refresh_reordering_and_empty_source(tmp_path, monkeypatch):
    destination = tmp_path / "clinics.json"
    monkeypatch.setattr(fetch_data, "CLINICS_PATH", destination)
    rows = [{"Operating Name": name, "Clinic Address": "1 Test St", "City": "Toronto"}
            for name in ("B", "A")]
    monkeypatch.setattr(fetch_data, "ckan", lambda *a, **kw: {"records": rows})
    monkeypatch.setattr(fetch_data, "city_center", lambda city: [43.65, -79.38])
    monkeypatch.setattr(fetch_data, "geocode", lambda *a: ([43.65, -79.38], "address"))
    fetch_data.main()
    before = destination.stat().st_mtime_ns
    content = destination.read_bytes()
    rows.reverse()
    fetch_data.main()
    assert destination.stat().st_mtime_ns == before
    rows.clear()
    with pytest.raises(RuntimeError):
        fetch_data.main()
    assert destination.read_bytes() == content


def test_service_error_is_not_cached_but_no_match_is(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_data, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(fetch_data, "cache", {})
    def fail(*a, **kw):
        raise OSError("geocoder unavailable")
    monkeypatch.setattr(fetch_data, "_lookup", fail)
    with pytest.raises(OSError):
        fetch_data._cached({"q": "test"})
    assert fetch_data.cache == {}
    monkeypatch.setattr(fetch_data, "_lookup", lambda *a, **kw: None)
    assert fetch_data._cached({"q": "test"}) is None
    assert fetch_data.cache == {"test": None}
