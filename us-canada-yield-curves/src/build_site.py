"""Embed validated curve data and chart assets into a standalone HTML page."""
import json
from pathlib import Path

from staticsites.assets import ASSETS, script_json
from staticsites.pipeline import write_if_changed
from fetch_data import validate_dataset

ROOT = Path(__file__).resolve().parent.parent


def display_data(data):
    payload = {key: value for key, value in data.items()
               if key not in ('overnight_sources', 'coverage')}
    if 'overnight_history' in data:
        payload['series'] = [
            {**series, 'overnightName': 'SOFR' if series['id'] == 'us' else 'CORRA',
             'overnight': data['overnight_history'][series['id']].get(data['date'])}
            for series in data['series']
        ]
        payload['sources'] = [*data['sources'], *data['overnight_sources']]
    return payload


def build():
    data = validate_dataset(json.loads((ROOT / 'data/curves.json').read_text()))
    # Embed official history so both date selections work offline.
    data = display_data(data)
    source = ROOT / 'src'
    style = '\n'.join((ASSETS / 'plots' / name).read_text()
                      for name in ('page.css', 'chart.css', 'page-mobile.css'))
    behavior = (ASSETS / 'plots/hover.js').read_text() + '\n' + (source / 'app.js').read_text()
    page = (source / 'page.html').read_text()
    for marker, value in [('__STYLE__', style), ('__DATA__', script_json(data)), ('__APP__', behavior)]:
        page = page.replace(marker, value)
    target = ROOT / 'output/us-canada-yield-curves.html'
    write_if_changed(target, page)
    return target


if __name__ == '__main__':
    print('Built ' + str(build()))
