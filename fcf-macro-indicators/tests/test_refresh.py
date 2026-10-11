import sys

import pandas as pd
import pytest

import fetch_data


def test_complete_refresh_repeat_sidecars_and_partial_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_data, "ROOT", tmp_path)
    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    for name, filename in (("SERIES_CSV", "series.csv"), ("PULLED_STAMP", "generated_at.txt"),
                           ("FCF_SOURCE_FILE", "fcf_source.txt")):
        monkeypatch.setattr(fetch_data, name, tmp_path / filename)
    monkeypatch.setattr(sys, "argv", ["fetch_data.py", "--tickers", "AAPL,MSFT"])
    monkeypatch.setattr(fetch_data, "_require_sec_user_agent", lambda: "test")
    series = pd.Series([10.0, 20.0], index=pd.to_datetime(["2025-03-31", "2025-06-30"]))
    macro = pd.DataFrame({column: series for column in fetch_data.FRED_SERIES.values()})
    monkeypatch.setattr(fetch_data, "_fetch_fred_quarterly", lambda: macro)
    monkeypatch.setattr(fetch_data, "_fetch_sp500_quarterly", lambda: series)
    monkeypatch.setattr(fetch_data, "_sec_session", lambda: None)
    monkeypatch.setattr(fetch_data, "_load_ticker_cik_map", lambda session: {})
    monkeypatch.setattr(fetch_data, "_fetch_company_fcf", lambda *a: series)
    monkeypatch.setattr(fetch_data, "_fetch_company_cash", lambda *a: series)
    fetch_data.main()
    before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir()}
    fetch_data.main()
    assert before == {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir()}
    fetch_data.PULLED_STAMP.unlink()
    fetch_data.FCF_SOURCE_FILE.unlink()
    fetch_data.main()
    assert fetch_data.PULLED_STAMP.exists() and fetch_data.FCF_SOURCE_FILE.exists()
    assert fetch_data.SERIES_CSV.stat().st_mtime_ns == before["series.csv"][1]
    def fail(*a):
        raise RuntimeError("company unavailable")
    monkeypatch.setattr(fetch_data, "_fetch_company_cash", fail)
    with pytest.raises(RuntimeError):
        fetch_data.main()
    assert fetch_data.SERIES_CSV.read_bytes() == before["series.csv"][0]
    monkeypatch.setattr(fetch_data, "_fetch_company_cash", lambda *a: series)
    macro["m2"] = float("nan")
    with pytest.raises(RuntimeError):
        fetch_data.main()
    assert fetch_data.SERIES_CSV.read_bytes() == before["series.csv"][0]


def test_missing_pull_date_recovers_rendered_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_data, "ROOT", tmp_path)
    monkeypatch.setattr(fetch_data, "PULLED_STAMP", tmp_path / "generated_at.txt")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / (tmp_path.name + ".html")).write_text("Data pulled 2025-01-02 &middot;")
    fetch_data.record_pull_date(False)
    assert fetch_data.PULLED_STAMP.read_text() == "2025-01-02\n"
