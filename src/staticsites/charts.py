"""Shared native chart page and Matplotlib presentation components."""
from html import escape, unescape
from pathlib import Path
import textwrap
import re
import json
import math
from staticsites.assets import script_json

INK = '#182d37'
MUTED = '#596b71'
PAPER = '#f5f6f3'
SURFACE = '#ffffff'
GRID = '#dce2df'
FONT = '-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'


def compact_label(label):
    """Keep source codes in provenance and use compact labels on the chart."""
    label = re.sub(r'\s*\((?:FRED:|\^GSPC|FINRA,)[^)]*\)', '', label)
    return (label.replace(' (basket sum)', '')
            .replace('Aggregate cash & equivalents', 'Aggregate cash')
            .replace('Money-market-fund assets', 'Money-market funds')
            .replace('Yield-curve inversion (10Y < 2Y)', '10Y < 2Y inversion'))


def matplotlib_style():
    import matplotlib.pyplot as plt
    # Reset global Matplotlib state so one render cannot inherit a caller's theme.
    plt.style.use('default')
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 10, 'text.color': INK,
        'figure.facecolor': PAPER, 'savefig.facecolor': PAPER,
        'axes.facecolor': SURFACE, 'axes.edgecolor': GRID, 'axes.labelcolor': INK,
        'axes.titlecolor': INK, 'axes.titleweight': 'bold',
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.grid': True, 'axes.axisbelow': True,
        'grid.color': GRID, 'grid.linewidth': .7,
        'xtick.color': MUTED, 'ytick.color': MUTED,
        'xtick.labelsize': 9, 'ytick.labelsize': 9,
        'legend.frameon': False, 'legend.fontsize': 9,
    })


def png_sources(fig, sources, pulled):
    label = (f'Data pulled {pulled} · ' if pulled else '') + 'Data sources: '
    label += ' · '.join(f'{name} ({url})' for name, url in sources)
    fig.text(.02, .012, textwrap.fill(label, width=175, break_long_words=False,
                                    break_on_hyphens=False),
             ha='left', va='bottom', fontsize=7, color=MUTED)


def series_data(values, *, name, color, key):
    """Keep real zeroes and explicit missing values; never interpolate for display."""
    points = []
    for date, value in values.items():
        try:
            number = float(value)
            number = number if math.isfinite(number) else None
        except (TypeError, ValueError):
            number = None
        points.append({'date': date.strftime('%Y-%m-%d'), 'value': number})
    return {'id': key, 'name': name, 'color': color, 'points': points}


def chart_page(payload, *, title, subtitle, sources, pulled, context=''):
    """One offline HTML artifact using native SVG, with no plotting runtime/CDN."""
    source = Path(__file__).parent / 'assets' / 'plots'
    style = (source / 'page.css').read_text(encoding='utf-8') + (source / 'chart.css').read_text(encoding='utf-8') + (source / 'page-mobile.css').read_text(encoding='utf-8')
    behavior = '\n'.join((source / name).read_text(encoding='utf-8') for name in ('hover.js', 'chart.js'))
    title = escape(unescape(title))
    encoded = script_json(payload)
    links = ''.join(f'<li><a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{escape(name)}</a></li>'
                    for name, url in sources)
    stamp = f'<p>Data pulled {escape(pulled)}</p>' if pulled else ''
    events = ''.join(f'<li>{escape(event["date"])}: {escape(event["label"])}</li>' for event in payload.get('events', []))
    events = '<p>Market event markers</p><ul>' + events + '</ul>' if events else ''
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{style}</style></head>
<body><main><header><p class="eyebrow">MARKETS & LIQUIDITY</p>
<h1>{title}</h1><p class="subtitle">{escape(subtitle)}</p></header>
<section class="explorer" aria-label="Chart">
<div id="chart-legend" class="legend" aria-label="Toggle chart series"></div>
<p class="series-description">{escape(context)}</p><div id="chart-choices" class="chart-choices"></div>
<div id="chart" class="chart" tabindex="0" role="group" aria-label="Chart. Use arrow keys to inspect observations."></div>
<div class="inspection-status" role="status" aria-atomic="true"><p id="inspect-period"></p><div id="readout"></div></div>
<p class="hint">Hover, tap the plot or use arrow keys to inspect · Tap legend entries to toggle series</p></section>
<footer><details><summary>Definitions & data sources</summary>{stamp}<p>{escape(context)}</p>{events}<ul>{links}</ul></details></footer>
</main><script id="chart-data" type="application/json">{encoded}</script><script>{behavior}</script></body></html>
'''
