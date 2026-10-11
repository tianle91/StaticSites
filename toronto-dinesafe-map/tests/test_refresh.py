import pytest

import fetch_data


def test_refresh_reordering_and_failure_preserve_data(tmp_path, monkeypatch):
    destination = tmp_path / "dinesafe.json"
    monkeypatch.setattr(fetch_data, "OUT_PATH", destination)
    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_data, "active_resource_id", lambda: "test")
    rows = [{"estId": "1", "estName": "Test", "Latitude": "43.65", "Longitude": "-79.38",
             "inspectionDate": "2026-10-01", "inspectionStatus": "Pass", "deficiencyDesc": item}
            for item in ("Z", "A")]
    monkeypatch.setattr(fetch_data, "iter_records", lambda rid: iter(rows))
    fetch_data.main()
    before = destination.stat().st_mtime_ns
    previous = destination.read_bytes()
    rows.reverse()
    fetch_data.main()
    assert destination.stat().st_mtime_ns == before
    rows.clear()
    with pytest.raises(RuntimeError):
        fetch_data.main()
    assert destination.read_bytes() == previous


def test_geocoding_failure_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_data, "cache", {})
    monkeypatch.setattr(fetch_data, "CACHE_PATH", tmp_path / "cache.json")
    def fail(*a, **kw):
        raise OSError("service unavailable")
    monkeypatch.setattr(fetch_data, "_lookup", fail)
    with pytest.raises(OSError):
        fetch_data.geocode("test")
    assert fetch_data.cache == {}
    monkeypatch.setattr(fetch_data, "_lookup", lambda *a, **kw: None)
    assert fetch_data.geocode("test") is None
    assert fetch_data.cache == {"test": None}
