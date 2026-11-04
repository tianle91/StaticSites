"""Offline, deterministic, single-file dashboard build from committed inputs."""
import json
from pathlib import Path

from fetch_data import validate_dataset
from staticsites.assets import ASSETS
from staticsites.assets import script_json
from staticsites.pipeline import write_if_changed

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
OUT_DIR = ROOT / 'output'


def build():
    data = validate_dataset(json.loads((DATA_DIR / 'series.json').read_text()))
    source = ROOT / 'src'
    html = (source / 'page.html').read_text()
    # Avoid a data string closing the script element, even if an upstream label changes.
    payload = script_json(data)
    for marker, value in [('__STYLE__', (ASSETS / 'plots/page.css').read_text() + (source / 'style.css').read_text() + (ASSETS / 'plots/page-mobile.css').read_text()),
                          ('__DATA__', payload),
                          ('__TIMELINE__', (source / 'timeline.js').read_text()),
                          ('__HOVER__', (ASSETS / 'plots/hover.js').read_text()),
                          ('__APP__', (source / 'app.js').read_text())]:
        html = html.replace(marker, value)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / 'canada-mortgage-stress.html'
    write_if_changed(target, html)
    return target


if __name__ == '__main__':
    print(f'Built {build()}')
