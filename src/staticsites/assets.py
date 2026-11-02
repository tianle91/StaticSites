"""Embed shared components at build time, never as runtime repo dependencies."""
from pathlib import Path
import json

ASSETS = Path(__file__).parent / "assets"
SHARED = {"explorer.js": "maps/explorer.js", "explorer.css": "maps/explorer.css",
          "chart.js": "plots/chart.js", "chart.css": "plots/chart.css",
          "query.js": "maps/query.js"}


def script_json(value):
    """Readable JSON safe inside an HTML script element, without invalid numbers."""
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
            .replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))


def source_text(project, filename):
    path = ASSETS / SHARED[filename] if filename in SHARED else Path(project) / "src" / filename
    return path.read_text(encoding="utf-8")


def read_template(path):
    text = Path(path).read_text(encoding="utf-8")
    for token, asset in {"__MAP_TABS__": "maps/tabs.html"}.items():
        if token in text:
            text = text.replace(token, (ASSETS / asset).read_text(encoding="utf-8"))
    return text

