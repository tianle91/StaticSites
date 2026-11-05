"""Source alignment and publication checks use offline response fixtures."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import build_site
import fetch_data
from fetch_data import TENORS, assemble, parse_canada, parse_treasury, validate_dataset

ROOT = Path(__file__).resolve().parent.parent


def treasury_fixture(rows):
    entries = []
    for day, values in rows:
        properties = '<d:NEW_DATE>' + day + 'T00:00:00</d:NEW_DATE>'
        properties += ''.join(f'<d:{tenor[2]}>{value}</d:{tenor[2]}>'
                              for tenor, value in zip(TENORS, values))
        entries.append('<entry><content><m:properties>' + properties + '</m:properties></content></entry>')
    return ('<feed xmlns="http://www.w3.org/2005/Atom" '
            'xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices" '
            'xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">'
            + ''.join(entries) + '</feed>')


def canada_fixture():
    return {
        'seriesDetail': {'AVG.INTWO': {'label': 'CORRA'}, **{tenor[3]: {'label': tenor[0]} for tenor in TENORS}},
        'observations': [
            {'d': '2026-11-02', 'AVG.INTWO': {'v': '2.54'}, **{tenor[3]: {'v': '3.00'} for tenor in TENORS}},
            {'d': '2026-11-03', 'AVG.INTWO': {'v': '2.53'}, **{tenor[3]: {'v': '3.10'} for tenor in TENORS}},
        ],
    }


def test_parse_official_envelopes_and_zero_yields():
    us = parse_treasury(treasury_fixture([('2026-11-03', list(range(len(TENORS))))]))
    assert us['2026-11-03'] == list(range(len(TENORS)))
    assert parse_canada(canada_fixture())['2026-11-03'] == [3.1] * len(TENORS)


def test_shared_date_never_mixes_trading_days():
    us = {'2026-11-02': [4] * len(TENORS), '2026-11-04': [5] * len(TENORS)}
    result = assemble(us, parse_canada(canada_fixture()), date(2026, 11, 5))
    assert result['date'] == '2026-11-02'
    assert result['series'][0]['yields'] == [4] * len(TENORS)
    assert result['series'][1]['yields'] == [3] * len(TENORS)
    assert result['latest_available'] == {'us': '2026-11-04', 'canada': '2026-11-03'}


def test_incomplete_day_is_not_filled_from_another_day():
    source = canada_fixture()
    del source['observations'][1][TENORS[0][3]]
    rows = parse_canada(source)
    assert rows['2026-11-03'][0] is None
    assert rows['2026-11-03'][1:] == [3.1]*(len(TENORS)-1)
    assert rows['2026-11-02'][0] == 3


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', 'garbage', '1000'])
def test_bad_values_fail(bad):
    source = canada_fixture()
    source['observations'][0][TENORS[0][3]]['v'] = bad
    with pytest.raises(ValueError):
        parse_canada(source)


def test_missing_required_series_fails():
    source = canada_fixture()
    del source['seriesDetail'][TENORS[0][3]]
    with pytest.raises(ValueError):
        parse_canada(source)


def test_stale_and_nonoverlapping_sources_fail():
    with pytest.raises(ValueError):
        assemble({'2026-11-02': [4]*len(TENORS)}, {'2026-11-03': [3]*len(TENORS)}, date(2026, 11, 5))
    with pytest.raises(ValueError):
        assemble({'2026-10-01': [4]*len(TENORS)}, {'2026-10-01': [3]*len(TENORS)}, date(2026, 11, 5))


def test_failed_required_source_preserves_snapshot(tmp_path, monkeypatch):
    output = tmp_path / 'curves.json'
    previous = json.dumps(snapshot_fixture())
    output.write_text(previous)
    monkeypatch.setattr(fetch_data, 'OUT', output)
    response = Mock(content=treasury_fixture([('2026-11-03', [4]*len(TENORS))]))
    monkeypatch.setattr(fetch_data, 'get_response', Mock(side_effect=[response, RuntimeError('unavailable')]))
    with pytest.raises(RuntimeError):
        fetch_data.main(date(2026, 1, 1))
    assert output.read_text() == previous


def test_build_rejects_incomplete_committed_data():
    data = json.loads((ROOT / 'data/curves.json').read_text())
    invalid = deepcopy(data)
    invalid['series'][1]['yields'].pop()
    with pytest.raises(ValueError):
        validate_dataset(invalid)


def test_build_is_standalone_and_content_aware(tmp_path, monkeypatch):
    (tmp_path / 'data').mkdir()
    (tmp_path / 'src').symlink_to(ROOT / 'src', target_is_directory=True)
    (tmp_path / 'data/curves.json').write_text((ROOT / 'data/curves.json').read_text())
    monkeypatch.setattr(build_site, 'ROOT', tmp_path)
    output = build_site.build()
    html = output.read_text()
    before = output.stat().st_mtime_ns
    build_site.build()
    assert output.stat().st_mtime_ns == before
    assert '<script src=' not in html and '__DATA__' not in html and '__APP__' not in html
    assert 'home.treasury.gov' in html and 'bankofcanada.ca' in html
    assert 'Canada’s long-term benchmark' in html


def snapshot_fixture():
    return assemble({'2026-11-02': [4]*len(TENORS)},
                    {'2026-11-02': [3]*len(TENORS)}, date(2026, 11, 5))


def official_snapshot(us=None, canada=None):
    return fetch_data.build_snapshot(
        us or {'2026-11-02': [4]*len(TENORS)},
        canada or {'2026-11-02': [3]*len(TENORS)},
        {'2026-11-02': 3.95}, {'2026-11-02': 2.54}, date(2026, 11, 5),
    )


def test_history_and_current_snapshot_must_agree():
    merged = official_snapshot()
    merged['history']['us']['2026-11-02'] = [8]*len(TENORS)
    with pytest.raises(ValueError, match='differs from history'):
        validate_dataset(merged)


def test_invalid_history_is_rejected():
    merged = official_snapshot()
    merged['history']['us']['2026-10-01'] = [float('nan')]*len(TENORS)
    with pytest.raises(ValueError):
        validate_dataset(merged)


def test_refresh_preserves_bytes_and_timestamp_when_sources_are_unchanged(tmp_path, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 5)

    monkeypatch.setattr(fetch_data, 'date', FixedDate)
    output = tmp_path / 'curves.json'
    monkeypatch.setattr(fetch_data, 'OUT', output)
    values = [4]*len(TENORS)
    us = Mock(content=treasury_fixture([('2026-11-03', values)]))
    canada = Mock()
    canada.json.return_value = canada_fixture()
    overnight = Mock()
    overnight.json.return_value = {'refRates': [{'effectiveDate': '2026-11-03', 'type': 'SOFR', 'percentRate': 3.97}]}
    monkeypatch.setattr(fetch_data, 'get_response', Mock(side_effect=[us, canada, overnight, us, canada, overnight]))
    fetch_data.main(date(2026, 1, 1))
    before = output.read_bytes(), output.stat().st_mtime_ns
    fetch_data.main(date(2026, 1, 1))
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_overnight_parsers_use_effective_observation_dates():
    sofr = fetch_data.parse_sofr({'refRates': [
        {'effectiveDate': '2026-11-03', 'type': 'SOFR', 'percentRate': 3.97},
        {'effectiveDate': '2026-11-02', 'type': 'SOFR', 'percentRate': 0},
    ]})
    assert sofr == {'2026-11-03': 3.97, '2026-11-02': 0}
    assert fetch_data.parse_corra(canada_fixture()) == {'2026-11-02': 2.54, '2026-11-03': 2.53}
    with pytest.raises(ValueError):
        fetch_data.parse_sofr({'refRates': [{'effectiveDate': '2026-11-03', 'type': 'SOFR', 'percentRate': 'NaN'}]})
    with pytest.raises(ValueError):
        fetch_data.parse_corra({'seriesDetail': {}, 'observations': []})


def test_overnight_display_is_same_day_and_leaves_original_history_unchanged():
    data = snapshot_fixture()
    data['overnight_history'] = {'us': {'2026-11-02': 3.95}, 'canada': {'2026-11-01': 2.5}}
    data['overnight_sources'] = fetch_data.OVERNIGHT_SOURCES
    original = deepcopy(data)
    display = build_site.display_data(validate_dataset(data))
    assert data == original
    assert display['tenors'] == data['tenors']
    assert display['series'][0]['overnight'] == 3.95
    assert display['series'][1]['overnight'] is None
    assert display['series'][0]['yields'] == data['series'][0]['yields']
    assert display['series'][1]['overnightName'] == 'CORRA'
    assert display['overnight_history'] == data['overnight_history']


def test_failed_overnight_source_preserves_all_previous_data(tmp_path, monkeypatch):
    output = tmp_path / 'curves.json'
    previous = json.dumps(snapshot_fixture())
    output.write_text(previous)
    monkeypatch.setattr(fetch_data, 'OUT', output)
    us = Mock(content=treasury_fixture([('2026-11-03', [4]*len(TENORS))]))
    canada = Mock()
    canada.json.return_value = canada_fixture()
    monkeypatch.setattr(fetch_data, 'get_response', Mock(side_effect=[us, canada, RuntimeError('SOFR unavailable')]))
    with pytest.raises(RuntimeError):
        fetch_data.main(date(2026, 1, 1))
    assert output.read_text() == previous


def test_historical_treasury_missing_maturities_remain_null():
    xml = treasury_fixture([('1990-01-02', [8]*len(TENORS))])
    for field in ['BC_1MONTH', 'BC_2MONTH']:
        xml = xml.replace(f'<d:{field}>8</d:{field}>', '')
    rows = parse_treasury(xml)
    assert rows['1990-01-02'][:2] == [None, None]
    assert rows['1990-01-02'][2:] == [8]*(len(TENORS)-2)


def test_partial_history_survives_and_latest_comparison_stays_complete():
    us = {'2026-11-03': [None, *([4]*10)]}
    canada = {'2026-11-03': [3]*len(TENORS)}
    result = official_snapshot({'2026-11-02': [4]*len(TENORS), **us},
                               {'2026-11-02': [3]*len(TENORS), **canada})
    assert result['date'] == '2026-11-02'
    assert result['history']['us']['2026-11-03'][0] is None
    assert result['latest_available']['us'] == '2026-11-02'
    assert result['latest_available']['canada'] == '2026-11-03'


def test_coverage_reports_real_observations_without_counting_gaps():
    result = official_snapshot(us={'1990-01-02': [None, *([8]*10)], '2026-11-02': [4]*len(TENORS)})
    coverage = fetch_data.coverage(result)
    assert coverage['curves']['us']['1M'] == {'start': '2026-11-02', 'end': '2026-11-02', 'observations': 1}
    assert coverage['curves']['us']['2M'] == {'start': '1990-01-02', 'end': '2026-11-02', 'observations': 2}


def test_history_rejects_empty_curves_and_malformed_lengths():
    for values in [[None]*len(TENORS), [3]*3]:
        with pytest.raises(ValueError):
            official_snapshot(us={'1990-01-02': values, '2026-11-02': [4]*len(TENORS)})


def test_default_refresh_replaces_previous_pull_with_official_history(tmp_path, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 5)

    monkeypatch.setattr(fetch_data, 'date', FixedDate)
    output = tmp_path / 'curves.json'
    output.write_text(json.dumps({
        'history': {'us': {'1980-01-02': [9]*len(TENORS), '2026-11-03': [9]*len(TENORS)}},
        'overnight_history': {'us': {'1980-01-02': 9}},
    }))
    monkeypatch.setattr(fetch_data, 'OUT', output)

    def treasury_year(year):
        if year == 2026:
            return {'2026-11-02': [4]*len(TENORS), '2026-11-03': [None, *([4]*10)]}
        return {f'{year}-01-02': [4]*len(TENORS)}

    treasury = Mock(side_effect=treasury_year)
    monkeypatch.setattr(fetch_data, 'fetch_treasury_year', treasury)
    canada = Mock()
    canada.json.return_value = canada_fixture()
    overnight = Mock()
    overnight.json.return_value = {'refRates': [{'effectiveDate': '2026-11-03', 'type': 'SOFR', 'percentRate': 3.97}]}
    request = Mock(side_effect=[canada, overnight])
    monkeypatch.setattr(fetch_data, 'get_response', request)
    fetch_data.main()
    data = json.loads(output.read_text())
    assert sorted(call.args[0] for call in treasury.call_args_list) == list(range(1990, 2027))
    assert request.call_args_list[0].kwargs['params']['start_date'] == '1990-01-01'
    assert '1980-01-02' not in data['history']['us']
    assert data['history']['us']['2026-11-03'][0] is None
    assert data['overnight_history']['us'] == {'2026-11-03': 3.97}
    assert data['date'] == '2026-11-02'
    validate_dataset(data)


def test_display_embeds_history_for_offline_date_comparisons():
    data = official_snapshot(us={'1990-01-02': [None, *([8]*10)], '2026-11-02': [4]*len(TENORS)})
    display = build_site.display_data(data)
    assert display['history'] == data['history']
    assert display['overnight_history'] == data['overnight_history']
    assert display['history']['us']['1990-01-02'][0] is None
    assert 'coverage' not in display
