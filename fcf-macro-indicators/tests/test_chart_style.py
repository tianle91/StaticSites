"""Presentation must preserve chart data and the controls that act on it."""
import json

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from chart_style import chart_page, plotly_style


def test_styling_preserves_data_buttons_shapes_and_slider_scope():
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True)
    for row in (1, 2, 3):
        fig.add_trace(go.Scatter(x=[1, 2], y=[100, 110], name=f'Series {row}'), row=row, col=1)
    fig.update_xaxes(rangeslider=dict(visible=True), row=3, col=1)
    fig.add_shape(type='line', x0=1, x1=1, y0=0, y1=1)
    fig.update_layout(updatemenus=[dict(buttons=[
        dict(label='Linear', method='relayout', args=[{'yaxis.type': 'linear'}]),
        dict(label='Log', method='relayout', args=[{'yaxis.type': 'log'}]),
    ])])
    before = fig.to_plotly_json()
    plotly_style(fig, height=1100, bottom=240)
    after = fig.to_plotly_json()
    assert after['data'] == before['data']
    assert after['layout']['shapes'] == before['layout']['shapes']
    assert after['layout']['updatemenus'][0]['buttons'] == before['layout']['updatemenus'][0]['buttons']
    assert fig.layout.xaxis.rangeslider.visible is not True
    assert fig.layout.xaxis2.rangeslider.visible is not True
    assert fig.layout.xaxis3.rangeslider.visible is True


def test_page_wrapper_preserves_interaction_targets_and_escapes_labels():
    original = '<html><head></head><body><div id="chart-id"></div><script>window.chartReady=true;</script></body></html>'
    html = chart_page(original, title='Cash &amp; <unsafe>', subtitle='Levels < 100',
                      sources=[('Source <A>', 'https://example.com/?a=1&b=2')],
                      pulled='2026-10-01', hint='<span id="rebase-anchor-label">2020</span>',
                      script='<script>window.rebaseReady=true;</script>')
    assert 'id="chart-id"' in html and 'id="rebase-anchor-label"' in html
    assert 'window.chartReady=true' in html and 'window.rebaseReady=true' in html
    assert 'Cash &amp; &lt;unsafe&gt;' in html and 'Levels &lt; 100' in html
    assert 'Source &lt;A&gt;' in html
    assert '<summary>Data sources</summary>' in html
    assert html.count('<body>') == html.count('</body>') == 1
