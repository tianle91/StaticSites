"""Offline validation of snapshot completeness, counting inputs and publication."""
import copy
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

import build_site
import fetch_data as fetch

ROOT = pathlib.Path(__file__).resolve().parent.parent


def attributes(oid=1):
    return {"OBJECTID": oid, "EVENT_UNIQUE_ID": "GO-123", "CSI_CATEGORY": "Assault",
            "OCC_DATE": 1735707600000, "REPORT_DATE": 1735707600000,
            "NEIGHBOURHOOD_158": "Test (1)", "DIVISION": "D11",
            "OFFENCE": "Assault", "PREMISES_TYPE": "Apartment",
            "LAT_WGS84": 43.7, "LONG_WGS84": -79.4}


def mock_source(monkeypatch, batches=None, changed=False, final_ids=None):
    metadata = {"fields": [{"name": name} for name in fetch.COMMON + fetch.EXTRA['main']],
                "editingInfo": {"lastEditDate": 1}}
    calls = []
    def request(url, **params):
        calls.append((url, params))
        if not url.endswith('/query'):
            result = copy.deepcopy(metadata)
            if changed and len(calls) > 1:
                result['editingInfo']['lastEditDate'] = 2
            return result
        if params.get('returnIdsOnly'):
            count = sum(1 for _, p in calls if p.get('returnIdsOnly'))
            return {"objectIds": final_ids if count > 1 and final_ids is not None else [1, 2]}
        return batches if batches is not None else {"features": [{"attributes": attributes(i)} for i in [2, 1]]}
    monkeypatch.setattr(fetch, 'request_json', request)
    return calls


def test_complete_source_sorted_and_retains_multiple_offences(monkeypatch):
    mock_source(monkeypatch)
    rows, summary = fetch.fetch_source('main', 2025)
    assert [r[1] for r in rows] == [1, 2]
    assert rows[0][2] == rows[1][2]  # same incident, both offence/victim rows retained
    assert summary['records'] == 2


@pytest.mark.parametrize('response', [
    {"features": [{"attributes": attributes(1)}]},
    {"features": [{"attributes": attributes(1)}, {"attributes": attributes(1)}]},
    {"features": [{"attributes": attributes(1)}, {"attributes": attributes(2)}], "exceededTransferLimit": True},
])
def test_reject_incomplete_or_duplicate_batches(monkeypatch, response):
    mock_source(monkeypatch, response)
    with pytest.raises(ValueError, match='Incomplete'):
        fetch.fetch_source('main', 2025)


@pytest.mark.parametrize('changed,final_ids', [(True,None),(False,[1,2,3])])
def test_reject_source_changed_during_download(monkeypatch, changed, final_ids):
    mock_source(monkeypatch, changed=changed, final_ids=final_ids)
    with pytest.raises(ValueError, match='changed during'):
        fetch.fetch_source('main', 2025)


@pytest.mark.parametrize('lat,lon', [(None,None),(0,0),(float('nan'),-79.4),(90,180)])
def test_invalid_coordinates_remain_unmapped(lat, lon):
    a = attributes(); a.update(LAT_WGS84=lat, LONG_WGS84=lon)
    row = fetch.normalize('main', a)
    assert row[10:12] == [None,None]
    assert row[2] == 'GO-123'


def test_dates_use_toronto_calendar():
    assert fetch.date(1735689600000) == '2024-12-31'  # midnight UTC
    assert fetch.date(None) == ''


def test_unknown_category_fails():
    a = attributes();a['CSI_CATEGORY'] = 'Unknown'
    with pytest.raises(ValueError, match='Unknown offence'):
        fetch.normalize('main', a)


def test_api_error_fails(monkeypatch):
    monkeypatch.setattr(fetch, 'download', lambda *args: '{"error":{"message":"bad query"}}')
    with pytest.raises(ValueError, match='ArcGIS query failed'):
        fetch.request_json('https://example.invalid')


def test_long_batch_uses_post(monkeypatch):
    calls = []
    monkeypatch.setattr(fetch, 'download', lambda *args: calls.append(args) or '{}')
    fetch.request_json('https://example.invalid/query', objectIds='1,2')
    assert calls[0][0] == 'https://example.invalid/query'
    assert b'objectIds=1%2C2' in calls[0][1]


def test_unchanged_refresh_and_missing_asset_restoration(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, 'fetch_source', lambda source, year: ([fetch.normalize('main', attributes())], {"records":1}))
    monkeypatch.setattr(fetch, 'download', lambda url: '/* library */')
    fetch.refresh(data_dir=tmp_path)
    target = tmp_path / 'crimes.json'; before = target.read_bytes(); stamp = target.stat().st_mtime_ns
    (tmp_path / 'leaflet.js').unlink()
    fetch.refresh(data_dir=tmp_path)
    assert target.read_bytes() == before
    assert target.stat().st_mtime_ns == stamp
    assert (tmp_path / 'leaflet.js').exists()


@pytest.mark.parametrize('failure', ['source', 'asset'])
def test_failed_refresh_preserves_previous_snapshot(monkeypatch, tmp_path, failure):
    target = tmp_path / 'crimes.json'; target.write_text('old snapshot')
    def source(name, year):
        if failure == 'source' and name == 'homicide':
            raise ValueError('upstream failure')
        return [], {}
    def asset(url):
        raise ValueError('asset failure')
    monkeypatch.setattr(fetch, 'fetch_source', source)
    monkeypatch.setattr(fetch, 'download', asset)
    with pytest.raises(ValueError):
        fetch.refresh(data_dir=tmp_path)
    assert target.read_text() == 'old snapshot'
    assert list(tmp_path.iterdir()) == [target]


def test_offline_build_is_portable_deterministic_and_escapes_text(tmp_path):
    # A minimal snapshot exercises escaping without copying the large live data.
    data = {"columns":fetch.COLUMNS,"rows":[fetch.normalize('main', attributes())]}
    data['rows'][0][4] = '</script><script>alert(1)</script>'
    for name in fetch.ASSETS:
        (tmp_path / name).write_text('/* asset */')
    (tmp_path / 'crimes.json').write_text(json.dumps(data))
    html = build_site.render(tmp_path)
    assert html == build_site.render(tmp_path)
    assert '</script><script>alert(1)' not in html
    assert '\\u003c/script>' in html
    assert '__DATA__' not in html and '__APP__' not in html
    assert 'Data sources' in html and 'Approximate intersection locations' in html
    assert 'src="http' not in html  # no remote JS libraries


def test_committed_snapshot_matches_source_counts():
    data = json.loads((ROOT / 'data/crimes.json').read_text())
    assert data['columns'] == fetch.COLUMNS
    assert len(data['rows']) > 0
    for source, metadata in data['sources'].items():
        rows = [r for r in data['rows'] if r[0] == source]
        assert len(rows) == metadata['records']
        assert len({r[1] for r in rows}) == len(rows)
        assert all(len(r) == len(fetch.COLUMNS) for r in rows)


def test_builder_runs_from_other_directory(tmp_path):
    project = tmp_path / 'project'
    shutil.copytree(ROOT / 'src', project / 'src')
    shutil.copytree(ROOT / 'data', project / 'data')
    subprocess.run([sys.executable,str(project / 'src/build_site.py')], cwd=tmp_path, check=True)
    assert (project / 'output/toronto-crime-map.html').exists()


def test_merge_retains_source_rows_types_and_differing_points():
    a = fetch.normalize('main', attributes())
    b = list(a); b[0] = 'homicide'; b[1] = 99; b[3] = 'Homicide'; b[10] += .001
    c = list(a); c[2] = 'GO-OTHER'; c[10:12] = [None, None]
    data = {"columns": fetch.COLUMNS, "rows": [a, b, c], "start_year": 2025}
    payload = build_site.prepare_payload(data)
    assert "rows" not in payload
    assert payload["incidents"] == [{"id": a[2], "rows": [a, b]}, {"id": c[2], "rows": [c]}]
    assert payload["start_year"] == 2025
    # Grouping must leave the committed source model untouched.
    assert data["rows"] == [a, b, c]
