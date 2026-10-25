"""Offline regressions for the portal failures seen during the full refresh."""
import pytest
import requests

import fetch_data


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.body


def install_bulk(monkeypatch, body, count=1, estimated=False):
    def ckan(action, **params):
        if action == "package_show":
            return {"resources": [{"name": "dinesafe.csv", "url": "https://example.test/official.csv"}]}
        return {"total": count, "total_was_estimated": estimated}
    monkeypatch.setattr(fetch_data, "ckan", ckan)
    monkeypatch.setattr(fetch_data.requests, "get", lambda *a, **kw: Response(body))


CSV = b'estId,inspectionDate,inspectionStatus,address,latitude,longitude\n1,2026-10-01,Pass,Test,43.65,-79.38\n'


def test_later_page_failure_discards_partial_rows_before_bulk(monkeypatch):
    install_bulk(monkeypatch, CSV)
    def pages(*args):
        yield {"estId": "partial API row"}
        raise requests.HTTPError("502")
    monkeypatch.setattr(fetch_data, "datastore_records", pages)
    rows = list(fetch_data.iter_records("current"))
    assert len(rows) == 1
    assert rows[0]["estId"] == "1"


@pytest.mark.parametrize("body,count,estimated", [
    (CSV, 2, False), (CSV, 1, True), (b'wrong,columns\n1,2\n', 1, False),
    (CSV + b'2,short\n', 2, False),
])
def test_failed_bulk_keeps_existing_snapshot(tmp_path, monkeypatch, body, count, estimated):
    install_bulk(monkeypatch, body, count, estimated)
    def fail(*args):
        raise requests.HTTPError("502")
    monkeypatch.setattr(fetch_data, "datastore_records", fail)
    monkeypatch.setattr(fetch_data, "active_resource_id", lambda: "current")
    destination = tmp_path / "dinesafe.json"
    destination.write_text('previous snapshot\n')
    monkeypatch.setattr(fetch_data, "OUT_PATH", destination)
    with pytest.raises(RuntimeError):
        fetch_data.main()
    assert destination.read_text() == 'previous snapshot\n'


def test_changing_count_rejects_export(monkeypatch):
    install_bulk(monkeypatch, CSV)
    counts = iter([1, 2])
    monkeypatch.setattr(fetch_data, "exact_count", lambda rid: next(counts))
    with pytest.raises(RuntimeError, match="changing"):
        fetch_data.bulk_records("current")


def test_successful_pagination_does_not_download_csv(monkeypatch):
    monkeypatch.setattr(fetch_data, "exact_count", lambda rid: 1)
    monkeypatch.setattr(fetch_data, "datastore_records", lambda *a: iter([{"estId": "1"}]))
    assert list(fetch_data.iter_records("current")) == [{"estId": "1"}]
