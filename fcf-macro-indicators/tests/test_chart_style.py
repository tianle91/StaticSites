"""Native pages preserve observations and need no external rendering runtime."""
import json
import math
import re

import pandas as pd
import pytest

from staticsites.charts import chart_page, series_data
from plot_fcf_macro import build_rebased, chart_payload, render_html


def test_missing_values_stay_gaps_and_zero_is_not_dropped():
    values = pd.Series([1., float('nan'), 0.], index=pd.date_range('2024-01-31', periods=3, freq='ME'))
    trace = series_data(values, name='A', color='#116965', key='a')
    assert [point['value'] for point in trace['points']] == [1., None, 0.]
    assert [point['date'] for point in trace['points']] == ['2024-01-31','2024-02-29','2024-03-31']


def test_page_payload_is_escaped_and_sources_stay_linked():
    payload = {'domain':['2024-01-01','2024-12-31'], 'panels':[], 'note':'</script><unsafe>'}
    html = chart_page(payload, title='Cash &amp; <unsafe>', subtitle='Levels < 100',
                      sources=[('Source <A>', 'https://example.com/?a=1&b=2')], pulled='2026-10-01')
    assert 'Cash &amp; &lt;unsafe&gt;' in html and 'Levels &lt; 100' in html
    assert 'Source &lt;A&gt;' in html
    embedded = re.search(r'<script id="chart-data" type="application/json">(.*?)</script>', html, re.S)[1]
    assert json.loads(embedded) == payload
    assert '<unsafe>' not in html
    assert 'Definitions & data sources' in html
    assert not re.search(r'<script[^>]+src=',html)


def test_native_payload_keeps_source_coordinates_and_units():
    frame = build_rebased(None)
    payload = chart_payload(frame)
    assert payload['domain'] == [frame.index.min().strftime('%Y-%m-%d'),frame.index.max().strftime('%Y-%m-%d')]
    direct = [series for panel in payload['panels'] if not panel.get('choices') for series in panel['series']]
    assert len(direct) == len(frame.columns)
    for series in direct:
        values = frame[series['id']]
        assert len(series['points']) == len(values)
        for point,(date,value) in zip(series['points'],values.items()):
            assert point['date'] == date.strftime('%Y-%m-%d')
            assert point['value'] == (None if not math.isfinite(float(value)) else float(value))
    if len(payload['panels']) > 1:
        assert payload['panels'][1]['unit'] == '%'
        assert len(payload['panels'][2]['choices']) == 2
        assert all(choice['series'][0]['points'][0]['value'] == pytest.approx(100) for choice in payload['panels'][2]['choices'])


def test_html_build_is_deterministic_and_has_no_plotly(tmp_path):
    frame = build_rebased(None)
    target = tmp_path / 'chart.html'
    render_html(frame,target)
    original,mtime = target.read_bytes(),target.stat().st_mtime_ns
    render_html(frame,target)
    assert target.read_bytes() == original and target.stat().st_mtime_ns == mtime
    html = target.read_text()
    assert 'plotly' not in html.lower()
    assert 'chart-legend' in html and 'inspect-period' in html
    assert 'zoom' not in html.lower()
