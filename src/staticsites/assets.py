"""Embed shared components at build time, never as runtime repo dependencies."""
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
SHARED = {"explorer.js": "maps/explorer.js", "explorer.css": "maps/explorer.css",
          "chart.js": "plots/chart.js", "chart.css": "plots/chart.css"}


def source_text(project, filename):
    path = ASSETS / SHARED[filename] if filename in SHARED else Path(project) / "src" / filename
    return path.read_text(encoding="utf-8")


def read_template(path):
    text = Path(path).read_text(encoding="utf-8")
    for token, asset in {"__MAP_TABS__": "maps/tabs.html"}.items():
        if token in text:
            text = text.replace(token, (ASSETS / asset).read_text(encoding="utf-8"))
    return text

