"""Project-local chart presentation; deliberately copied, never imported across projects."""
from html import escape, unescape
from pathlib import Path
import textwrap
import re

INK = '#182d37'
MUTED = '#596b71'
PAPER = '#f5f6f3'
SURFACE = '#ffffff'
GRID = '#dce2df'
FONT = '-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'


def compact_label(label):
    """Source codes belong in hover text and provenance, not a crowded legend."""
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


def plotly_style(fig, *, height, bottom):
    """Match the SVG/PNG typography and grid, while retaining analytical controls."""
    fig.update_layout(
        title=None, height=height, autosize=True,
        font=dict(family=FONT, size=12, color=INK),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        margin=dict(l=76, r=30, t=95, b=bottom),
        # A horizontal legend keeps long source labels from shrinking the plot.
        # Space below the range slider is reserved explicitly by each renderer.
        legend=dict(orientation='h', x=0, y=-.30, xanchor='left', yanchor='top',
                    bgcolor='rgba(0,0,0,0)', borderwidth=0,
                    font=dict(size=11, color=INK)),
        hoverlabel=dict(bgcolor=INK, bordercolor=INK,
                        font=dict(family=FONT, size=12, color=SURFACE)),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(size=11, color=MUTED), title_font=dict(size=12, color=MUTED),
                     spikecolor=MUTED)
    for name in fig.layout:
        if not name.startswith('xaxis'):
            continue
        axis = fig.layout[name]
        # Styling must not create a new slider on another subplot.
        if axis.rangeslider.visible is True:
            axis.rangeslider.update(bgcolor=PAPER, bordercolor=GRID, borderwidth=1)
        if axis.rangeselector.buttons:
            axis.rangeselector.update(bgcolor=PAPER, activecolor=GRID,
                                      bordercolor=GRID, borderwidth=1,
                                      font=dict(size=11, color=INK))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(size=11, color=MUTED), title_font=dict(size=12, color=MUTED))
    fig.update_annotations(font=dict(family=FONT, size=12, color=INK))
    for menu in fig.layout.updatemenus:
        menu.update(bgcolor=SURFACE, bordercolor=GRID, borderwidth=1,
                    font=dict(family=FONT, size=11, color=INK))


def chart_page(plot_html, *, title, subtitle, sources, pulled, hint='', script=''):
    """Wrap Plotly's generated body without changing trace data or interaction JS."""
    body = plot_html.split('<body>', 1)[1].rsplit('</body>', 1)[0]
    style = Path(__file__).with_name('chart.css').read_text(encoding='utf-8')
    title = escape(unescape(title))
    links = ''.join(f'<li><a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{escape(name)}</a></li>'
                    for name, url in sources)
    stamp = f'<p>Data pulled {escape(pulled)}</p>' if pulled else ''
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{style}</style></head>
<body><main><header><p class="eyebrow">MARKETS & LIQUIDITY</p>
<h1>{title}</h1><p class="subtitle">{escape(subtitle)}</p></header>
<section class="explorer" aria-label="Interactive chart">{hint}{body}</section>
<p class="hint">Drag to zoom · Double-click to reset · Click legend entries to toggle series</p>
<footer><details><summary>Data sources</summary>{stamp}<ul>{links}</ul></details></footer>
</main>{script}</body></html>
'''
