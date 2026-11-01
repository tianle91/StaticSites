"""Offline, deterministic, single-file dashboard build from committed inputs."""
import json
from pathlib import Path

from fetch_data import validate_dataset

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
OUT_DIR = ROOT / 'output'


def build():
    data = validate_dataset(json.loads((DATA_DIR / 'series.json').read_text()))
    source = ROOT / 'src'
    html = (source / 'page.html').read_text()
    # Avoid a data string closing the script element, even if an upstream label changes.
    payload = json.dumps(data, indent=2, ensure_ascii=False).replace('<', '\\u003c')
    for marker, value in [('__STYLE__', (source / 'style.css').read_text()),
                          ('__DATA__', payload), ('__APP__', (source / 'app.js').read_text())]:
        html = html.replace(marker, value)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / 'canada-mortgage-stress.html'
    if not target.exists() or target.read_text() != html:
        target.write_text(html)
    return target


if __name__ == '__main__':
    print(f'Built {build()}')
