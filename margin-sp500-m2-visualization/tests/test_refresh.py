import pandas as pd
import pytest

import fetch_data


def test_refresh_repeat_missing_sidecar_and_empty_series(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_data, "ROOT", tmp_path)
    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_data, "SERIES_CSV", tmp_path / "series.csv")
    monkeypatch.setattr(fetch_data, "PULLED_STAMP", tmp_path / "generated_at.txt")
    series = pd.Series([10.0], index=pd.to_datetime(["2025-03-31"]))
    monkeypatch.setattr(fetch_data, "_fetch_fred_monthly", lambda key: series)
    monkeypatch.setattr(fetch_data, "_fetch_margin_debit", lambda: series)
    monkeypatch.setattr(fetch_data, "_fetch_sp500_monthly", lambda: series)
    fetch_data.main()
    before = fetch_data.SERIES_CSV.stat().st_mtime_ns
    content = fetch_data.SERIES_CSV.read_bytes()
    fetch_data.main()
    assert fetch_data.SERIES_CSV.stat().st_mtime_ns == before
    fetch_data.PULLED_STAMP.unlink()
    fetch_data.main()
    assert fetch_data.PULLED_STAMP.exists()
    assert fetch_data.SERIES_CSV.stat().st_mtime_ns == before
    monkeypatch.setattr(fetch_data, "_fetch_margin_debit", lambda: pd.Series(dtype=float))
    with pytest.raises(RuntimeError):
        fetch_data.main()
    assert fetch_data.SERIES_CSV.read_bytes() == content


def test_missing_pull_date_recovers_rendered_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_data, "ROOT", tmp_path)
    monkeypatch.setattr(fetch_data, "PULLED_STAMP", tmp_path / "generated_at.txt")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / (tmp_path.name + ".html")).write_text("Data pulled 2025-01-02 &middot;")
    fetch_data.record_pull_date(False)
    assert fetch_data.PULLED_STAMP.read_text() == "2025-01-02\n"
