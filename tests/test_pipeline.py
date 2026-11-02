from types import SimpleNamespace
import json
import pytest
import requests
from staticsites import pipeline, sources
from staticsites.assets import source_text


def test_failed_encoding_and_replace_preserve_previous_snapshot(tmp_path, monkeypatch):
    target = tmp_path / 'data.json'
    pipeline.write_snapshot(target, {'values':[0, 1]})
    before, mtime = target.read_bytes(), target.stat().st_mtime_ns
    assert not pipeline.write_snapshot(target, {'values':[0, 1]})
    assert target.stat().st_mtime_ns == mtime
    with pytest.raises(ValueError):
        pipeline.write_snapshot(target, {'values':[float('nan')]})
    def fail(*args):
        raise OSError('replace failed')
    monkeypatch.setattr(type(target), 'replace', fail)
    with pytest.raises(OSError):
        pipeline.write_snapshot(target, {'values':[2]})
    assert target.read_bytes() == before
    assert list(tmp_path.iterdir()) == [target]


def test_geocode_misses_are_cached_but_service_failures_are_not():
    cache, saved = {}, []
    assert pipeline.cached_lookup(cache, 'missing', lambda: None, lambda: saved.append(1)) is None
    assert pipeline.cached_lookup(cache, 'missing', lambda: pytest.fail('cached miss retried'), lambda: None) is None
    def fail():
        raise RuntimeError('service down')
    with pytest.raises(RuntimeError):
        pipeline.cached_lookup(cache, 'error', fail, lambda: None)
    with pytest.raises(RuntimeError):
        pipeline.cached_lookup(cache, 'write-error', lambda: [43, -79], fail)
    assert cache == {'missing':None} and saved == [1]


def test_ckan_retry_and_failure_are_bounded():
    calls, delays = [], []
    def get(url, **options):
        calls.append((url,options))
        if len(calls) < 3:
            raise requests.ConnectionError('interrupted')
        return SimpleNamespace(raise_for_status=lambda:None, json=lambda:{'success':True,'result':{'records':[0]}})
    assert sources.ckan_action('https://example.invalid', 'datastore_search', {'offset':0},
                               user_agent='test', get=get, attempts=3, sleep=delays.append) == {'records':[0]}
    assert delays == [1,2]
    assert calls[-1][1]['params'] == {'offset':0}
    assert calls[-1][1]['timeout'] == 60
    bad = lambda *a,**kw: SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'success':False})
    with pytest.raises(RuntimeError, match='CKAN'):
        sources.ckan_action('https://example.invalid', 'x', {}, user_agent='test', get=bad)
    with pytest.raises(ValueError, match='ArcGIS'):
        sources.arcgis_result({'error':{'message':'bad query'}})


def test_assets_are_embedded_from_package_not_another_project(tmp_path):
    assert 'const Explorer' in source_text(tmp_path, 'explorer.js')
    (tmp_path/'src').mkdir()
    (tmp_path/'src/app.js').write_text('local adapter')
    assert source_text(tmp_path, 'app.js') == 'local adapter'


def test_script_json_is_safe_readable_and_round_trips_values():
    from staticsites.assets import script_json
    value={'label':'</script><script>alert(1)</script>\u2028\u2029','points':[0,None,-1]}
    encoded=script_json(value)
    assert json.loads(encoded)==value
    assert '</script>' not in encoded
    assert '\u2028' not in encoded and '\u2029' not in encoded
    assert '\\u2028' in encoded and '\\u2029' in encoded
    assert '\n  "label"' in encoded
    with pytest.raises(ValueError):
        script_json({'value':float('nan')})
