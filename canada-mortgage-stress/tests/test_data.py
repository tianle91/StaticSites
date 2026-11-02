"""Regression checks for economic meaning, parser ordering and safe publication."""
from copy import deepcopy
import json
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from fetch_data import (collect, parse_monthly_text, publish, quarterly_group,
                        validate_dataset)
import build_site
import fetch_data
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def data():
    return json.loads((ROOT / 'data/series.json').read_text())


def series(data, group, name):
    return next(s['points'] for g in data['groups'] if g['id'] == group
                for s in g['series'] if s['name'] == name)


def test_reference_observations_and_forecast_boundary(data):
    ontario = {p['period']: p for p in series(data, 'provinces', 'Ontario')}
    assert ontario['2022-Q2']['value'] == .06
    assert ontario['2026-Q2']['value'] == .32
    private = series(data, 'private', 'GTHA')
    assert private[-1]['period'] == '2026-Q1'
    assert private[-1]['value'] == 11.14
    outlook = series(data, 'outlook', 'Ontario')
    assert [p['period'] for p in outlook if p['status'] == 'observed'][-1] == '2026-06'
    assert [p['period'] for p in outlook if p['status'] == 'forecast'][0] == '2026-07'
    assert outlook[-1] == {'period': '2027-06', 'value': .44, 'status': 'forecast'}


@pytest.mark.parametrize('year,period,value', [
    ('2021','2020-01',838087), ('2021','2021-12',1157849),
    ('2023','2022-02',1334021), ('2023','2023-12',1084692),
    ('2025','2024-01',1028699), ('latest','2026-09',1006409),
])
def test_pdf_layouts_preserve_year_month_and_price(year, period, value):
    parsed = parse_monthly_text((FIXTURES / f'trreb-{year}.txt').read_text(), 'source.pdf')
    assert parsed[period]['value'] == value
    assert parsed[period]['source'] == 'source.pdf'
    assert len(parsed) == (21 if year == 'latest' else 24)


def test_unreadable_pdf_table_fails():
    with pytest.raises(ValueError, match='Incomplete'):
        parse_monthly_text('Monthly Statistics 2025\nJanuary 100 $1,000,000', 'bad.pdf')


def test_quarterly_parser_rejects_missing_value():
    soup = BeautifulSoup('<table><caption>Arrears</caption><tr><th>Quarter</th><th>Ontario</th></tr>'
                         '<tr><th>2026 Q1</th></tr></table>', 'html.parser')
    with pytest.raises(ValueError, match='Malformed quarterly'):
        quarterly_group(soup, 'test', 'Test', 'Arrears', 'note', 'source', 1)


def test_price_coverage_break_is_two_series(data):
    group = next(g for g in data['groups'] if g['id'] == 'prices')
    old, new = group['series']
    assert old['points'][-1]['period'] == '2023-12'
    assert new['points'][0]['period'] == '2024-01'
    assert 'not a quality-adjusted HPI' in group['note']
    assert 'balance' in next(g['note'] for g in data['groups'] if g['id'] == 'private')


@pytest.mark.parametrize('damage', ['duplicate', 'gap', 'nan', 'negative', 'rate_over_100'])
def test_corrupt_source_records_are_rejected(data, damage):
    points = data['groups'][0]['series'][0]['points']
    if damage == 'duplicate': points.insert(1, deepcopy(points[0]))
    elif damage == 'gap': points.pop(1)
    elif damage == 'nan': points[0]['value'] = float('nan')
    elif damage == 'negative': points[0]['value'] = -1
    else: points[0]['value'] = 101
    with pytest.raises(ValueError): validate_dataset(data)


def test_content_aware_atomic_publication(data, tmp_path):
    data.pop('retrieved_at')
    target = tmp_path / 'series.json'
    assert publish(data, target)
    original, mtime = target.read_bytes(), target.stat().st_mtime_ns
    assert not publish(data, target)
    assert target.read_bytes() == original and target.stat().st_mtime_ns == mtime
    invalid = deepcopy(data)
    invalid['groups'][0]['series'][0]['points'][0]['value'] = -1
    with pytest.raises(ValueError): publish(invalid, target)
    assert target.read_bytes() == original
    target.unlink()
    assert publish(data, target)  # Restore a missing committed input.


def test_required_source_failure_does_not_publish(data, tmp_path):
    target = tmp_path / 'series.json'
    target.write_text(json.dumps(data))
    original = target.read_bytes()
    def fail(url): raise RuntimeError('required-source download failed')
    with pytest.raises(RuntimeError): publish(collect(fail), target)
    assert target.read_bytes() == original


@pytest.mark.parametrize('damage', [None, 'terminal', 'prior_year', 'future'])
def test_latest_report_coverage_is_anchored_to_filename(data, tmp_path, monkeypatch, damage):
    """A readable but truncated latest PDF must never replace published history."""
    monkeypatch.setattr(fetch_data, 'parse_cmhc', lambda _: deepcopy(data['groups'][:-2]))
    monkeypatch.setattr(fetch_data, 'parse_annual', lambda _: data['groups'][-1]['series'][0]['points'])

    def parse_fixture(content, source):
        vintage = {'mw2112.pdf': '2021', 'mw2312.pdf': '2023',
                   'mw2512.pdf': '2025', 'mw2609.pdf': 'latest'}[source.rsplit('/', 1)[-1]]
        parsed = parse_monthly_text((FIXTURES / f'trreb-{vintage}.txt').read_text(), source)
        if vintage == 'latest':
            if damage == 'terminal': parsed.pop('2026-09')
            elif damage == 'prior_year': parsed.pop('2025-01')
            elif damage == 'future': parsed['2026-10'] = {**parsed['2026-09'], 'period': '2026-10'}
        return parsed

    monkeypatch.setattr(fetch_data, 'parse_monthly', parse_fixture)

    def get(url):
        return SimpleNamespace(content=b'', text='<a href="/mw2609.pdf">September report</a>')

    target = tmp_path / 'series.json'
    target.write_text(json.dumps(data, indent=2))
    original, mtime = target.read_bytes(), target.stat().st_mtime_ns
    if damage:
        with pytest.raises(ValueError, match='Latest TRREB report must cover.*2026-09'):
            publish(collect(get), target)
        assert target.read_bytes() == original
        assert target.stat().st_mtime_ns == mtime
    else:
        result = collect(get)
        assert result['groups'][-2]['series'][-1]['points'][-1]['period'] == '2026-09'


def test_offline_build_is_deterministic_and_embeds_sources(data, tmp_path, monkeypatch):
    source = tmp_path / 'src'
    source.mkdir()
    for filename in ('page.html','style.css','timeline.js','app.js'):
        (source / filename).write_bytes((ROOT / 'src' / filename).read_bytes())
    inputs = tmp_path / 'data'
    inputs.mkdir()
    (inputs / 'series.json').write_text(json.dumps(data))
    monkeypatch.setattr(build_site, 'ROOT', tmp_path)
    monkeypatch.setattr(build_site, 'DATA_DIR', inputs)
    monkeypatch.setattr(build_site, 'OUT_DIR', tmp_path / 'output')
    def offline(*args, **kwargs): raise AssertionError('Build accessed network')
    monkeypatch.setattr('requests.Session.request', offline)
    target = build_site.build()
    original, mtime = target.read_bytes(), target.stat().st_mtime_ns
    assert build_site.build().read_bytes() == original
    assert target.stat().st_mtime_ns == mtime
    html = target.read_text()
    assert all(marker not in html for marker in ('__DATA__','__TIMELINE__','__APP__','__STYLE__'))
    soup = BeautifulSoup(html,'html.parser')
    assert json.loads(soup.select_one('#dataset').string) == data
    assert not soup.select('script[src],link[rel=stylesheet]')
    assert 'data sources' in html.lower()
    assert len(soup.select('#chart')) == 1
    assert not soup.select('#plots, #show-private, #headlines, #coverage')
    assert not soup.select('#bank-type, #price-type, #from, #to, [data-start]')
    assert 'Monthly bank arrears + CMHC forecast' in html
